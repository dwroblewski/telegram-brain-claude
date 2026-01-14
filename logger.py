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
