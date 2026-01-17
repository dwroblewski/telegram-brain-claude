# GitHub Sync Setup

One-time setup to enable automatic capture sync from R2 to GitHub.

## Step 1: Create Fine-Grained GitHub Token

1. Go to: https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Configure:
   - **Name**: `telegram-brain-capture-sync`
   - **Expiration**: 90 days (or longer)
   - **Repository access**: Only select repositories → `dwroblewski/second-brain`
   - **Permissions**:
     - **Contents**: No access (we don't write directly)
     - **Actions**: Read and write (to trigger workflows)
4. Generate and copy token

## Step 2: Add Token to Cloudflare Worker

```bash
cd ~/projects/telegram-brain-claude/worker
npx wrangler secret put GITHUB_TOKEN
# Paste the token when prompted
```

## Step 3: Deploy Worker

```bash
cd ~/projects/telegram-brain-claude
./scripts/deploy.sh
```

## Step 4: Push GitHub Action to second-brain

```bash
cd ~/projects/second-brain
git add .github/workflows/sync-capture.yml
git commit -m "feat: Add telegram capture sync workflow"
git push
```

## Step 5: Test

Send a message to your Telegram bot. Check:
1. Bot reacts with 👍 (R2 save succeeded)
2. GitHub Actions shows "Sync Telegram Capture" run
3. File appears in `0-Inbox/telegram-*.md`

## Troubleshooting

**Action not triggering?**
- Check worker logs: `cd worker && npx wrangler tail`
- Verify GITHUB_TOKEN is set: `npx wrangler secret list`

**Action fails on R2 download?**
- Verify R2 secrets exist in GitHub: Settings → Secrets → Actions
- Required: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`

**Filename validation fails?**
- Worker generates `telegram-YYYY-MM-DDTHH-MM-SS-MMMZ.md` format
- If format changed, update regex in `sync-capture.yml`
