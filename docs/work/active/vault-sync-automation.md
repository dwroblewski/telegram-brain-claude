# vault-sync-automation: Automatic Vault Sync to R2

> **Started:** 2026-01-15 | **Status:** Planning

## Mission

Automatically sync vault context to R2 when second-brain repo is pushed, so Telegram bot always has current data.

## Approach

GitHub Action in second-brain repo triggers on push, aggregates vault, uploads to R2 via AWS CLI.

See: `artifacts/vault-sync-automation/design.md`

## Acceptance Criteria

### AC1: GitHub Action triggers on push
- **Done when:** Pushing to second-brain main branch triggers workflow
- **Verify:** `gh run list --repo dwroblewski/second-brain --limit 1`
- **Evidence:** `artifacts/vault-sync-automation/evidence/ac1_workflow_run.log`

### AC2: Vault context uploaded to R2
- **Done when:** `_vault_context.md` in R2 matches local aggregation
- **Verify:** `wrangler r2 object get telegram-brain-vault/_vault_context.md --file /tmp/check.md --remote && wc -c /tmp/check.md`
- **Evidence:** `artifacts/vault-sync-automation/evidence/ac2_r2_upload.log`

### AC3: Bot queries updated content
- **Done when:** `/ask` returns content from latest vault sync
- **Verify:** Manual test via Telegram
- **Evidence:** Screenshot or message copy

### AC4: Failure notification works
- **Done when:** Simulated failure sends Telegram message
- **Verify:** Intentionally break sync, check for notification
- **Evidence:** `artifacts/vault-sync-automation/evidence/ac4_failure_notification.log`

### AC5: No credential/content leakage
- **Done when:** GitHub Action logs contain no secrets or vault content
- **Verify:** Review workflow run logs
- **Evidence:** `artifacts/vault-sync-automation/evidence/ac5_log_review.md`

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| R2 403 permission error | Use Admin Read & Write token |
| Queue delays | Accept; not critical for personal use |
| Script breaks in CI | Test locally first with similar environment |
| Credentials leak in logs | Use `::add-mask::` for secrets, review logs |

## Dependencies

- R2 API token (Admin Read & Write) - **Manual step required**
- GitHub Secrets configured in second-brain repo - **Manual step required**

## Anti-Patterns to Avoid

- Don't install wrangler when AWS CLI is pre-installed
- Don't over-engineer retry logic
- Don't log vault content for debugging
- Don't use complex delta sync (irrelevant for our architecture)
