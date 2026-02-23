#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <ngrok_https_base_url>"
  echo "Example: $0 https://marlon-squishier-limitlessly.ngrok-free.dev"
  exit 1
fi

BASE_URL="$1"

# Load TELEGRAM_BOT_TOKEN from .env
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep TELEGRAM_BOT_TOKEN | xargs)
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "❌ TELEGRAM_BOT_TOKEN not found in .env"
  exit 1
fi

echo "🔧 Setting webhook to: ${BASE_URL}/webhook"
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${BASE_URL}/webhook\"}")

echo "$RESPONSE"
echo ""
echo "✅ Webhook set to local (ngrok)"
