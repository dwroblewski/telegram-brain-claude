# GitHub Sync Setup

Complete setup for bidirectional sync between your vault and the Telegram bot.

## Overview

Two workflows are needed in your vault repo:

| Workflow | Direction | Trigger |
|----------|-----------|---------|
| `sync-vault.yml` | Vault → R2 | Push to main |
| `sync-capture.yml` | R2 → Vault | Worker sends repository_dispatch |

## Step 1: Create R2 API Token

1. Go to: Cloudflare Dashboard → R2 → Manage R2 API Tokens
2. Create token:
   - **Name**: `github-actions-sync`
   - **Permissions**: Admin Read & Write (not Object Read/Write - has known 403 bug)
   - **Bucket scope**: Your bucket only
3. Save the Access Key ID and Secret Access Key

## Step 2: Add Secrets to Your Vault Repo

Go to: GitHub → Your vault repo → Settings → Secrets → Actions

Add these secrets:

| Secret | Value |
|--------|-------|
| `R2_ACCESS_KEY_ID` | Access Key ID from Step 1 |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key from Step 1 |
| `R2_ACCOUNT_ID` | Your Cloudflare Account ID |
| `TELEGRAM_BOT_TOKEN` | (Optional) For failure notifications |
| `TELEGRAM_CHAT_ID` | (Optional) Your Telegram user ID |

## Step 3: Add Workflows to Your Vault Repo

Copy the workflow files to your vault repo:

```bash
# From your vault repo root
mkdir -p .github/workflows

# Copy from telegram-brain-claude
cp /path/to/telegram-brain-claude/scripts/workflows/sync-vault.yml .github/workflows/
cp /path/to/telegram-brain-claude/scripts/workflows/sync-capture.yml .github/workflows/

git add .github/workflows/
git commit -m "feat: Add telegram-brain sync workflows"
git push
```

## Step 4: Create GitHub Token for Worker

1. Go to: https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Configure:
   - **Name**: `telegram-brain-worker`
   - **Expiration**: 90 days (or custom)
   - **Repository access**: Only select repositories → Your vault repo
   - **Permissions**:
     - **Contents**: Read and write (required for repository_dispatch)
4. Copy the token

## Step 5: Add Token to Cloudflare Worker

```bash
cd worker
npx wrangler secret put GITHUB_TOKEN    # Paste token
npx wrangler secret put GITHUB_REPO     # e.g., "yourusername/your-vault"
```

## Step 6: Test

**Test vault → R2:**
```bash
# Make a small change to your vault
echo "<!-- test -->" >> QUICKFACTS.md
git add QUICKFACTS.md && git commit -m "test: trigger sync" && git push

# Check GitHub Actions - "Sync Vault to R2" should run
# Check worker health - vault size should update
curl https://your-worker.workers.dev/health
```

**Test capture → git:**
1. Send any message to your Telegram bot
2. Bot should react with 👍
3. Check GitHub Actions - "Sync Telegram Capture" should run
4. File should appear in `0-Inbox/telegram-*.md`

## Troubleshooting

**Vault sync fails with 403?**
- Use "Admin Read & Write" permission, not "Object Read/Write"
- See: https://github.com/cloudflare/workers-sdk/issues/9235

**Capture sync not triggering?**
- Check worker has GITHUB_TOKEN and GITHUB_REPO secrets
- Verify token has "Contents: Read and write" permission
- Note: "Actions: Read and write" alone won't work

**Capture sync fails on R2 download?**
- Verify R2 secrets in GitHub (R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID)
- Check bucket name matches in workflow file

**Filename validation fails?**
- Worker generates `telegram-YYYY-MM-DDTHH-MM-SS-MSSZ.md` format
- If you modified the worker, update regex in sync-capture.yml
