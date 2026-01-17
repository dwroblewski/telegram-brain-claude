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
                            │                        ↑↓
                            ▼                  ┌─────────────┐
                     ┌─────────────┐           │ GitHub Repo │
                     │  Gemini AI  │           │ (your vault)│
                     │  (queries)  │           └─────────────┘
                     └─────────────┘
```

R2 ↔ GitHub sync is bidirectional:
- **Capture → Git**: Worker triggers Action to commit new captures
- **Vault → R2**: Push to main triggers Action to update query context

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

## Bidirectional Sync

Two GitHub Actions keep your vault and R2 in sync:

**Capture → Git** (when you message the bot):
1. Message saved to R2 (instant)
2. Worker triggers repository_dispatch
3. `sync-capture.yml` pulls from R2 and commits
4. ~3 seconds end-to-end

**Vault → R2** (when you edit your vault):
1. Push changes to your vault repo
2. `sync-vault.yml` aggregates markdown files
3. Uploads `_vault_context.md` to R2
4. Next `/ask` query uses updated content

Setup: See `scripts/setup-github-sync.md` for both workflows.

## Setup

### Prerequisites

- Cloudflare account with R2 enabled
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Gemini API key (from [AI Studio](https://aistudio.google.com/app/apikey))
- Your Telegram user ID (from [@userinfobot](https://t.me/userinfobot))
- GitHub repository for your vault (for bidirectional sync)

### Configuration

```bash
cp .env.example .env
# Edit .env with your values
```

### Deploy

```bash
# Set secrets (required)
cd worker
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ALLOWED_USER_ID

# Set secrets (for GitHub auto-sync)
npx wrangler secret put GITHUB_TOKEN    # Fine-grained token with Contents:write
npx wrangler secret put GITHUB_REPO     # e.g., "username/vault-repo"

# Initial vault sync to R2 (one-time, before GitHub Action is set up)
./scripts/sync-vault.sh

# Deploy worker
./scripts/deploy.sh
```

### Set Telegram Webhook

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>/webhook"
```

### GitHub Bidirectional Sync

Two workflows keep R2 and your vault repo in sync. Both are required for full functionality.

**Step 1: Create R2 API token** (for vault → R2)
- Cloudflare Dashboard → R2 → Manage R2 API Tokens
- Permission: **Admin Read & Write** (not Object Read/Write)
- Add to your vault repo's GitHub secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`

**Step 2: Create GitHub token** (for capture → git)
- GitHub → Settings → Developer settings → Fine-grained tokens
- Permission: **Contents: Read and write** (not Actions)
- Add to Cloudflare Worker secrets:
  ```bash
  cd worker
  npx wrangler secret put GITHUB_TOKEN
  npx wrangler secret put GITHUB_REPO     # e.g., "username/vault-repo"
  ```

**Step 3: Add workflows to your vault repo**
```bash
mkdir -p .github/workflows
cp scripts/workflows/sync-vault.yml .github/workflows/
cp scripts/workflows/sync-capture.yml .github/workflows/
git add .github/workflows && git commit -m "Add telegram-brain sync" && git push
```

See `scripts/setup-github-sync.md` for detailed setup and troubleshooting.

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
worker/              # Cloudflare Worker (main bot)
scripts/             # Sync and deploy scripts
scripts/workflows/   # GitHub Action workflows for your vault repo
tests/               # Unit tests (run: node tests/worker.test.js)
docs/                # Architecture validation and decisions
```

## Troubleshooting

### Sync fails with 403 error

R2 API tokens with "Object Read/Write" permission can fail with 403. Use "Admin Read & Write" instead.

```bash
# Cloudflare Dashboard → R2 → Manage R2 API Tokens
# Create new token with: Admin Read & Write (not Object Read/Write)
```

### GitHub auto-sync not triggering

Fine-grained GitHub tokens with "Actions: Read and write" cannot trigger repository_dispatch. You need "Contents: Read and write".

```bash
# GitHub → Settings → Developer settings → Fine-grained tokens
# Required: Contents: Read and write
```

### Query times out

Queries over 25s will timeout. This usually means the vault context is too large or Gemini is slow.

1. Check vault size: `wc -c /tmp/vault_context.md` (should be <500KB)
2. Reduce `VAULT_DEPTH` in `.env` (default: 3)
3. Try again - Gemini has occasional slow responses

### Bot not responding

1. Check webhook is set: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
2. Check worker health: `curl <WORKER_URL>/health`
3. Check logs: `cd worker && npx wrangler tail`

### Vault not updating after sync

Sync pushes to R2, but bot might have cached old content. Queries always fetch fresh from R2, so just wait or re-query.

## Security

- Single user only (ALLOWED_USER_ID)
- Secrets stored in Cloudflare (not in code)
- R2 bucket is private
- No vault content in git

## Legacy

Previous Python implementation preserved in `legacy-python` branch.

## License

MIT
