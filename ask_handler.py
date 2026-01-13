"""
Ask Handler - Claude Agent SDK integration for vault queries.

Uses Claude Code's built-in tools (Read, Grep, Glob) with read-only enforcement.
Requires ClaudeSDKClient (streaming mode) for can_use_tool callback.
"""
import logging

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

import config

logger = logging.getLogger(__name__)

# Read-only tools whitelist
READ_ONLY_TOOLS = {"Read", "Grep", "Glob", "LS"}

# Blocked file patterns (security)
BLOCKED_PATTERNS = [".env", "credentials", "secrets", ".git/"]

SYSTEM_PROMPT = """You are answering questions about a personal knowledge vault (markdown files).

Rules:
1. ONLY use information found in the vault files - never hallucinate
2. If you can't find relevant information, say "I couldn't find that in your vault"
3. Reference which files you found information in
4. Keep answers concise (under 400 words for Telegram)
5. Search broadly first, then read specific files

Tips:
- Use Grep to search for keywords across all files
- Use Glob to find files by name pattern
- Use Read to get full file contents
- Check for README.md, INDEX.md, or similar overview files first
"""


async def enforce_read_only(
    tool_name: str,
    tool_input: dict,
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Block all write operations - whitelist approach."""

    # Only allow specific read tools
    if tool_name not in READ_ONLY_TOOLS:
        logger.warning(f"Blocked tool: {tool_name}")
        return PermissionResultDeny(
            behavior="deny",
            message=f"Tool '{tool_name}' not allowed (read-only mode)",
            interrupt=False,
        )

    # Check for sensitive file access
    file_path = str(tool_input.get("file_path", "") or tool_input.get("path", ""))

    for pattern in BLOCKED_PATTERNS:
        if pattern in file_path.lower():
            logger.warning(f"Blocked sensitive file access: {file_path}")
            return PermissionResultDeny(
                behavior="deny",
                message="Cannot read sensitive files",
                interrupt=False,
            )

    return PermissionResultAllow(behavior="allow", updated_input=tool_input)


async def ask_vault(question: str, model: str = None) -> dict:
    """
    Query the vault using Claude Agent SDK with ClaudeSDKClient (streaming mode).

    Args:
        question: The user's question
        model: "sonnet" or "haiku" (defaults to config.DEFAULT_MODEL)

    Returns:
        dict with 'answer', 'cost_usd', 'model', 'usage'
    """
    if model is None:
        model = config.DEFAULT_MODEL

    # Get model-specific settings
    if model == "sonnet":
        max_turns = config.MAX_TURNS_SONNET
        max_budget = config.MAX_BUDGET_SONNET
    else:
        max_turns = config.MAX_TURNS_HAIKU
        max_budget = config.MAX_BUDGET_HAIKU

    options = ClaudeAgentOptions(
        cwd=str(config.VAULT_PATH),
        allowed_tools=list(READ_ONLY_TOOLS),
        can_use_tool=enforce_read_only,
        system_prompt=SYSTEM_PROMPT,
        max_turns=max_turns,
        max_budget_usd=max_budget,
        model=model,
    )

    answer_parts = []
    total_cost = 0.0
    model_used = "unknown"
    usage_info = {}

    logger.info(f"Starting vault query: {question[:50]}...")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(question)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    if message.model:
                        model_used = message.model
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            answer_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    total_cost = message.total_cost_usd
                    if message.usage:
                        usage_info = message.usage
                    logger.info(f"Query completed. Model: {model_used}, Cost: ${total_cost:.4f}, Usage: {usage_info}")

    except Exception as e:
        logger.error(f"Claude Agent SDK error: {e}")
        raise

    answer = "\n".join(answer_parts).strip()

    if not answer:
        answer = "I wasn't able to find an answer to your question in the vault."

    return {
        "answer": answer,
        "cost_usd": total_cost,
        "model": model_used,
        "usage": usage_info,
    }
