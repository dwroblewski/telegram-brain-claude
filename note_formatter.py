"""Format captured messages as markdown notes."""
from datetime import datetime
from typing import Optional


def generate_filename(dt: datetime) -> str:
    """Generate timestamped filename: YYYY-MM-DD-HHMMSS Telegram Capture.md"""
    return dt.strftime("%Y-%m-%d-%H%M%S") + " Telegram Capture.md"


def format_note(
    content: str,
    dt: datetime,
    forward_from: Optional[str] = None
) -> str:
    """Format message content as markdown note."""
    lines = [
        "#inbox #telegram-capture",
        "",
        f"**Captured**: {dt.strftime('%Y-%m-%d %H:%M:%S')}",
        "**Source**: Telegram",
    ]

    if forward_from:
        lines.append(f"**Forwarded from**: {forward_from}")

    lines.extend([
        "",
        "---",
        "",
        content
    ])

    return "\n".join(lines)
