#!/usr/bin/env python3
# ETAPE 3 - Test Telegram Bot
# Test sending messages to Telegram.

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from app.telegram.client import TelegramClient


def main():
    load_dotenv()

    print("=" * 80)
    print("ÉTAPE 3 - TEST TELEGRAM BOT")
    print("=" * 80)
    print()

    required_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        print("  Make sure Telegram credentials are set in .env file")
        return 1

    try:
        print("Initializing Telegram client...")
        client = TelegramClient()
        print("✓ Client initialized")
        print()

        print("Test 1: Sending simple message...")
        print("-" * 80)
        result = client.send_message("✓ Test message from KW Email Reader")

        if result.get("ok"):
            print("✓ Message sent successfully")
        else:
            print(f"✗ Failed to send message: {result}")
            return 1

        print()

        print("Test 2: Sending formatted message...")
        print("-" * 80)

        formatted_message = (
            "KW Email Reader - Test 📧\n\n"
            "Features:\n"
            "- ✓ IMAP connection to Proton Bridge\n"
            "- ✓ Mistral AI summarization\n"
            "- ✓ Telegram bot integration\n\n"
            "All systems operational!"
        )

        result = client.send_message(formatted_message)

        if result.get("ok"):
            print("✓ Formatted message sent successfully")
        else:
            print(f"✗ Failed to send formatted message: {result}")
            return 1

        print()

        print("Test 3: Checking webhook configuration...")
        print("-" * 80)

        webhook_info = client.get_webhook_info()

        if webhook_info.get("ok"):
            webhook_data = webhook_info.get("result", {})
            webhook_url = webhook_data.get("url", "Not set")
            pending_updates = webhook_data.get("pending_update_count", 0)

            print(f"Webhook URL: {webhook_url}")
            print(f"Pending updates: {pending_updates}")
            print()

            if webhook_url == "" or webhook_url == "Not set":
                print("ℹ️  No webhook configured (normal for local testing)")
                print("   To set up webhook, you need:")
                print("   1. A public URL (use ngrok or similar)")
                print("   2. Run the FastAPI server")
                print("   3. Set webhook to: https://your-domain.com/webhook")
        else:
            print(f"✗ Failed to get webhook info: {webhook_info}")

        print()
        print("=" * 80)
        print("✓ ÉTAPE 3 - TELEGRAM CLIENT VALIDATED")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Check your Telegram for the test messages")
        print("2. To enable webhook, run: python -m app.main")
        print("3. Use ngrok to expose local server for testing")

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"✗ ÉTAPE 3 FAILED: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
