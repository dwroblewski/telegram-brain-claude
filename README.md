# Telegram Brain Claude

A personal Telegram bot that captures notes and queries them using Claude AI.

## What This Does

**The problem:** You have ideas, links, and notes throughout the day, but getting them into your note-taking system is friction. And once they're there, finding them again is hard.

**The solution:** A Telegram bot that:
1. **Captures** anything you send → saves as a markdown file
2. **Queries** your notes with AI → Claude searches and answers questions

Send a message from your phone, it lands in your notes. Ask "what did I save about X?", get an answer with sources.

## What You Need

### Your Notes (Markdown Files)

This bot works with any folder of markdown files. It's designed for "second brain" style note systems like:

- [Obsidian](https://obsidian.md) - Popular markdown-based note app
- [Logseq](https://logseq.com) - Outline-based notes
- Any folder of `.md` files

The bot reads and writes plain markdown - no proprietary formats.

### Accounts & Keys

- **Telegram account** - Where you'll interact with the bot
- **Anthropic API key** - For Claude AI queries ([get one here](https://console.anthropic.com))

### Technical

- Python 3.10+
- A computer that stays on (your machine, a server, Raspberry Pi, etc.)

**No public IP or server required.** The bot uses long-polling, so it works behind NAT, firewalls, or on your home network. Just needs outbound internet access.

## Installation

```bash
# Clone
git clone https://github.com/dwroblewski/telegram-brain-claude.git
cd telegram-brain-claude

# Setup Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your values (see Configuration below)
```

## Configuration

Edit your `.env` file:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_USER_ID=your_telegram_user_id
VAULT_PATH=/path/to/your/notes/folder

# Optional
INBOX_FOLDER=inbox                # Subfolder where captures land (created if missing)
DEFAULT_MODEL=sonnet              # AI model for /ask command
QUICK_MODEL=haiku                 # AI model for /quick command
MAX_BUDGET_SONNET=0.15           # Max $ per thorough query
MAX_BUDGET_HAIKU=0.02            # Max $ per quick query
GIT_ENABLED=true                  # Auto-commit captures to git
GIT_AUTO_PUSH=true                # Push after commit
```

### Getting Your Telegram Credentials

**Bot Token:**
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy the token to `TELEGRAM_BOT_TOKEN`

**Your User ID:**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy the number to `TELEGRAM_USER_ID`

The user ID ensures only you can use the bot.

## Usage

```bash
# Start the bot
python bot.py
```

Then open Telegram and message your bot.

### Capturing Notes

Just send any message:
- Text thoughts or ideas
- Forward articles or links
- Photos with captions

Each message becomes a timestamped markdown file in your inbox folder.

### Querying Your Notes

| Command | Shortcut | Description |
|---------|----------|-------------|
| `/ask <question>` | `/a` | Thorough search (Sonnet, ~$0.02-0.10) |
| `/quick <question>` | `/q` | Fast lookup (Haiku, ~$0.002-0.01) |
| `/status` | - | Show capture stats |
| `/help` | - | Show commands |

**Examples:**
```
/ask what are my notes about project management?
/q summarize yesterday's captures
/a find everything related to the Smith meeting
```

Claude searches your files using grep and file reading, then synthesizes an answer with references to specific notes.

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Telegram   │────▶│   Bot       │────▶│  Your Notes │
│  (phone)    │◀────│  (Python)   │◀────│  (markdown) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Claude AI  │
                    │  (queries)  │
                    └─────────────┘
```

- **Capture flow:** Telegram message → bot formats as markdown → saves to inbox folder → (optional) git commit & push
- **Query flow:** Your question → Claude Agent SDK → Claude searches your files → returns answer with sources

## Security

- **Single user only** - Only your Telegram user ID can interact
- **Read-only AI** - Claude can search and read files, but cannot write, edit, or delete
- **Blocked paths** - AI cannot access `.env`, credentials, or `.git/` folders
- **Budget limits** - Per-query spending caps prevent runaway API costs

## Running 24/7

To keep the bot running, use systemd (Linux):

```bash
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

Or use `screen`, `tmux`, or Docker.

## Customization

**Note format:** Edit `note_formatter.py` to change how captures are formatted.

**AI behavior:** Edit `ask_handler.py` to modify the system prompt or allowed operations.

**File patterns:** The bot saves to `{INBOX_FOLDER}/{timestamp} Telegram Capture.md` by default.

## License

MIT License - see [LICENSE](LICENSE)

## Built With

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram API
- [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk) - AI integration
