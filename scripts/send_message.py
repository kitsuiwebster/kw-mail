#!/usr/bin/env bash
set -euo pipefail

message="${1:-🧪}"

docker compose run --rm kw-mail python3 -c "from dotenv import load_dotenv; load_dotenv(); from app.telegram.client import TelegramClient; print(TelegramClient().send_message('''${message}'''))"
