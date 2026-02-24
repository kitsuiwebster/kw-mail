#!/usr/bin/env python3
# Quick test to validate Mistral API key.

import os
import sys

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

api_key = os.getenv("MISTRAL_API_KEY")

print("Testing Mistral API key...")
print(f"Key: {api_key[:10]}...{api_key[-5:]}")
print()

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": "mistral-large-latest",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10,
}

try:
    with httpx.Client() as client:
        response = client.post(
            "https://api.mistral.ai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10.0,
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")

        if response.status_code == 401:
            print("\n❌ API Key is INVALID")
            print("  Get a valid key from: https://console.mistral.ai/api-keys/")
        elif response.status_code == 200:
            print("\n👉 API Key is VALID")
        else:
            print(f"\n? Unexpected status: {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
