from app.telegram.client import TelegramClient
from app.telegram.messages import MENU_TEXT


async def handle_menu(chat_id: str, telegram_client: TelegramClient):
    # Handle /menu command - show all commands
    telegram_client.send_message(MENU_TEXT, chat_id)
