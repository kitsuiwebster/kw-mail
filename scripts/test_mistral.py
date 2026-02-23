#!/usr/bin/env python3
"""
ÉTAPE 2 - Test Mistral Email Summarization
Fetch emails from last 24h and generate summary with Mistral.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from app.imap_client import IMAPClient
from app.mistral_client import MistralClient


def main():
    # Load environment variables
    load_dotenv()

    print("="*80)
    print("ÉTAPE 2 - TEST MISTRAL SUMMARIZATION")
    print("="*80)
    print()

    # Check required env vars
    required_vars = ["IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "MISTRAL_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        print("  Make sure all credentials are set in .env file")
        return 1

    try:
        # Step 1: Fetch emails from IMAP
        print("Step 1: Fetching emails from last 24 hours...")
        print("-"*80)
        imap_client = IMAPClient()
        imap_client.connect()
        emails = imap_client.get_emails_last_24h()
        imap_client.disconnect()
        print()

        if not emails:
            print("No emails found in last 24h. Nothing to summarize.")
            return 0

        # Step 2: Show email digest (headers only)
        print("Step 2: Email digest (headers only)...")
        print("-"*80)
        for idx, email in enumerate(emails, 1):
            print(f"[{idx}] From: {email['from']}")
            print(f"    Subject: {email['subject']}")
            print(f"    Date: {email['date']}")
            if email.get('cc'):
                print(f"    CC: {email['cc']}")
            print()

        print("-"*80)
        print()

        # Step 3: Generate summary with Mistral
        print("Step 3: Generating summary with Mistral...")
        print("-"*80)
        mistral_client = MistralClient()
        summary = mistral_client.summarize_emails(emails)
        print()

        # Display summary
        print("="*80)
        print("RÉSUMÉ DES EMAILS (24H)")
        print("="*80)
        print()
        print(summary)
        print()
        print("="*80)
        print("✓ ÉTAPE 2 COMPLETED SUCCESSFULLY")
        print("="*80)

        return 0

    except Exception as e:
        print()
        print("="*80)
        print(f"✗ ÉTAPE 2 FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
