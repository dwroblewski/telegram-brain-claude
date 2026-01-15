#!/bin/bash
# Sync vault markdown files to R2 bucket
# Handles spaces in filenames correctly

set -e

VAULT_PATH="${VAULT_PATH:-$HOME/projects/second-brain}"
BUCKET="telegram-brain-vault"

# Load .env if present
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
  set -a; source "$SCRIPT_DIR/../.env"; set +a
fi

# Require credentials
if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
  echo "ERROR: Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
  echo "Create .env file from .env.example"
  exit 1
fi

export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID

cd "$VAULT_PATH"

MAX_FILES="${1:-150}"

echo "Syncing vault to R2 ($MAX_FILES files max)..."

count=0

# Use process substitution to avoid subshell issue
while IFS= read -r -d '' file; do
  if [ $count -ge $MAX_FILES ]; then
    break
  fi

  # Remove leading ./
  key="${file#./}"

  # Upload to R2
  if wrangler r2 object put "$BUCKET/$key" --file "$file" --content-type "text/markdown" --remote 2>/dev/null; then
    count=$((count + 1))

    # Progress every 30 files
    if [ $((count % 30)) -eq 0 ]; then
      echo "  $count files..."
    fi
  else
    echo "  FAILED: $key"
  fi
done < <(find . -maxdepth 3 -name "*.md" \
  -not -path "*/venv*" \
  -not -path "*/.git/*" \
  -not -path "*/node_modules/*" \
  -not -path "*/telegram-brain-claude/*" \
  -not -path "*/.ai-context/*" \
  -not -path "*/telegram-brain-v2/*" \
  -print0)

echo "Done: $count files synced"
