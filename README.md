# Telegram Brain Claude

A personal Telegram bot that captures messages to your Obsidian vault and queries it using Claude AI.

**Two core functions:**
1. **Capture** - Send any message → saved as markdown note in your vault inbox
2. **Query** - Ask questions about your vault → Claude searches and answers

## Features

- **Instant capture**: Forward articles, jot down ideas, save links - all via Telegram
- **AI-powered search**: Query your entire vault with natural language
- **Dual model support**: Thorough search (Sonnet) or quick lookup (Haiku)
- **Git integration**: Auto-commit and push captures to your vault repo
- **Security**: Single-user only, read-only vault queries, no sensitive file access

## Prerequisites

- Python 3.10+
- Telegram account
- Obsidian vault (local or git-synced)
- Anthropic API key (for `/ask` features)

**No public IP or server required.** The bot uses long-polling (not webhooks), so it works on:
- Your local machine
- Home server behind NAT
- Any VM or VPS
- Raspberry Pi

Just needs outbound internet access to reach Telegram and Anthropic APIs.

## Installation

```bash
# Clone
git clone https://github.com/dwroblewski/telegram-brain-claude.git
cd telegram-brain-claude

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your values
```

## Configuration

Create a `.env` file:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_USER_ID=your_telegram_user_id
VAULT_PATH=/path/to/your/obsidian/vault

# Optional
INBOX_FOLDER=0-Inbox              # Where captures land
DEFAULT_MODEL=sonnet              # For /ask command
QUICK_MODEL=haiku                 # For /quick command
MAX_BUDGET_SONNET=0.15           # Max $ per query
MAX_BUDGET_HAIKU=0.02
GIT_ENABLED=true                  # Auto-commit captures
GIT_AUTO_PUSH=true                # Push after commit
```

### Getting Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID

### Creating a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow prompts
3. Copy the token to your `.env`

## Usage

```bash
# Start the bot
python bot.py
```

### Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `/ask <question>` | `/a` | Query vault with Sonnet (thorough) |
| `/quick <question>` | `/q` | Query vault with Haiku (fast) |
| `/status` | - | Show capture stats and recent activity |
| `/help` | - | Show available commands |

### Capturing

Just send any message to the bot:
- Text notes
- Forwarded messages (source preserved)
- Links with comments
- Photos with captions

Each capture creates a timestamped markdown file in your inbox folder.

### Querying

```
/ask what are my notes about RAG?
/q summarize my recent meeting notes
/a what projects am I working on?
```

The bot searches your vault using Claude's built-in tools (Grep, Glob, Read) and synthesizes an answer with file references.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Telegram   │────▶│   bot.py    │────▶│  Obsidian   │
│   Client    │◀────│             │◀────│    Vault    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Claude Agent│
                    │     SDK     │
                    └─────────────┘
```

**Key components:**
- `bot.py` - Telegram handlers for capture and commands
- `ask_handler.py` - Claude Agent SDK integration with read-only enforcement
- `config.py` - Centralized configuration
- `git_ops.py` - Auto-commit and push for captures
- `note_formatter.py` - Markdown note generation

## Security

- **Single user**: Only your Telegram user ID can interact
- **Read-only queries**: Claude can only read files (Grep, Glob, Read)
- **Blocked patterns**: No access to `.env`, credentials, `.git/`
- **Budget limits**: Per-query spending caps prevent runaway costs

## Customization

### Changing the Note Format

Edit `note_formatter.py` to customize the capture template:

```python
def format_note(content: str, timestamp: datetime, forward_from: str = None) -> str:
    # Your template here
```

### Adjusting Query Behavior

Edit `ask_handler.py`:
- `SYSTEM_PROMPT` - Instructions for Claude
- `READ_ONLY_TOOLS` - Allowed tool whitelist
- `BLOCKED_PATTERNS` - Sensitive file patterns

## Running as a Service

```bash
# systemd service file
sudo cat > /etc/systemd/system/telegram-brain.service << EOF
[Unit]
Description=Telegram Brain Claude Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/telegram-brain-claude
ExecStart=/path/to/telegram-brain-claude/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable telegram-brain
sudo systemctl start telegram-brain
```

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python)
