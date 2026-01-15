# Vault Sync Automation: Design Document

> **Created:** 2026-01-15
> **Status:** Approved after research

## Problem Statement

The Telegram bot queries a pre-aggregated vault context file (`_vault_context.md`) stored in Cloudflare R2. Currently, syncing requires:
1. SSH to VM
2. Run `./scripts/sync-vault.sh` manually

This means the bot queries stale data until someone remembers to sync.

## Goal

Automatically sync vault context to R2 when the second-brain repo is updated.

## Constraints

- Single user (Daniel)
- Vault is ~500KB pre-aggregated (51 files)
- second-brain repo is on GitHub
- Bot runs on Cloudflare Workers + R2
- Must not expose vault content or credentials

## Research Findings

### Architecture Decision: Single Aggregated File

We use a **pre-aggregated context file** rather than individual vault files. This means:
- Delta sync is **irrelevant** (file is regenerated each time)
- Always uploading full ~500KB
- This is acceptable (0.01 cents, <2 seconds)

### Tool Selection: AWS CLI over Wrangler

| Tool | Pros | Cons |
|------|------|------|
| wrangler | Native Cloudflare | Needs npm install in runner, no sync command |
| aws s3 | Pre-installed on GitHub runners | Needs endpoint configuration |
| rclone | Good sync support | Needs install, configuration |

**Decision:** AWS CLI - already available, well-documented for R2.

### Known Risks

| Risk | Mitigation |
|------|------------|
| R2 403 with Object Read/Write permission | Use Admin Read & Write token |
| GitHub Actions queue delays | Accept; add failure notification |
| Credentials in GitHub Secrets | Acceptable for private repo |
| Script fails silently | Add Telegram notification on failure |

### What Must Be True

1. R2 API token with Admin Read & Write permission created
2. Token credentials stored in GitHub Secrets (second-brain repo)
3. Aggregation script works in Ubuntu runner (bash + AWS CLI)
4. R2 endpoint reachable from GitHub runners

## Selected Approach

**GitHub Action triggered on push to second-brain repo:**

```
Push to second-brain → GitHub Action → Aggregate vault → AWS CLI sync to R2
```

### Workflow Steps

1. Checkout second-brain repo
2. Run aggregation script (bash, creates _vault_context.md)
3. Upload to R2 via AWS CLI
4. On failure: notify via Telegram

### Not Doing

- Individual file sync (architecture doesn't support it)
- Checksum-based sync (AWS CLI doesn't support it)
- Wrangler (unnecessary install step)
- Complex retry logic (simple is better)

## Files to Create

1. `.github/workflows/sync-vault.yml` - GitHub Action workflow
2. `scripts/aggregate-vault.sh` - Aggregation script (CI-compatible)
3. Update `scripts/sync-vault.sh` - Add failure notification

## Acceptance Criteria

1. Push to second-brain triggers sync within 5 minutes (typical)
2. Bot queries updated content after sync completes
3. Sync failures notify via Telegram
4. No vault content or credentials in logs/code

## References

- [Cloudflare R2 Authentication](https://developers.cloudflare.com/r2/api/tokens/)
- [AWS CLI sync](https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html)
- [R2 403 Bug](https://github.com/cloudflare/workers-sdk/issues/9235)
- [GitHub Actions with R2](https://mzfit.app/blog/github_with_cloudflare_r2/)
