# vault-sync-automation: Implementation Tasks

> **Plan created:** 2026-01-15
> **Work container:** `docs/work/active/vault-sync-automation.md`
> **Design:** `artifacts/vault-sync-automation/design.md`

## Prerequisites (Manual Steps)

### P1: Create R2 API Token

**Location:** Cloudflare Dashboard → R2 → Manage R2 API Tokens

**Settings:**
- Name: `github-actions-sync`
- Permissions: **Admin Read & Write** (not Object Read/Write - known 403 bug)
- Bucket scope: `telegram-brain-vault` only

**Capture:**
- Access Key ID
- Secret Access Key
- Account ID (from URL or dashboard)

### P2: Add GitHub Secrets

**Location:** github.com/dwroblewski/second-brain → Settings → Secrets → Actions

**Create secrets:**
- `R2_ACCESS_KEY_ID` - Access Key ID from P1
- `R2_SECRET_ACCESS_KEY` - Secret Access Key from P1
- `R2_ACCOUNT_ID` - Cloudflare Account ID
- `TELEGRAM_BOT_TOKEN` - For failure notifications
- `TELEGRAM_CHAT_ID` - Your Telegram user ID

---

## Tasks

### Task 1: Create CI-compatible aggregation script

**Files:**
- Create: `scripts/aggregate-vault.sh`

**Why:** Current `sync-vault.sh` depends on wrangler and local .env. Need a script that:
- Takes vault path as argument
- Outputs to stdout or specified file
- Works with only bash + standard tools
- No external dependencies

**Steps:**

1. [ ] Create aggregation script
   ```bash
   # scripts/aggregate-vault.sh
   #!/bin/bash
   # Aggregate vault into single context file for R2
   # Usage: ./aggregate-vault.sh /path/to/vault /path/to/output.md
   set -euo pipefail

   VAULT_PATH="${1:?Usage: $0 <vault_path> <output_file>}"
   OUTPUT_FILE="${2:?Usage: $0 <vault_path> <output_file>}"

   # ... aggregation logic from sync-vault.sh
   ```

2. [ ] Test locally
   ```bash
   ./scripts/aggregate-vault.sh ~/projects/second-brain /tmp/test_context.md
   wc -c /tmp/test_context.md  # Should be ~500KB
   ```

3. [ ] Commit
   ```bash
   git add scripts/aggregate-vault.sh
   git commit -m "feat(sync): Add CI-compatible aggregation script"
   ```

---

### Task 2: Create GitHub Action workflow

**Files:**
- Create: `.github/workflows/sync-vault.yml` (in second-brain repo)

**Steps:**

1. [ ] Create workflow file
   ```yaml
   name: Sync Vault to R2

   on:
     push:
       branches: [main]
       paths:
         - 'Areas/**'
         - 'Projects/**'
         - 'Resources/**'
         - 'QUICKFACTS.md'
         - 'VAULT-INDEX.md'
     workflow_dispatch:  # Manual trigger

   jobs:
     sync:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Aggregate vault
           run: |
             # Inline aggregation (or call script)
             # Output to _vault_context.md

         - name: Upload to R2
           env:
             AWS_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
             AWS_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
           run: |
             aws s3 cp _vault_context.md \
               s3://telegram-brain-vault/_vault_context.md \
               --endpoint-url https://${{ secrets.R2_ACCOUNT_ID }}.r2.cloudflarestorage.com

         - name: Notify on failure
           if: failure()
           run: |
             curl -s -X POST \
               "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
               -d chat_id=${{ secrets.TELEGRAM_CHAT_ID }} \
               -d text="❌ Vault sync failed. Check GitHub Actions."
   ```

2. [ ] Test with workflow_dispatch first (manual trigger)

3. [ ] Verify R2 upload
   ```bash
   wrangler r2 object get telegram-brain-vault/_vault_context.md \
     --file /tmp/verify.md --remote
   wc -c /tmp/verify.md
   ```

4. [ ] Commit workflow to second-brain repo
   ```bash
   cd ~/projects/second-brain
   git add .github/workflows/sync-vault.yml
   git commit -m "ci: Add vault sync to R2 on push"
   git push
   ```

---

### Task 3: Test end-to-end flow

**Steps:**

1. [ ] Make a small vault change
   ```bash
   cd ~/projects/second-brain
   echo "<!-- sync test $(date) -->" >> QUICKFACTS.md
   git add QUICKFACTS.md
   git commit -m "test: Trigger vault sync"
   git push
   ```

2. [ ] Monitor GitHub Action
   ```bash
   gh run watch --repo dwroblewski/second-brain
   ```

3. [ ] Verify R2 updated
   ```bash
   wrangler r2 object get telegram-brain-vault/_vault_context.md \
     --file /tmp/post_sync.md --remote
   grep "sync test" /tmp/post_sync.md
   ```

4. [ ] Test bot query
   - Send `/ask what is in QUICKFACTS?` to Telegram bot
   - Verify response includes recent content

5. [ ] Capture evidence
   ```bash
   gh run list --repo dwroblewski/second-brain --limit 1 > \
     artifacts/vault-sync-automation/evidence/ac1_workflow_run.log
   ```

---

### Task 4: Test failure notification

**Steps:**

1. [ ] Temporarily break the workflow (wrong secret name)

2. [ ] Trigger workflow
   ```bash
   gh workflow run sync-vault.yml --repo dwroblewski/second-brain
   ```

3. [ ] Verify Telegram notification received

4. [ ] Fix workflow and commit

5. [ ] Document in evidence
   ```bash
   echo "Failure notification received at $(date)" > \
     artifacts/vault-sync-automation/evidence/ac4_failure_notification.log
   ```

---

### Task 5: Security review

**Steps:**

1. [ ] Review GitHub Action logs for credential leaks
   ```bash
   gh run view --repo dwroblewski/second-brain --log | grep -i "key\|token\|secret"
   ```

2. [ ] Verify no vault content in logs
   ```bash
   gh run view --repo dwroblewski/second-brain --log | grep -i "harbourvest\|lindsay"
   ```

3. [ ] Document review
   ```bash
   cat > artifacts/vault-sync-automation/evidence/ac5_log_review.md << 'EOF'
   # Security Review: Vault Sync Workflow

   **Date:** $(date)
   **Reviewer:** Claude + Daniel

   ## Checklist
   - [ ] No API keys in logs
   - [ ] No vault content in logs
   - [ ] Secrets properly masked
   - [ ] Workflow uses minimal permissions

   ## Findings
   [Document any issues]
   EOF
   ```

---

## Completion Checklist

- [ ] P1: R2 API Token created
- [ ] P2: GitHub Secrets configured
- [ ] Task 1: Aggregation script created
- [ ] Task 2: GitHub Action workflow deployed
- [ ] Task 3: End-to-end test passed
- [ ] Task 4: Failure notification tested
- [ ] Task 5: Security review completed
- [ ] All acceptance criteria verified
