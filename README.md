# Telegram Brain

A serverless Telegram bot that captures notes and queries your second brain using AI.

## Architecture

```
┌─────────────┐     ┌────────────────────┐     ┌─────────────┐
│  Telegram   │────▶│  Cloudflare Worker │────▶│  R2 Storage │
│  (phone)    │◀────│  (edge, serverless)│◀────│  (vault)    │
└─────────────┘     └────────────────────┘     └─────────────┘
                            │                        │
                            ▼                        ▼
                     ┌─────────────┐          ┌─────────────┐
                     │  Gemini AI  │          │ GitHub Sync │
                     │  (queries)  │          │ (auto-commit)│
                     └─────────────┘          └─────────────┘
```

**Why serverless?** No VM to maintain, no systemd services, auto-scaling, runs at the edge.

## Commands

| Command | Description |
|---------|-------------|
| `/ask <query>` | Query your vault with AI |
| `/recent` | Show last 5 captures |
| `/stats` | Vault statistics |
| `/health` | Check bot status |
| `/help` | List commands |
| `<any text>` | Capture to inbox |

## Auto-Sync

Captures automatically commit to your vault repo:
1. Message saved to R2 (instant)
2. GitHub Action triggered via repository_dispatch
3. Action pulls from R2 and commits
4. ~3 seconds end-to-end

Setup: See `scripts/setup-github-sync.md`

## Setup

### Prerequisites

- Cloudflare account with R2 enabled
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Gemini API key
- Your Telegram user ID (from [@userinfobot](https://t.me/userinfobot))

### Configuration

```bash
cp .env.example .env
# Edit .env with your values
```

### Deploy

```bash
# Set secrets
cd worker
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ALLOWED_USER_ID

# Sync vault to R2
./scripts/sync-vault.sh

# Deploy worker
./scripts/deploy.sh
```

### Set Telegram Webhook

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>/webhook"
```

## Development

```bash
# Local development
cd worker
npx wrangler dev

# View logs
npx wrangler tail
```

## Files

```
worker/           # Cloudflare Worker (main bot)
scripts/          # Sync and deploy scripts
phase0-tests/     # Model selection and validation tests
cf-worker-test/   # Isolated API testing
```

## Security

- Single user only (ALLOWED_USER_ID)
- Secrets stored in Cloudflare (not in code)
- R2 bucket is private
- No vault content in git

## Legacy

Previous Python implementation preserved in `legacy-python` branch.

## License

MIT
