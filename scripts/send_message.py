#!/usr/bin/env python3
# Send a simple message to Telegram

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from app.telegram.client import TelegramClient

load_dotenv()

def main():
    message = sys.argv[1] if len(sys.argv) > 1 else "Test message"
    
    try:
        client = TelegramClient()
        result = client.send_message(message)
        
        if result.get('ok'):
            print(f"✓ Message sent: {message}")
        else:
            print(f"✗ Failed: {result}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
