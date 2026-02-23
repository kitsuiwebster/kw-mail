from app.telegram.client import TelegramClient
from app.telegram.messages import WELCOME_TEXT


async def handle_start(chat_id: str, telegram_client: TelegramClient):
    # Handle /start command - welcome message
    telegram_client.send_message(WELCOME_TEXT, chat_id)
