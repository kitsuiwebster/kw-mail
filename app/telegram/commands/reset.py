from app.telegram.client import TelegramClient


async def handle_reset(chat_id: str, telegram_client: TelegramClient, conversation_history: dict):
    # Handle /reset command - clear conversation history
    if chat_id in conversation_history:
        del conversation_history[chat_id]
    telegram_client.send_message("🧠 Mémoire réinitialisée !", chat_id)
