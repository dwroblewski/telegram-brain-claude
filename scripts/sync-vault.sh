#!/bin/bash
# sync-vault.sh - Sync vault to R2 with pre-aggregated context
# Creates single _vault_context.md for fast worker queries
set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$HOME/projects/second-brain}"
BUCKET="telegram-brain-vault"
CONTEXT_FILE="/tmp/vault_context.md"

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

echo "=== Vault Sync ==="
echo "Source: $VAULT_PATH"
echo "Bucket: $BUCKET"

# Step 1: Build aggregated context file
echo ""
echo "Building vault context..."
rm -f "$CONTEXT_FILE"

file_count=0
total_size=0

# Priority files first (always included in full)
priority_files=(
  "QUICKFACTS.md"
  "VAULT-INDEX.md"
)

for pf in "${priority_files[@]}"; do
  if [ -f "$pf" ]; then
    echo "=== $pf ===" >> "$CONTEXT_FILE"
    cat "$pf" >> "$CONTEXT_FILE"
    echo -e "\n" >> "$CONTEXT_FILE"
    ((file_count++)) || true
  fi
done

# Then PARA folders (Areas most important, then Projects, then Resources)
for folder in Areas Projects Resources; do
  if [ ! -d "$folder" ]; then continue; fi

  while IFS= read -r -d '' file; do
    # Skip if we've hit size limit (500KB)
    current_size=$(wc -c < "$CONTEXT_FILE" 2>/dev/null || echo 0)
    if [ "$current_size" -gt 500000 ]; then
      echo "  Size limit reached at $file_count files"
      break 2
    fi

    # Get relative path
    relpath="${file#./}"

    echo "=== $relpath ===" >> "$CONTEXT_FILE"
    cat "$file" >> "$CONTEXT_FILE"
    echo -e "\n" >> "$CONTEXT_FILE"
    ((file_count++)) || true

  done < <(find "./$folder" -maxdepth 2 -name "*.md" -type f -print0 2>/dev/null)
done

total_size=$(wc -c < "$CONTEXT_FILE")
echo "  Aggregated $file_count files ($((total_size / 1024))KB)"

# Step 2: Upload context file to R2
echo ""
echo "Uploading to R2..."

if wrangler r2 object put "$BUCKET/_vault_context.md" \
  --file "$CONTEXT_FILE" \
  --content-type "text/markdown" \
  --remote 2>&1 | grep -q "Upload complete"; then
  echo "  ✓ Context file uploaded"
else
  echo "  ✗ Upload failed!"
  exit 1
fi

# Step 3: Verify upload
echo ""
echo "Verifying..."

# Download and check size matches
wrangler r2 object get "$BUCKET/_vault_context.md" \
  --file /tmp/verify_context.md --remote 2>/dev/null || true

if [ -f /tmp/verify_context.md ]; then
  verify_size=$(wc -c < /tmp/verify_context.md)
  # Allow small difference due to line endings
  size_diff=$((total_size - verify_size))
  if [ ${size_diff#-} -lt 1000 ]; then
    echo "  ✓ Verification passed (${verify_size} bytes)"
  else
    echo "  ✗ Size mismatch! Local: $total_size, R2: $verify_size"
    exit 1
  fi
else
  echo "  ✗ Could not download for verification"
  exit 1
fi

# Step 4: Also upload individual files for capture browsing (optional, background)
echo ""
echo "Syncing individual files for inbox captures..."

# Just sync 0-Inbox to R2 for capture history
inbox_count=0
while IFS= read -r -d '' file; do
  key="${file#./}"
  if wrangler r2 object put "$BUCKET/$key" --file "$file" \
    --content-type "text/markdown" --remote 2>/dev/null; then
    ((inbox_count++)) || true
  fi
done < <(find "./0-Inbox" -name "*.md" -type f -print0 2>/dev/null)

echo "  Synced $inbox_count inbox files"

echo ""
echo "=== Sync Complete ==="
echo "  Context: $file_count files ($((total_size / 1024))KB)"
echo "  Inbox: $inbox_count captures"

# Cleanup
rm -f "$CONTEXT_FILE" /tmp/verify_context.md
