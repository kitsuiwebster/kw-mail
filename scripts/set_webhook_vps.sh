#!/usr/bin/env bash
set -euo pipefail

# Load TELEGRAM_BOT_TOKEN from .env
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep TELEGRAM_BOT_TOKEN | xargs)
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "❌ TELEGRAM_BOT_TOKEN not found in .env"
  exit 1
fi

WEBHOOK_URL="https://mailbot.kitsuiwebster.com/webhook"

echo "🔧 Setting webhook to: ${WEBHOOK_URL}"
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${WEBHOOK_URL}\"}")

echo "$RESPONSE"
echo ""
echo "✅ Webhook set to VPS"
