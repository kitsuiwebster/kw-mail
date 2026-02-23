import re

from app.email.imap_client import IMAPClient
from app.telegram.client import TelegramClient
from app.telegram.commands._shared import send_in_chunks


async def handle_all(command: str, chat_id: str, telegram_client: TelegramClient):
    # Handle /all and /tous commands - list all emails
    try:
        parts = command.split()
        days = 1
        if len(parts) > 1:
            try:
                days = int(parts[1])
            except ValueError:
                days = 1

        telegram_client.send_message("Chargement...", chat_id)

        imap_client = IMAPClient()
        imap_client.connect()
        emails = imap_client.get_emails_last_24h(days=days)
        imap_client.disconnect()

        if not emails:
            telegram_client.send_message("Aucun email trouvé", chat_id)
            return

        lines = [f"📧 {len(emails)} emails ({days}j):\n"]

        for idx, email in enumerate(emails, 1):
            from_full = email.get("from", "Unknown")
            email_match = re.search(r"<(.+?)>", from_full)
            if email_match:
                sender = email_match.group(1)
            else:
                email_pattern = re.search(r"[\w\.-]+@[\w\.-]+", from_full)
                sender = email_pattern.group() if email_pattern else from_full[:30]

            date_full = email.get("date", "")
            date_match = re.search(r"\d{1,2}\s+\w{3}", date_full)
            date_str = date_match.group() if date_match else date_full[:10]

            subject = email.get("subject", "Sans sujet")[:45]
            lines.append(f"{idx}. {sender} - {subject} ({date_str})")

        send_in_chunks(telegram_client, chat_id, lines)

    except Exception as e:
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)
