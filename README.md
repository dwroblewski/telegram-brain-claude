# Telegram Brain

A serverless Telegram bot that captures notes and queries your second brain using AI.

## Cost

- **Capture:** Free within free tiers (Cloudflare Workers, GitHub Actions, R2) — plenty for personal use
- **Query:** A couple bucks per month in Gemini API costs, depending on usage

No database, no always-on compute, no subscription fees.

## Quick Start

For experienced users who know Cloudflare Workers and GitHub Actions:

```bash
# 1. Clone and configure
git clone https://github.com/yourusername/telegram-brain-claude
cd telegram-brain-claude && cp .env.example .env

# 2. Set Cloudflare secrets
cd worker
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ALLOWED_USER_ID
npx wrangler secret put GITHUB_TOKEN      # Fine-grained, Contents:write
npx wrangler secret put GITHUB_REPO       # "username/vault-repo"

# 3. Copy workflows to your vault repo, add R2 secrets to GitHub

# 4. Deploy and set webhook
./scripts/sync-vault.sh && ./scripts/deploy.sh
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>/webhook"
```

Details below. Troubleshooting at the end.

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

**R2 ↔ GitHub is bidirectional:**
- **Capture → Git**: You message the bot → saved to R2 → Worker triggers GitHub Action → committed to your vault
- **Vault → R2**: You push to your vault repo → GitHub Action aggregates markdown → uploads to R2 → next query uses updated content

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

## Setup

### Prerequisites

- Cloudflare account with R2 enabled
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Gemini API key (from [AI Studio](https://aistudio.google.com/app/apikey))
- Your Telegram user ID (from [@userinfobot](https://t.me/userinfobot))
- GitHub repository for your vault

### Step 1: Configure

```bash
cp .env.example .env
# Edit .env with your values
```

### Step 2: Set Cloudflare Worker Secrets

```bash
cd worker
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ALLOWED_USER_ID
npx wrangler secret put GITHUB_TOKEN      # See Step 3
npx wrangler secret put GITHUB_REPO       # e.g., "username/vault-repo"
```

### Step 3: Set Up GitHub Sync

Two workflows keep your vault and R2 in sync. Both required.

**3a. Create R2 API token** (for vault → R2 sync)
1. Cloudflare Dashboard → R2 → Manage R2 API Tokens
2. Create token with **Admin Read & Write** permission (not Object Read/Write — known bug)
3. Add these secrets to your **vault repo** (GitHub → Settings → Secrets → Actions):
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_ACCOUNT_ID`

**3b. Create GitHub token** (for capture → git sync)
1. GitHub → Settings → Developer settings → Fine-grained tokens
2. Create token with **Contents: Read and write** permission (not Actions — won't work)
3. This is the `GITHUB_TOKEN` you set in Step 2

**3c. Add workflows to your vault repo**
```bash
# From your vault repo
mkdir -p .github/workflows
cp /path/to/telegram-brain-claude/scripts/workflows/sync-vault.yml .github/workflows/
cp /path/to/telegram-brain-claude/scripts/workflows/sync-capture.yml .github/workflows/
git add .github/workflows && git commit -m "Add telegram-brain sync" && git push
```

See `scripts/setup-github-sync.md` for detailed walkthrough.

### Step 4: Deploy

```bash
# Initial vault sync (one-time, seeds R2 before GitHub Action exists)
./scripts/sync-vault.sh

# Deploy the worker
./scripts/deploy.sh
```

### Step 5: Set Telegram Webhook

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
worker/              # Cloudflare Worker (main bot logic)
scripts/             # Sync and deploy scripts
scripts/workflows/   # GitHub Action workflows (copy to your vault repo)
tests/               # Unit tests (run: node tests/worker.test.js)
docs/                # Architecture decisions
```

## Troubleshooting

### Sync fails with 403 error

R2 API tokens with "Object Read/Write" permission fail with 403. Use "Admin Read & Write" instead.

```
Cloudflare Dashboard → R2 → Manage R2 API Tokens
Create new token with: Admin Read & Write
```

### GitHub auto-sync not triggering

Fine-grained tokens with "Actions: Read and write" cannot trigger repository_dispatch. You need "Contents: Read and write".

```
GitHub → Settings → Developer settings → Fine-grained tokens
Required permission: Contents: Read and write
```

### Query times out

Queries over 25s timeout. Usually means vault is too large or Gemini is slow.

1. Check vault size: `wc -c /tmp/vault_context.md` (should be <500KB)
2. Reduce `VAULT_DEPTH` in `.env` (default: 3)
3. Try again — Gemini has occasional slow responses

### Bot not responding

1. Check webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
2. Check health: `curl <WORKER_URL>/health`
3. Check logs: `cd worker && npx wrangler tail`

### Vault not updating after sync

Queries always fetch fresh from R2. If vault seems stale, the GitHub Action may not have run — check Actions tab in your vault repo.

## Security

- Single user only (`ALLOWED_USER_ID`)
- Webhook signature validation (`WEBHOOK_SECRET`)
- Prompt injection filtering on queries
- Secrets stored in Cloudflare (not in code)
- R2 bucket is private

## How I Actually Use It

This bot handles ad-hoc capture. The heavy lifting happens in Claude Code sessions where I:
- Process the inbox and file notes into the right folders
- Create links between related notes
- Generate digests and summaries
- Do research with the vault as context

The bot solves mobile capture. Claude Code solves everything else. They work together.

## Legacy

Previous Python implementation preserved in `legacy-python` branch.

## License

MIT
