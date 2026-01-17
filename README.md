# Telegram Brain

A serverless Telegram bot that captures notes and queries your second brain using AI.

## Who This Is For

You'll need comfort with:
- Command line (npm, wrangler CLI)
- Cloudflare account setup
- GitHub Actions
- Environment variables and API keys

If that sounds intimidating, check out simpler approaches like Google Forms + Apps Script or local Python scripts.

## Cost

- **Capture:** Free (Cloudflare Worker free tier, GitHub Actions free tier, R2 free tier)
- **Query:** A couple bucks per month in Gemini API costs, depending on usage

No database, no always-on compute, no subscription fees.

## How I Actually Use It

This bot handles ad-hoc capture. The heavy lifting happens in Claude Code sessions where I:
- Process the inbox and file notes into the right folders
- Create links between related notes
- Generate digests and summaries
- Do research with the vault as context

The bot solves mobile capture. Claude Code solves everything else. They work together.

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

**Why no database?** The entire vault fits in Gemini's context window (~500KB). On each query, the bot loads everything and lets the model search. Gemini's implicit caching means repeated queries are cheap and fast. No embeddings, no vector store, no sync logic.

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
