#!/usr/bin/env python3
# ETAPE 4 - Test Tool System
# Test search_emails, get_full_email, and Mistral tool calling.

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from app.mistral.client import MistralClient
from app.mistral.tool_definitions import TOOL_DEFINITIONS
from app.mistral.tools import execute_tool, get_full_email, search_emails


def main():
    load_dotenv()

    print("=" * 80)
    print("ÉTAPE 4 - TEST TOOL SYSTEM")
    print("=" * 80)
    print()

    try:
        print("Test 1: search_emails tool")
        print("-" * 80)
        print("Searching for 'INPI' in emails...")

        results = search_emails("INPI")

        if results:
            print(f"👉 Found {len(results)} matching emails:")
            for idx, email in enumerate(results, 1):
                print(f"  [{idx}] From: {email['from']}")
                print(f"      Subject: {email['subject']}")
                print(f"      ID: {email['id']}")
                print()
        else:
            print("No emails found matching 'INPI'")

        print()

        print("Test 2: get_full_email tool")
        print("-" * 80)

        if results:
            email_id = results[0]["id"]
            print(f"Retrieving full email with ID: {email_id}...")

            full_email = get_full_email(email_id)

            if full_email:
                print("👉 Retrieved email:")
                print(f"  From: {full_email['from']}")
                print(f"  Subject: {full_email['subject']}")
                print(f"  Date: {full_email['date']}")
                print(f"  Body preview: {full_email['body'][:200]}...")
            else:
                print("❌ Email not found")
        else:
            print("Skipping (no search results from Test 1)")

        print()

        print("Test 3: Mistral with tool calling")
        print("-" * 80)
        print("Testing Mistral's ability to call tools...")
        print()

        mistral_client = MistralClient()

        test_query = (
            "L'utilisateur te demande: \"Montre-moi les emails de l'INPI\"\n\n"
            "Utilise l'outil search_emails pour chercher les emails contenant \"INPI\"."
        )

        print('Query: "Montre-moi les emails de l\'INPI"')
        print()

        response = mistral_client.chat_with_tools(
            user_message=test_query,
            tools=TOOL_DEFINITIONS,
            tool_executor=execute_tool,
        )

        print("Mistral response:")
        print(response)
        print()

        print("Test 4: Query requiring full email retrieval")
        print("-" * 80)

        if results:
            email_id = results[0]["id"]
            test_query_2 = (
                "L'utilisateur demande le contenu complet d'un email spécifique.\n\n"
                f"L'ID de l'email est: {email_id}\n\n"
                "Utilise l'outil get_full_email pour récupérer le contenu complet, puis résume-le."
            )

            print('Query: "Donne-moi le contenu complet de l\'email INPI"')
            print()

            response_2 = mistral_client.chat_with_tools(
                user_message=test_query_2,
                tools=TOOL_DEFINITIONS,
                tool_executor=execute_tool,
            )

            print("Mistral response:")
            print(response_2)
        else:
            print("Skipping (no emails found in previous tests)")

        print()
        print("=" * 80)
        print("👉 ÉTAPE 4 - TOOL SYSTEM VALIDATED")
        print("=" * 80)
        print()
        print("The tool system is working!")
        print()
        print("Next steps:")
        print("1. Start the server: python scripts/start_server.py")
        print("2. Set up ngrok webhook (see ETAPE3_TESTING.md)")
        print("3. Try asking questions on Telegram:")
        print('   - "Montre-moi les emails de l\'INPI"')
        print('   - "Quel est le contenu de l\'email sur Hyperstack ?"')
        print('   - "Ai-je reçu quelque chose d\'urgent ?"')

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ÉTAPE 4 FAILED: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
