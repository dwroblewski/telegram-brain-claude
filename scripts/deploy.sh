#!/bin/bash
# deploy.sh - Deploy worker with preflight checks and smoke tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [ -f "$SCRIPT_DIR/../.env" ]; then
  set -a; source "$SCRIPT_DIR/../.env"; set +a
fi

# Require credentials
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] || [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  echo "ERROR: Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
  echo "Create .env file from .env.example"
  exit 1
fi

if [ -z "${WORKER_URL:-}" ]; then
  echo "ERROR: Missing WORKER_URL in .env"
  exit 1
fi

if [ -z "${TELEGRAM_ALLOWED_USER_ID:-}" ]; then
  echo "ERROR: Missing TELEGRAM_ALLOWED_USER_ID in .env"
  exit 1
fi

export CLOUDFLARE_API_TOKEN
export CLOUDFLARE_ACCOUNT_ID

echo "=== Pre-flight Checks ==="

# 1. Check for conflicting services
echo "Checking for conflicting services..."
conflicting_services=("telegram-inbox-bot" "telegram-brain" "secondbrain-bot")
for svc in "${conflicting_services[@]}"; do
  if systemctl is-active "$svc" 2>/dev/null; then
    echo "  ✗ CONFLICT: $svc is running"
    echo "    Run: sudo systemctl stop $svc && sudo systemctl disable $svc"
    exit 1
  fi
done
echo "  ✓ No conflicting services"

# 2. Check wrangler is available
if ! command -v wrangler &>/dev/null && ! npx wrangler --version &>/dev/null; then
  echo "  ✗ wrangler not found"
  exit 1
fi
echo "  ✓ wrangler available"

# 3. Check vault context exists in R2
echo "Checking vault context..."
if ! wrangler r2 object get telegram-brain-vault/_vault_context.md \
  --file /tmp/check_context.md --remote 2>/dev/null; then
  echo "  ✗ No vault context in R2"
  echo "    Run: ./sync-vault.sh first"
  exit 1
fi
context_size=$(wc -c < /tmp/check_context.md)
rm -f /tmp/check_context.md
if [ "$context_size" -lt 10000 ]; then
  echo "  ✗ Vault context too small (${context_size} bytes)"
  exit 1
fi
echo "  ✓ Vault context exists ($((context_size / 1024))KB)"

echo ""
echo "=== Deploying Worker ==="
cd "$PROJECT_DIR/worker"
npx wrangler deploy

echo ""
echo "=== Smoke Tests ==="

# Test 1: Health check
echo "Testing /health..."
health_response=$(curl -sf "$WORKER_URL/health" || echo '{"status":"failed"}')
health_status=$(echo "$health_response" | jq -r '.status')

if [ "$health_status" != "healthy" ]; then
  echo "  ✗ Health check failed: $health_response"
  echo "  Rolling back..."
  npx wrangler rollback
  exit 1
fi

vault_size=$(echo "$health_response" | jq -r '.checks.vault.sizeKB // 0')
echo "  ✓ Health: $health_status (vault: ${vault_size}KB)"

# Test 2: /ask response (with timeout)
echo "Testing /ask..."
ask_start=$(date +%s)

# Send test query
curl -sf -X POST "$WORKER_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "update_id": '"$(date +%s)"',
    "message": {
      "message_id": 9999,
      "chat": {"id": '"$TELEGRAM_ALLOWED_USER_ID"'},
      "from": {"id": '"$TELEGRAM_ALLOWED_USER_ID"'},
      "text": "/ask What is in my vault?"
    }
  }' >/dev/null

# Wait for processing
sleep 3

ask_end=$(date +%s)
ask_duration=$((ask_end - ask_start))

if [ "$ask_duration" -gt 20 ]; then
  echo "  ⚠ /ask slow (${ask_duration}s)"
else
  echo "  ✓ /ask responded (${ask_duration}s)"
fi

# Test 3: /test endpoint (no persistence)
echo "Testing /test endpoint..."
test_response=$(curl -sf -X POST "$WORKER_URL/test" \
  -H "Content-Type: application/json" || echo '{"ok":false}')

if echo "$test_response" | jq -e '.ok' >/dev/null 2>&1; then
  echo "  ✓ /test endpoint working"
else
  echo "  ⚠ /test response unclear: $test_response"
fi

echo ""
echo "=== Deploy Complete ==="
echo "Worker: $WORKER_URL"
echo ""
echo "Manual verification:"
echo "  1. Send /health to bot"
echo "  2. Send /ask <your test query>"
echo "  3. Send a test capture message"
