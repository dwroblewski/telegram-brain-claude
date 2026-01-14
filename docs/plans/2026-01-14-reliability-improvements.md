# Telegram Brain Claude: Reliability Improvements

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve system reliability through cost control, data integrity, query optimization, observability, and dependency resilience.

**Architecture:** Five independent improvements to existing modules. Each area has its own test file and integrates with existing code. No breaking changes.

**Tech Stack:** Python 3.10+, pytest, python-telegram-bot v22+, claude-agent-sdk

---

## Area 1: Cost Control & Rate Limiting

### Acceptance Criteria
- [ ] AC1.1: Queries are rate-limited to 1 per 30 seconds per user (configurable)
- [ ] AC1.2: Daily budget tracking with configurable USD limit (default: $1.00)
- [ ] AC1.3: Query results cached for 5 minutes (same question = no API call)
- [ ] AC1.4: User receives clear message when rate-limited or budget exceeded
- [ ] AC1.5: Stats command shows daily spend and remaining budget

### Task 1.1: Add Rate Limit Configuration

**Files:**
- Modify: `config.py:27` (after MAX_TURNS_HAIKU)

**Step 1: Add config variables**

Add to `config.py` after line 27:

```python
# Rate limiting
QUERY_COOLDOWN_SECONDS = int(os.getenv("QUERY_COOLDOWN_SECONDS", "30"))
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "1.00"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
```

**Step 2: Commit**

```bash
git add config.py
git commit -m "feat: add rate limiting config variables"
```

---

### Task 1.2: Create Rate Limiter Module

**Files:**
- Create: `rate_limiter.py`
- Create: `tests/test_rate_limiter.py`

**Step 1: Write failing tests**

Create `tests/test_rate_limiter.py`:

```python
"""Tests for rate_limiter.py - rate limiting and budget tracking."""
import pytest
import time
from unittest.mock import patch
from rate_limiter import RateLimiter


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_first_query_allowed(self):
        """First query should always be allowed."""
        limiter = RateLimiter(cooldown_seconds=30)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is True
        assert msg is None

    def test_immediate_second_query_blocked(self):
        """Query within cooldown should be blocked."""
        limiter = RateLimiter(cooldown_seconds=30)
        limiter.check_rate_limit(user_id=123)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is False
        assert "wait" in msg.lower()

    def test_query_after_cooldown_allowed(self):
        """Query after cooldown should be allowed."""
        limiter = RateLimiter(cooldown_seconds=1)
        limiter.check_rate_limit(user_id=123)
        time.sleep(1.1)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is True

    def test_different_users_independent(self):
        """Different users should have independent rate limits."""
        limiter = RateLimiter(cooldown_seconds=30)
        limiter.check_rate_limit(user_id=123)
        allowed, msg = limiter.check_rate_limit(user_id=456)
        assert allowed is True


class TestBudgetTracking:
    """Test daily budget tracking."""

    def test_under_budget_allowed(self):
        """Queries under budget should be allowed."""
        limiter = RateLimiter(daily_budget_usd=1.00)
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is True

    def test_record_spend_tracks_cost(self):
        """Recording spend should update daily total."""
        limiter = RateLimiter(daily_budget_usd=1.00)
        limiter.record_spend(user_id=123, cost_usd=0.50)
        assert limiter.get_daily_spend(user_id=123) == 0.50

    def test_over_budget_blocked(self):
        """Queries over budget should be blocked."""
        limiter = RateLimiter(daily_budget_usd=0.10)
        limiter.record_spend(user_id=123, cost_usd=0.10)
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is False
        assert "budget" in msg.lower()

    def test_budget_resets_daily(self):
        """Budget should reset at midnight."""
        limiter = RateLimiter(daily_budget_usd=0.10)
        limiter.record_spend(user_id=123, cost_usd=0.10)
        # Simulate day change
        limiter._spend_dates[123] = "2026-01-13"
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is True


class TestQueryCache:
    """Test query result caching."""

    def test_cache_miss_returns_none(self):
        """Uncached query should return None."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result is None

    def test_cache_hit_returns_result(self):
        """Cached query should return stored result."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        expected = {"answer": "cached answer", "cost_usd": 0.0}
        limiter.cache_result(user_id=123, question="test?", result=expected)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result == expected

    def test_cache_expires(self):
        """Cached result should expire after TTL."""
        limiter = RateLimiter(cache_ttl_seconds=1)
        limiter.cache_result(user_id=123, question="test?", result={"answer": "old"})
        time.sleep(1.1)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result is None

    def test_cache_key_includes_question(self):
        """Different questions should have different cache entries."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        limiter.cache_result(user_id=123, question="q1?", result={"answer": "a1"})
        result = limiter.get_cached_result(user_id=123, question="q2?")
        assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/daniel_wroblewski_gmail_com/projects/telegram-brain-claude
python -m pytest tests/test_rate_limiter.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'rate_limiter'"

**Step 3: Implement rate_limiter.py**

Create `rate_limiter.py`:

```python
"""Rate limiting, budget tracking, and query caching for Telegram bot."""
import hashlib
import time
from datetime import datetime
from typing import Optional, Tuple


class RateLimiter:
    """Manages rate limiting, daily budgets, and query caching."""

    def __init__(
        self,
        cooldown_seconds: int = 30,
        daily_budget_usd: float = 1.00,
        cache_ttl_seconds: int = 300,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.daily_budget_usd = daily_budget_usd
        self.cache_ttl_seconds = cache_ttl_seconds

        # Rate limiting: {user_id: last_query_timestamp}
        self._last_query: dict[int, float] = {}

        # Budget tracking: {user_id: daily_spend_usd}
        self._daily_spend: dict[int, float] = {}
        self._spend_dates: dict[int, str] = {}

        # Query cache: {cache_key: (result, timestamp)}
        self._cache: dict[str, tuple[dict, float]] = {}

    def check_rate_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user can query. Returns (allowed, error_message)."""
        now = time.time()

        if user_id in self._last_query:
            elapsed = now - self._last_query[user_id]
            if elapsed < self.cooldown_seconds:
                wait_time = int(self.cooldown_seconds - elapsed)
                return False, f"Please wait {wait_time}s before next query."

        self._last_query[user_id] = now
        return True, None

    def check_budget(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user has remaining budget. Returns (allowed, error_message)."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Reset if new day
        if self._spend_dates.get(user_id) != today:
            self._daily_spend[user_id] = 0.0
            self._spend_dates[user_id] = today

        current_spend = self._daily_spend.get(user_id, 0.0)

        if current_spend >= self.daily_budget_usd:
            return False, f"Daily budget (${self.daily_budget_usd:.2f}) exceeded."

        return True, None

    def record_spend(self, user_id: int, cost_usd: float) -> None:
        """Record API spend for user."""
        today = datetime.now().strftime("%Y-%m-%d")

        if self._spend_dates.get(user_id) != today:
            self._daily_spend[user_id] = 0.0
            self._spend_dates[user_id] = today

        self._daily_spend[user_id] = self._daily_spend.get(user_id, 0.0) + cost_usd

    def get_daily_spend(self, user_id: int) -> float:
        """Get current daily spend for user."""
        today = datetime.now().strftime("%Y-%m-%d")

        if self._spend_dates.get(user_id) != today:
            return 0.0

        return self._daily_spend.get(user_id, 0.0)

    def get_remaining_budget(self, user_id: int) -> float:
        """Get remaining daily budget for user."""
        return max(0.0, self.daily_budget_usd - self.get_daily_spend(user_id))

    def _cache_key(self, user_id: int, question: str) -> str:
        """Generate cache key from user and question."""
        normalized = question.strip().lower()
        return hashlib.md5(f"{user_id}:{normalized}".encode()).hexdigest()

    def get_cached_result(self, user_id: int, question: str) -> Optional[dict]:
        """Get cached result if exists and not expired."""
        key = self._cache_key(user_id, question)

        if key not in self._cache:
            return None

        result, timestamp = self._cache[key]
        if time.time() - timestamp > self.cache_ttl_seconds:
            del self._cache[key]
            return None

        return result

    def cache_result(self, user_id: int, question: str, result: dict) -> None:
        """Cache query result."""
        key = self._cache_key(user_id, question)
        self._cache[key] = (result, time.time())

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries. Returns count removed."""
        now = time.time()
        expired = [
            k for k, (_, ts) in self._cache.items()
            if now - ts > self.cache_ttl_seconds
        ]
        for k in expired:
            del self._cache[k]
        return len(expired)
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_rate_limiter.py -v
```

Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add rate_limiter.py tests/test_rate_limiter.py
git commit -m "feat: add rate limiter with budget tracking and caching"
```

---

### Task 1.3: Integrate Rate Limiter into Bot

**Files:**
- Modify: `bot.py:25` (imports)
- Modify: `bot.py:35` (after last_error)
- Modify: `bot.py:173-229` (_handle_vault_query function)
- Modify: `bot.py:120-141` (handle_status function)

**Step 1: Add imports and instantiate limiter**

In `bot.py`, add after line 25:

```python
from rate_limiter import RateLimiter
```

After line 35 (after `last_error: str | None = None`), add:

```python
# Rate limiter instance
rate_limiter = RateLimiter(
    cooldown_seconds=config.QUERY_COOLDOWN_SECONDS,
    daily_budget_usd=config.DAILY_BUDGET_USD,
    cache_ttl_seconds=config.CACHE_TTL_SECONDS,
)
```

**Step 2: Modify _handle_vault_query to use rate limiter**

Replace the `_handle_vault_query` function (lines 173-229) with:

```python
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
```

**Step 3: Update status command to show budget**

In `handle_status`, after line 124 (`lines.append(f"📊 *Today:* {today_count} captures")`), add:

```python
    # Budget info
    user_id = message.from_user.id
    daily_spend = rate_limiter.get_daily_spend(user_id)
    remaining = rate_limiter.get_remaining_budget(user_id)
    lines.append(f"💰 *Budget:* ${daily_spend:.2f} spent / ${remaining:.2f} remaining")
```

**Step 4: Test manually**

```bash
python bot.py
# In Telegram: send /ask test query
# Immediately send /ask another query - should be rate limited
# Send /status - should show budget info
```

**Step 5: Commit**

```bash
git add bot.py
git commit -m "feat: integrate rate limiter into query flow"
```

---

## Area 2: Data Integrity & Error Recovery

### Acceptance Criteria
- [ ] AC2.1: Git operations use INBOX_FOLDER from config (not hardcoded)
- [ ] AC2.2: Duplicate messages are detected and skipped (5-minute window)
- [ ] AC2.3: File save and git commit are separate operations with clear error reporting
- [ ] AC2.4: User sees distinct reactions for: saved (👍), save failed (❌), git failed (⚠️)

### Task 2.1: Fix Hardcoded Inbox Path in git_ops.py

**Files:**
- Modify: `git_ops.py:1-19`

**Step 1: Write failing test**

Create `tests/test_git_ops.py`:

```python
"""Tests for git_ops.py - git operations."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import git_ops


class TestInboxPath:
    """Test inbox path uses config."""

    @patch('git_ops.config')
    @patch('git_ops.subprocess.run')
    def test_uses_config_inbox_folder(self, mock_run, mock_config):
        """Should use INBOX_FOLDER from config, not hardcoded."""
        mock_config.INBOX_FOLDER = "custom-inbox"
        mock_run.return_value = MagicMock(returncode=0)

        # Create temp dir structure
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_path = Path(tmpdir) / "custom-inbox"
            inbox_path.mkdir()

            result = git_ops.save_and_push_note(
                repo_path=tmpdir,
                filename="test.md",
                content="test content",
                push=False
            )

            # File should be in custom-inbox, not 0-Inbox
            assert (inbox_path / "test.md").exists()
            assert not (Path(tmpdir) / "0-Inbox" / "test.md").exists()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_git_ops.py -v
```

Expected: FAIL (currently uses hardcoded "0-Inbox")

**Step 3: Fix git_ops.py**

Replace `git_ops.py`:

```python
"""Git operations for saving and pushing notes."""
import subprocess
from pathlib import Path
from typing import Dict, Any

import config


def save_and_push_note(
    repo_path: str,
    filename: str,
    content: str,
    push: bool = True
) -> Dict[str, Any]:
    """
    Save note to inbox folder, commit, and optionally push.

    Returns dict with 'success', 'error', and 'file_saved' keys.
    """
    result = {"success": False, "error": None, "file_saved": False, "git_committed": False}

    try:
        inbox_path = Path(repo_path) / config.INBOX_FOLDER
        inbox_path.mkdir(parents=True, exist_ok=True)
        file_path = inbox_path / filename

        # Step 1: Write file
        file_path.write_text(content)
        result["file_saved"] = True

        # Step 2: Git add
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Step 3: Git commit
        commit_msg = f"Telegram capture: {filename.replace(' Telegram Capture.md', '')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        result["git_committed"] = True

        # Step 4: Git push (optional)
        if push and config.GIT_AUTO_PUSH:
            push_result = subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if push_result.returncode != 0:
                result["error"] = f"Push failed: {push_result.stderr}"
                return result

        result["success"] = True
        return result

    except subprocess.CalledProcessError as e:
        result["error"] = f"Git error: {e}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_git_ops.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add git_ops.py tests/test_git_ops.py
git commit -m "fix: use config.INBOX_FOLDER instead of hardcoded path"
```

---

### Task 2.2: Add Message Deduplication

**Files:**
- Modify: `bot.py` (add dedup logic)

**Step 1: Write failing test**

Add to `tests/test_bot.py`:

```python
"""Tests for bot.py - message handling."""
import pytest
import time
from bot import is_duplicate_message, clear_message_hashes


class TestDeduplication:
    """Test message deduplication."""

    def setup_method(self):
        """Clear hashes before each test."""
        clear_message_hashes()

    def test_first_message_not_duplicate(self):
        """First message should not be duplicate."""
        assert is_duplicate_message("hello", 1234567890) is False

    def test_same_message_is_duplicate(self):
        """Same message within window is duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("hello", 1234567890) is True

    def test_different_message_not_duplicate(self):
        """Different message is not duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("world", 1234567891) is False

    def test_same_content_different_time_not_duplicate(self):
        """Same content but different timestamp is not duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("hello", 1234567900) is False
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: FAIL (function doesn't exist)

**Step 3: Add deduplication to bot.py**

After line 35 (`last_error: str | None = None`), add:

```python
# Message deduplication
_message_hashes: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 300  # 5 minutes


def _hash_message(content: str, timestamp: int) -> str:
    """Generate hash for message deduplication."""
    import hashlib
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
```

Add import at top: `import time`

In `handle_message`, after getting content (line 259), add:

```python
    # Check for duplicate
    msg_timestamp = int(message.date.timestamp())
    if is_duplicate_message(content, msg_timestamp):
        logger.info(f"Skipping duplicate message: {content[:50]}...")
        await message.set_reaction([ReactionTypeEmoji("👀")])  # Eyes = already seen
        return
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add message deduplication with 5-minute window"
```

---

### Task 2.3: Improve Error Reactions

**Files:**
- Modify: `bot.py:269-279` (handle_message result handling)

**Step 1: Update reaction logic**

Replace the result handling in `handle_message` (lines 269-279):

```python
    try:
        if result["success"]:
            await message.set_reaction([ReactionTypeEmoji("👍")])  # Full success
            logger.info(f"Successfully saved and pushed: {filename}")
            last_error = None
        elif result["file_saved"] and not result["git_committed"]:
            await message.set_reaction([ReactionTypeEmoji("⚠️")])  # Saved but git failed
            last_error = f"File saved but git failed: {result['error']}"
            logger.warning(last_error)
        elif result["file_saved"]:
            await message.set_reaction([ReactionTypeEmoji("📝")])  # Saved, git issue
            last_error = f"Saved but push failed: {result['error']}"
            logger.warning(last_error)
        else:
            await message.set_reaction([ReactionTypeEmoji("❌")])  # Save failed
            last_error = result["error"]
            logger.error(f"Failed to save: {result['error']}")
    except Exception as e:
        logger.warning(f"Could not set reaction: {e}")
```

**Step 2: Commit**

```bash
git add bot.py
git commit -m "feat: distinct reactions for save/git status"
```

---

## Area 3: Query Optimization for Growing Vault

### Acceptance Criteria
- [ ] AC3.1: System prompt includes vault structure awareness (PARA folders)
- [ ] AC3.2: System prompt prioritizes recent files and key folders
- [ ] AC3.3: Configurable search scope limit (max files to read)

### Task 3.1: Enhanced System Prompt

**Files:**
- Modify: `ask_handler.py:30-44` (SYSTEM_PROMPT)
- Modify: `config.py` (add MAX_FILES_TO_READ)

**Step 1: Update config.py**

Add after line 27:

```python
# Query optimization
MAX_FILES_TO_READ = int(os.getenv("MAX_FILES_TO_READ", "10"))
```

**Step 2: Update SYSTEM_PROMPT**

Replace SYSTEM_PROMPT in `ask_handler.py`:

```python
SYSTEM_PROMPT = """You are answering questions about a personal knowledge vault organized using PARA method.

## Vault Structure (search priority order)
1. **Daily/** - Recent daily notes (check first for current context)
2. **0-Inbox/** - Unprocessed captures (recent additions)
3. **Projects/** - Active time-bound work
4. **Areas/** - Ongoing responsibilities (GenAI-Research, Career-Development, PE-VC-Strategy)
5. **Resources/** - Reference materials (LLM-Technical, PE-Industry)
6. **Archive/** - Completed/outdated (search last)

## Search Strategy
1. Start with Grep for specific keywords across vault
2. Check Daily/ and 0-Inbox/ for recent context
3. Read max 10 most relevant files fully
4. Synthesize across sources, cite file paths

## Rules
- ONLY use information found in vault files - never hallucinate
- If you can't find relevant info, say "I couldn't find that in your vault"
- Reference which files you found information in (format: `filename.md`)
- Keep answers concise (under 400 words for Telegram)
- User interests: GenAI, PE/VC, career development, knowledge management

## Key Files to Check
- QUICKFACTS.md - Current priorities and status
- VAULT-INDEX.md - Navigation overview
- *-Hub.md files - Topic collections
"""
```

**Step 3: Commit**

```bash
git add ask_handler.py config.py
git commit -m "feat: enhanced system prompt with PARA awareness"
```

---

## Area 4: Observability & Debugging

### Acceptance Criteria
- [ ] AC4.1: Structured JSON logging for all events
- [ ] AC4.2: PII scrubbed from logs (content truncated)
- [ ] AC4.3: /stats command shows queries/day, captures/day, costs
- [ ] AC4.4: Debug mode configurable via environment

### Task 4.1: Create Structured Logger

**Files:**
- Create: `logger.py`

**Step 1: Create logger.py**

```python
"""Structured logging for Telegram Brain Claude."""
import json
import logging
from datetime import datetime
from typing import Any, Optional

# Configure base logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("telegram-brain")


def _scrub_pii(data: dict, max_content_len: int = 100) -> dict:
    """Remove or truncate PII from log data."""
    scrubbed = data.copy()

    # Truncate content fields
    for field in ["content", "message", "answer", "question"]:
        if field in scrubbed and isinstance(scrubbed[field], str):
            if len(scrubbed[field]) > max_content_len:
                scrubbed[field] = scrubbed[field][:max_content_len] + "..."

    # Remove sensitive fields
    for field in ["api_key", "token", "password", "secret"]:
        if field in scrubbed:
            scrubbed[field] = "[REDACTED]"

    return scrubbed


def log_event(
    event_type: str,
    data: Optional[dict] = None,
    level: str = "info"
) -> None:
    """Log structured event as JSON."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event_type,
    }

    if data:
        entry.update(_scrub_pii(data))

    json_str = json.dumps(entry)

    if level == "error":
        logger.error(json_str)
    elif level == "warning":
        logger.warning(json_str)
    elif level == "debug":
        logger.debug(json_str)
    else:
        logger.info(json_str)


def log_capture(chars: int, has_forward: bool, filename: str) -> None:
    """Log capture event."""
    log_event("capture", {
        "chars": chars,
        "has_forward": has_forward,
        "filename": filename,
    })


def log_query(
    model: str,
    question: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    cached: bool = False,
) -> None:
    """Log query event."""
    log_event("query", {
        "model": model,
        "question": question,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "cached": cached,
    })


def log_git_op(action: str, success: bool, error: Optional[str] = None) -> None:
    """Log git operation."""
    log_event("git_op", {
        "action": action,
        "success": success,
        "error": error,
    }, level="error" if error else "info")


def log_rate_limit(user_id: int, reason: str) -> None:
    """Log rate limit event."""
    log_event("rate_limit", {
        "user_id": user_id,
        "reason": reason,
    }, level="warning")
```

**Step 2: Write tests**

Create `tests/test_logger.py`:

```python
"""Tests for logger.py - structured logging."""
import pytest
import json
from logger import _scrub_pii, log_event


class TestPIIScrubbing:
    """Test PII scrubbing."""

    def test_truncates_long_content(self):
        """Long content should be truncated."""
        data = {"content": "a" * 200}
        scrubbed = _scrub_pii(data, max_content_len=100)
        assert len(scrubbed["content"]) == 103  # 100 + "..."
        assert scrubbed["content"].endswith("...")

    def test_redacts_sensitive_fields(self):
        """Sensitive fields should be redacted."""
        data = {"api_key": "sk-1234", "token": "abc"}
        scrubbed = _scrub_pii(data)
        assert scrubbed["api_key"] == "[REDACTED]"
        assert scrubbed["token"] == "[REDACTED]"

    def test_preserves_short_content(self):
        """Short content should not be modified."""
        data = {"content": "short text"}
        scrubbed = _scrub_pii(data)
        assert scrubbed["content"] == "short text"
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_logger.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add logger.py tests/test_logger.py
git commit -m "feat: add structured JSON logging with PII scrubbing"
```

---

### Task 4.2: Integrate Logger into Bot

**Files:**
- Modify: `bot.py` (replace logging calls)
- Modify: `ask_handler.py` (add query logging)

**Step 1: Update imports in bot.py**

Replace:
```python
logger = logging.getLogger(__name__)
```

With:
```python
from logger import log_capture, log_git_op, log_rate_limit, logger
```

**Step 2: Update handle_message to use structured logging**

After saving note, replace logging calls:

```python
    log_capture(
        chars=len(content),
        has_forward=forward_from is not None,
        filename=filename,
    )
```

**Step 3: Update ask_handler.py**

Add import:
```python
from logger import log_query
```

After getting result in `ask_vault`, add:
```python
    log_query(
        model=model_used,
        question=question,
        tokens_in=usage_info.get("input_tokens", 0),
        tokens_out=usage_info.get("output_tokens", 0),
        cost_usd=total_cost,
    )
```

**Step 4: Commit**

```bash
git add bot.py ask_handler.py
git commit -m "feat: integrate structured logging throughout bot"
```

---

## Area 5: Dependency Resilience

### Acceptance Criteria
- [ ] AC5.1: All dependencies pinned to exact versions
- [ ] AC5.2: /health command checks vault, git, and Claude API status
- [ ] AC5.3: Retry logic for transient API failures (3 attempts with exponential backoff)

### Task 5.1: Pin Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Update requirements.txt**

```
python-telegram-bot==20.7
python-dotenv==1.0.1
claude-agent-sdk==0.1.19
tenacity==8.2.3
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: pin all dependencies to exact versions"
```

---

### Task 5.2: Add Health Check Command

**Files:**
- Modify: `bot.py` (add /health handler)

**Step 1: Create health check function**

Add to `bot.py`:

```python
async def check_health() -> dict[str, bool]:
    """Check health of all system components."""
    health = {
        "vault": False,
        "git": False,
        "claude_api": False,
    }

    # Check vault exists
    health["vault"] = config.VAULT_PATH.exists()

    # Check git status
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(config.VAULT_PATH),
            capture_output=True,
            timeout=5
        )
        health["git"] = result.returncode == 0
    except Exception:
        pass

    # Check Claude API (lightweight)
    try:
        import os
        health["claude_api"] = bool(os.getenv("ANTHROPIC_API_KEY"))
    except Exception:
        pass

    return health


async def handle_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health command."""
    message = update.message
    if not message or not message.from_user:
        return

    if message.from_user.id != config.TELEGRAM_USER_ID:
        return

    health = await check_health()

    status_emoji = "✅" if all(health.values()) else "⚠️"
    lines = [f"{status_emoji} *System Health*", ""]

    for component, ok in health.items():
        emoji = "✅" if ok else "❌"
        lines.append(f"{emoji} {component}")

    await message.reply_text("\n".join(lines), parse_mode="Markdown")
```

Add subprocess import at top if not present:
```python
import subprocess
```

Add handler in `main()`:
```python
    app.add_handler(CommandHandler("health", handle_health))
```

**Step 2: Commit**

```bash
git add bot.py
git commit -m "feat: add /health command for system status"
```

---

### Task 5.3: Add Retry Logic to Ask Handler

**Files:**
- Modify: `ask_handler.py`

**Step 1: Update ask_handler.py with retry logic**

Add import:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
```

Wrap the query logic:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
async def _execute_query(client, question: str) -> tuple[list, float, str, dict]:
    """Execute query with retry logic."""
    answer_parts = []
    total_cost = 0.0
    model_used = "unknown"
    usage_info = {}

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

    return answer_parts, total_cost, model_used, usage_info
```

Update `ask_vault` to use the new function.

**Step 2: Commit**

```bash
git add ask_handler.py
git commit -m "feat: add retry logic for transient API failures"
```

---

## Final Integration Test

### Task 6.1: Manual Integration Test Checklist

**Checklist:**
- [ ] Start bot: `python bot.py`
- [ ] Send message → gets 👍 reaction, shows in inbox
- [ ] Send duplicate immediately → gets 👀 reaction, not saved
- [ ] Send `/ask test query` → gets answer with cost
- [ ] Send `/ask test query` again immediately → rate limited message
- [ ] Wait 30s, send `/ask test query` → gets cached result
- [ ] Send `/status` → shows captures, budget
- [ ] Send `/health` → shows all green
- [ ] Check logs for structured JSON output

---

## Summary

| Area | Tasks | Tests | Priority |
|------|-------|-------|----------|
| Cost Control | 3 | 12 | 1 |
| Data Integrity | 3 | 5 | 2 |
| Query Optimization | 1 | 0 | 3 |
| Observability | 2 | 3 | 4 |
| Dependency Resilience | 3 | 0 | 5 |

**Total: 12 tasks, 20 tests**

---

Plan complete and saved to `docs/plans/2026-01-14-reliability-improvements.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
