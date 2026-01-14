#!/usr/bin/env python3
"""
Telegram Brain Claude

Capture messages to your vault and query it with Claude AI.
Uses python-telegram-bot v22+ API and Claude Agent SDK.
"""
import asyncio
import hashlib
import logging
import time
from datetime import datetime

from telegram import (
    Update,
    ReactionTypeEmoji,
    MessageOriginUser,
    MessageOriginHiddenUser,
    MessageOriginChat,
    MessageOriginChannel,
)
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

import config
from note_formatter import format_note, generate_filename
from git_ops import save_and_push_note
from ask_handler import ask_vault
from rate_limiter import RateLimiter

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Track last error for status command
last_error: str | None = None

# Rate limiter instance
rate_limiter = RateLimiter(
    cooldown_seconds=config.QUERY_COOLDOWN_SECONDS,
    daily_budget_usd=config.DAILY_BUDGET_USD,
    cache_ttl_seconds=config.CACHE_TTL_SECONDS,
)

# Message deduplication
_message_hashes: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 300  # 5 minutes


def _hash_message(content: str, timestamp: int) -> str:
    """Generate hash for message deduplication."""
    return hashlib.md5(f"{content}:{timestamp}".encode()).hexdigest()


def is_duplicate_message(content: str, timestamp: int) -> bool:
    """Check if message is a duplicate. Returns True if duplicate."""
    msg_hash = _hash_message(content, timestamp)
    now = time.time()

    # Clean old hashes
    expired = [h for h, t in _message_hashes.items() if now - t > DEDUP_WINDOW_SECONDS]
    for h in expired:
        del _message_hashes[h]

    if msg_hash in _message_hashes:
        return True

    _message_hashes[msg_hash] = now
    return False


def clear_message_hashes() -> None:
    """Clear all message hashes (for testing)."""
    _message_hashes.clear()


def get_forward_source(message) -> str | None:
    """Extract forward source from message using v22+ API."""
    if not message.forward_origin:
        return None

    origin = message.forward_origin

    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.full_name
    elif isinstance(origin, MessageOriginHiddenUser):
        return origin.sender_user_name
    elif isinstance(origin, MessageOriginChat):
        return origin.chat.title or "Chat"
    elif isinstance(origin, MessageOriginChannel):
        return origin.chat.title or "Channel"
    else:
        return "Unknown"


def get_message_content(message) -> str:
    """Extract content from message, handling different types."""
    content = message.text or message.caption or ""

    if content:
        return content

    # Handle non-text message types
    if message.voice:
        return "[Voice message - transcription not available]"
    elif message.photo:
        return "[Photo - not downloaded]"
    elif message.document:
        filename = message.document.file_name or "unnamed"
        return f"[Document: {filename}]"
    elif message.video:
        return "[Video - not downloaded]"
    elif message.sticker:
        emoji = message.sticker.emoji or ""
        return f"[Sticker {emoji}]"
    elif message.location:
        return f"[Location: {message.location.latitude}, {message.location.longitude}]"
    else:
        return "[Unsupported message type]"


def get_recent_captures(limit: int = 5) -> list[dict]:
    """Get recent Telegram captures from inbox folder."""
    inbox_path = config.VAULT_PATH / config.INBOX_FOLDER
    captures = []

    if not inbox_path.exists():
        return captures

    for f in sorted(inbox_path.glob("*Telegram Capture.md"), reverse=True)[:limit]:
        name = f.stem.replace(" Telegram Capture", "")
        content = f.read_text().split("---")[-1].strip()[:50]
        if len(content) == 50:
            content += "..."
        captures.append({"time": name, "preview": content})

    return captures


def get_today_count() -> int:
    """Count captures from today."""
    inbox_path = config.VAULT_PATH / config.INBOX_FOLDER
    if not inbox_path.exists():
        return 0
    today = datetime.now().strftime("%Y-%m-%d")
    return len(list(inbox_path.glob(f"{today}*Telegram Capture.md")))


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    global last_error
    message = update.message
    if not message or not message.from_user:
        return

    if message.from_user.id != config.TELEGRAM_USER_ID:
        return

    lines = ["✅ *Bot Status*", ""]

    today_count = get_today_count()
    lines.append(f"📊 *Today:* {today_count} captures")

    # Budget info
    user_id = message.from_user.id
    daily_spend = rate_limiter.get_daily_spend(user_id)
    remaining = rate_limiter.get_remaining_budget(user_id)
    lines.append(f"💰 *Budget:* ${daily_spend:.2f} spent / ${remaining:.2f} remaining")
    lines.append("")

    captures = get_recent_captures(5)
    if captures:
        lines.append("📝 *Recent:*")
        for c in captures:
            lines.append(f"• `{c['time']}` {c['preview']}")
    else:
        lines.append("📝 *Recent:* None")

    lines.append("")

    if last_error:
        lines.append(f"⚠️ *Last error:* {last_error}")
    else:
        lines.append("✓ No errors")

    await message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    message = update.message
    if not message or not message.from_user:
        return

    if message.from_user.id != config.TELEGRAM_USER_ID:
        return

    help_text = """*Telegram Brain Claude*

*Capture:*
• Send any message → Saved to vault inbox

*Query:*
• `/ask` or `/a` <question> → Query vault (Sonnet)
• `/quick` or `/q` <question> → Query vault (Haiku)

*Info:*
• `/status` → Capture stats
• `/help` → This message

*Examples:*
`/a what are my current priorities?`
`/q summarize my recent notes`
"""
    await message.reply_text(help_text, parse_mode="Markdown")


async def _handle_vault_query(update: Update, context: ContextTypes.DEFAULT_TYPE, model: str) -> None:
    """Shared handler for vault queries with specified model."""
    message = update.message
    if not message or not message.from_user:
        return

    user_id = message.from_user.id
    if user_id != config.TELEGRAM_USER_ID:
        return

    question = " ".join(context.args) if context.args else ""
    if not question:
        cmd = "/ask" if model == "sonnet" else "/quick"
        await message.reply_text(f"Usage: {cmd} <your question>")
        return

    # Check rate limit
    allowed, rate_msg = rate_limiter.check_rate_limit(user_id)
    if not allowed:
        await message.reply_text(f"⏳ {rate_msg}")
        return

    # Check budget
    allowed, budget_msg = rate_limiter.check_budget(user_id)
    if not allowed:
        await message.reply_text(f"💰 {budget_msg}")
        return

    # Check cache
    cached = rate_limiter.get_cached_result(user_id, question)
    if cached:
        response = cached["answer"]
        if len(response) > 3900:
            response = response[:3900] + "\n\n_[Truncated]_"
        response += "\n\n_[Cached result]_"
        await message.reply_text(response, parse_mode="Markdown")
        return

    emoji = "🔍" if model == "sonnet" else "⚡"
    progress_msg = await message.reply_text(f"{emoji} Searching vault...")

    stop_typing = asyncio.Event()

    async def keep_typing():
        while not stop_typing.is_set():
            try:
                await message.chat.send_action("typing")
            except Exception:
                pass
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(keep_typing())

    try:
        result = await ask_vault(question, model=model)

        stop_typing.set()
        await typing_task

        # Record spend and cache result
        rate_limiter.record_spend(user_id, result["cost_usd"])
        rate_limiter.cache_result(user_id, question, result)

        response = result["answer"]

        if len(response) > 3900:
            response = response[:3900] + "\n\n_[Truncated]_"

        model_short = result['model'].replace('claude-', '').replace('-20250514', '')
        usage = result.get('usage', {})
        in_tok = usage.get('input_tokens', 0)
        out_tok = usage.get('output_tokens', 0)
        if in_tok or out_tok:
            response += f"\n\n_{model_short} | {in_tok:,}→{out_tok:,} tok | ${result['cost_usd']:.3f}_"
        else:
            response += f"\n\n_{model_short} | ${result['cost_usd']:.3f}_"

        await progress_msg.edit_text(response, parse_mode="Markdown")

    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error(f"Ask command failed: {e}")
        await progress_msg.edit_text(f"❌ Error: {str(e)[:200]}")


async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask and /a commands - query vault using Sonnet (thorough)."""
    await _handle_vault_query(update, context, model="sonnet")


async def handle_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quick and /q commands - query vault using Haiku (fast)."""
    await _handle_vault_query(update, context, model="haiku")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages - capture to vault."""
    global last_error
    message = update.message
    if not message:
        return

    if not message.from_user:
        logger.warning("Message without from_user, ignoring")
        return

    user_id = message.from_user.id

    if user_id != config.TELEGRAM_USER_ID:
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return

    content = get_message_content(message)
    forward_from = get_forward_source(message)

    # Check for duplicate
    msg_timestamp = int(message.date.timestamp())
    if is_duplicate_message(content, msg_timestamp):
        logger.info(f"Skipping duplicate message: {content[:50]}...")
        await message.set_reaction([ReactionTypeEmoji("👀")])  # Eyes = already seen
        return

    now = datetime.now()
    filename = generate_filename(now)
    note_content = format_note(content, now, forward_from)

    logger.info(f"Saving note: {filename}")
    result = save_and_push_note(str(config.VAULT_PATH), filename, note_content)

    try:
        if result["success"]:
            await message.set_reaction([ReactionTypeEmoji("👍")])
            logger.info(f"Successfully saved and pushed: {filename}")
            last_error = None
        else:
            await message.set_reaction([ReactionTypeEmoji("👎")])
            last_error = result["error"]
            logger.error(f"Failed to save: {result['error']}")
    except Exception as e:
        logger.warning(f"Could not set reaction: {e}")


def main() -> None:
    """Start the bot."""
    config.validate_config()

    logger.info(f"Starting bot for user {config.TELEGRAM_USER_ID}")
    logger.info(f"Vault: {config.VAULT_PATH}")
    logger.info(f"Inbox: {config.INBOX_FOLDER}")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler(["ask", "a"], handle_ask))
    app.add_handler(CommandHandler(["quick", "q"], handle_quick))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    logger.info("Bot started. Waiting for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
