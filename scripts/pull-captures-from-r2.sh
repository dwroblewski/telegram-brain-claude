#!/bin/bash
# pull-captures-from-r2.sh - Pull Telegram captures from R2 to local vault
# Run this to sync captures back to git

set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$HOME/projects/second-brain}"
BUCKET="telegram-brain-vault"
INBOX_PATH="$VAULT_PATH/0-Inbox"

# Load .env if present
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
  set -a; source "$SCRIPT_DIR/../.env"; set +a
fi

# Require credentials
if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
  echo "ERROR: Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
  exit 1
fi

export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID

echo "=== Pulling Telegram Captures from R2 ==="
echo "Bucket: $BUCKET"
echo "Target: $INBOX_PATH"
echo ""

# List all files in 0-Inbox/ prefix in R2
echo "Listing R2 objects..."
r2_files=$(wrangler r2 object list "$BUCKET" --prefix "0-Inbox/telegram-" --remote 2>/dev/null | grep -o '"key":"[^"]*"' | sed 's/"key":"//g;s/"//g' || echo "")

if [ -z "$r2_files" ]; then
  echo "No Telegram captures found in R2"
  exit 0
fi

# Count files
total=$(echo "$r2_files" | wc -l)
echo "Found $total captures in R2"
echo ""

# Pull each file if it doesn't exist locally
new_count=0
for r2_key in $r2_files; do
  # Extract filename from key (0-Inbox/telegram-2026-01-15T... → telegram-2026-01-15T...)
  filename=$(basename "$r2_key")
  local_path="$INBOX_PATH/$filename"

  if [ -f "$local_path" ]; then
    # Already exists locally, skip
    continue
  fi

  # Download from R2
  echo "  Pulling: $filename"
  if wrangler r2 object get "$BUCKET/$r2_key" --file "$local_path" --remote 2>/dev/null; then
    ((new_count++)) || true
  else
    echo "    FAILED to download"
  fi
done

echo ""
echo "=== Done ==="
echo "  New captures pulled: $new_count"
echo "  Total in R2: $total"

if [ $new_count -gt 0 ]; then
  echo ""
  echo "Tip: cd $VAULT_PATH && git add 0-Inbox && git commit -m 'chore: Sync Telegram captures' && git push"
fi
