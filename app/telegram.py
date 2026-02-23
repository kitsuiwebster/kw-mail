import os
import httpx
from typing import Optional


class TelegramClient:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not set in environment")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text: str, chat_id: Optional[str] = None) -> dict:
        """
        Send a message to Telegram.

        Args:
            text: Message text (plain text with emojis)
            chat_id: Optional chat ID (defaults to configured TELEGRAM_CHAT_ID)

        Returns:
            Response from Telegram API
        """
        target_chat_id = chat_id or self.chat_id

        payload = {
            "chat_id": target_chat_id,
            "text": text
            # No parse_mode = plain text with emojis
        }

        with httpx.Client() as client:
            response = client.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    def set_webhook(self, webhook_url: str) -> dict:
        """
        Set the webhook URL for receiving updates.

        Args:
            webhook_url: Public URL where Telegram will send updates

        Returns:
            Response from Telegram API
        """
        payload = {
            "url": webhook_url
        }

        with httpx.Client() as client:
            response = client.post(
                f"{self.api_url}/setWebhook",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    def delete_webhook(self) -> dict:
        """Delete the current webhook."""
        with httpx.Client() as client:
            response = client.post(
                f"{self.api_url}/deleteWebhook",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    def get_webhook_info(self) -> dict:
        """Get current webhook configuration."""
        with httpx.Client() as client:
            response = client.get(
                f"{self.api_url}/getWebhookInfo",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()


if __name__ == "__main__":
    # Quick test
    from dotenv import load_dotenv
    load_dotenv()

    client = TelegramClient()

    print("Sending test message...")
    result = client.send_message("✓ KW Email Reader - Telegram client test")
    print(f"Message sent: {result['ok']}")
