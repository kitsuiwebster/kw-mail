#!/usr/bin/env python3
# ETAPE 1 - Test IMAP Connection to Proton Bridge
# Read emails from last 24h and display metadata.

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from app.email.imap_client import IMAPClient


def main():
    load_dotenv()

    print("=" * 80)
    print("ÉTAPE 1 - TEST IMAP CONNECTION")
    print("=" * 80)
    print()

    required_vars = ["IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("  Create a .env file based on .env.example")
        return 1

    try:
        client = IMAPClient()

        print("Connecting to Proton Bridge...")
        client.connect()
        print()

        print("Fetching emails from last 24 hours...")
        emails = client.get_emails_last_24h()
        print()

        print("=" * 80)
        print(f"FOUND {len(emails)} EMAILS IN LAST 24H")
        print("=" * 80)
        print()

        if not emails:
            print("No emails found in the last 24 hours.")
            print("This is normal if you haven't received emails recently.")
        else:
            for idx, email_data in enumerate(emails, 1):
                print(f"[EMAIL {idx}]")
                print(f"  From:    {email_data['from']}")
                print(f"  Subject: {email_data['subject']}")
                print(f"  Date:    {email_data['date']}")
                print("  Body Preview:")

                body_preview = email_data["body"][:300].replace("\n", "\n           ")
                print(f"           {body_preview}")

                if len(email_data["body"]) > 300:
                    print(f"           ... ({len(email_data['body'])} chars total)")

                print()
                print("-" * 80)
                print()

        client.disconnect()

        print()
        print("=" * 80)
        print("👉 ÉTAPE 1 COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ÉTAPE 1 FAILED: {e}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
