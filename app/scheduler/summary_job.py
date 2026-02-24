# Scheduled summary job (last N hours).
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

from app.email.imap_client import IMAPClient
from app.logger import logger
from app.mistral.client import MistralClient
from app.telegram.client import TelegramClient


def _parse_email_dt(date_str: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(date_str)
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _filter_last_hours(emails: List[dict], hours: int) -> List[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for email in emails:
        dt = _parse_email_dt(email.get("date", ""))
        if dt and dt >= cutoff:
            recent.append(email)
    return recent


def run_summary(hours: int = 12) -> None:
    # Fetch emails and send summary to Telegram.
    try:
        telegram_client = TelegramClient()
        mistral_client = MistralClient()

        imap_client = IMAPClient()
        imap_client.connect()
        all_emails = imap_client.get_emails_last_24h(days=1)
        imap_client.disconnect()

        recent_emails = _filter_last_hours(all_emails, hours)
        summary = mistral_client.summarize_emails(recent_emails, window_label=f"{hours}h")
        telegram_client.send_message(summary)
        logger.info(f"Scheduled summary sent | hours={hours} count={len(recent_emails)}")
    except Exception as e:
        logger.error(f"Scheduled summary failed | error={e}")
