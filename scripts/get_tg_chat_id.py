#!/usr/bin/env python3
"""
Script to get your Telegram Chat ID
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

if not token or token == "your-telegram-bot-token":
    print("ERROR: Please set TELEGRAM_BOT_TOKEN in .env file first")
    print()
    print("Steps:")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot and follow instructions")
    print("3. Copy the token and add it to .env:")
    print("   TELEGRAM_BOT_TOKEN=your-token-here")
    sys.exit(1)

print("="*80)
print("GETTING YOUR TELEGRAM CHAT ID")
print("="*80)
print()
print("Instructions:")
print("1. Open Telegram")
print("2. Search for your bot (the username you created)")
print("3. Click START or send any message to your bot")
print("4. Then press ENTER here...")
input()

print("Fetching updates...")

import urllib.request
import json

url = f"https://api.telegram.org/bot{token}/getUpdates"

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read())

    if not data.get("result"):
        print("✗ No messages found")
        print("  Make sure you sent a message to your bot first!")
        sys.exit(1)

    # Get the most recent message
    last_update = data["result"][-1]
    chat_id = last_update["message"]["chat"]["id"]
    username = last_update["message"]["chat"].get("username", "N/A")

    print()
    print("✓ Found your chat!")
    print(f"  Username: @{username}")
    print(f"  Chat ID: {chat_id}")
    print()
    print("Add this to your .env file:")
    print(f"TELEGRAM_CHAT_ID={chat_id}")
    print()

except Exception as e:
    print(f"✗ Error: {e}")
    print()
    print("Troubleshooting:")
    print("- Check that your TELEGRAM_BOT_TOKEN is correct")
    print("- Make sure you sent a message to your bot")

