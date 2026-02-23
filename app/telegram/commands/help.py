from app.telegram.client import TelegramClient
from app.telegram.messages import HELP_TEXT


async def handle_help(chat_id: str, telegram_client: TelegramClient):
    # Handle /help command - detailed help
    telegram_client.send_message(HELP_TEXT, chat_id)
