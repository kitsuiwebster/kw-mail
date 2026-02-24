import os
import socket
from typing import Optional

import httpx

from app.logger import logger


class TelegramClient:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.force_ipv4 = os.getenv("TELEGRAM_FORCE_IPV4", "false").lower() == "true"
        self.timeout = float(os.getenv("TELEGRAM_HTTP_TIMEOUT", "10"))

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID not set in environment")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _client(self) -> httpx.Client:
        # Optionally force IPv4 if IPv6 routing is slow/unreliable
        if self.force_ipv4:
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
            return httpx.Client(transport=transport, timeout=self.timeout)
        return httpx.Client(timeout=self.timeout)

    def send_message(self, text: str, chat_id: Optional[str] = None) -> dict:
        # Send a message to Telegram
        target_chat_id = chat_id or self.chat_id

        payload = {
            "chat_id": target_chat_id,
            "text": text,
        }

        with self._client() as client:
            response = client.post(
                f"{self.api_url}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def set_webhook(self, webhook_url: str) -> dict:
        # Set the webhook URL for receiving updates
        with self._client() as client:
            response = client.post(
                f"{self.api_url}/setWebhook",
                json={"url": webhook_url},
            )
            response.raise_for_status()
            return response.json()

    def delete_webhook(self) -> dict:
        # Delete the current webhook
        with self._client() as client:
            response = client.post(
                f"{self.api_url}/deleteWebhook",
            )
            response.raise_for_status()
            return response.json()

    def get_webhook_info(self) -> dict:
        # Get current webhook configuration
        with self._client() as client:
            response = client.get(
                f"{self.api_url}/getWebhookInfo",
            )
            response.raise_for_status()
            return response.json()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    client = TelegramClient()

    logger.info("Sending test message...")
    result = client.send_message("👉 KW Email Reader - Telegram client test")
    logger.info(f"Message sent: {result['ok']}")
