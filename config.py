"""
Configuration for Telegram Brain Claude bot.

All settings loaded from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Required
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Vault settings
VAULT_PATH = Path(os.getenv("VAULT_PATH", "."))
INBOX_FOLDER = os.getenv("INBOX_FOLDER", "0-Inbox")

# Model settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "sonnet")
QUICK_MODEL = os.getenv("QUICK_MODEL", "haiku")
MAX_BUDGET_SONNET = float(os.getenv("MAX_BUDGET_SONNET", "0.15"))
MAX_BUDGET_HAIKU = float(os.getenv("MAX_BUDGET_HAIKU", "0.02"))
MAX_TURNS_SONNET = int(os.getenv("MAX_TURNS_SONNET", "10"))
MAX_TURNS_HAIKU = int(os.getenv("MAX_TURNS_HAIKU", "5"))

# Git settings
GIT_ENABLED = os.getenv("GIT_ENABLED", "true").lower() == "true"
GIT_AUTO_PUSH = os.getenv("GIT_AUTO_PUSH", "true").lower() == "true"


def validate_config():
    """Validate required configuration is present."""
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set")
    if TELEGRAM_USER_ID == 0:
        errors.append("TELEGRAM_USER_ID not set")
    if not VAULT_PATH.exists():
        errors.append(f"VAULT_PATH does not exist: {VAULT_PATH}")

    # ANTHROPIC_API_KEY only required if using /ask features
    # Claude Agent SDK will handle its own auth

    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))


if __name__ == "__main__":
    # Test configuration
    validate_config()
    print("Configuration valid!")
    print(f"  Vault: {VAULT_PATH}")
    print(f"  Inbox: {INBOX_FOLDER}")
    print(f"  Git enabled: {GIT_ENABLED}")
