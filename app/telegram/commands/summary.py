from app.email.imap_client import IMAPClient
from app.mistral.client import MistralClient
from app.telegram.client import TelegramClient
from app.utils import remove_markdown


async def handle_summary(chat_id: str, telegram_client: TelegramClient, mistral_client: MistralClient):
    # Handle /summary command - AI summary of emails
    try:
        telegram_client.send_message("Chargement...", chat_id)

        imap_client = IMAPClient()
        imap_client.connect()
        emails = imap_client.get_emails_last_24h()
        imap_client.disconnect()

        if not emails:
            telegram_client.send_message("Aucun email reçu dans les dernières 24h.", chat_id)
            return

        summary = mistral_client.summarize_emails(emails)
        clean_summary = remove_markdown(summary)
        telegram_client.send_message(f"📊 Résumé des emails (24h)\n\n{clean_summary}", chat_id)

    except Exception as e:
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)
