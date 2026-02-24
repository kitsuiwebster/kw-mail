from datetime import datetime
import re
import time

from app.email.imap_client import IMAPClient
from app.logger import logger
from app.telegram.client import TelegramClient
from app.telegram.commands._shared import send_in_chunks


async def handle_today(chat_id: str, telegram_client: TelegramClient, last_search_results: dict | None = None):
    # Handle /today command - show today's emails only
    try:
        start_ts = time.time()
        logger.info(f"Command /today started | chat={chat_id}")
        telegram_client.send_message("🌀 Chargement...", chat_id)
        sent_ts = time.time()
        logger.debug(f"/today loading sent | chat={chat_id} | dt={sent_ts - start_ts:.3f}s")

        imap_client = IMAPClient()
        imap_client.connect()
        all_emails = imap_client.get_emails_last_24h(days=1)
        imap_client.disconnect()
        imap_ts = time.time()
        logger.info(f"/today fetch complete | chat={chat_id} | imap_time={imap_ts - sent_ts:.3f}s | total={imap_ts - start_ts:.3f}s")

        if not all_emails:
            telegram_client.send_message("Aucun email aujourd'hui", chat_id)
            return

        today = datetime.now().date()
        today_emails = []

        for email in all_emails:
            date_str = email.get("date", "")
            date_match = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", date_str)
            if date_match:
                try:
                    email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                    if email_date.date() == today:
                        today_emails.append(email)
                except Exception:
                    continue

        if not today_emails:
            telegram_client.send_message("Aucun email reçu aujourd'hui", chat_id)
            return

        if last_search_results is not None:
            last_search_results[chat_id] = today_emails

        lines = [f"👉 {len(today_emails)} emails aujourd'hui:\n"]

        for idx, email in enumerate(today_emails, 1):
            from_full = email.get("from", "Unknown")
            email_match = re.search(r"<(.+?)>", from_full)
            if email_match:
                sender = email_match.group(1)
            else:
                email_pattern = re.search(r"[\w\.-]+@[\w\.-]+", from_full)
                sender = email_pattern.group() if email_pattern else from_full[:30]

            date_full = email.get("date", "")
            time_match = re.search(r"(\d{2}:\d{2})", date_full)
            time_str = time_match.group() if time_match else ""

            subject = email.get("subject", "Sans sujet")[:45]
            lines.append(f"{idx}. {sender} - {subject} ({time_str})")

        send_in_chunks(telegram_client, chat_id, lines)

    except Exception as e:
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)
