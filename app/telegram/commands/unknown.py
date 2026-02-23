from app.telegram.client import TelegramClient


async def handle_unknown_command(command: str, chat_id: str, telegram_client: TelegramClient):
    # Handle unknown commands
    telegram_client.send_message(
        f"Commande inconnue : {command}\nUtilisez /help pour voir les commandes.",
        chat_id,
    )
