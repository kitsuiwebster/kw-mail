# Scheduled summary job (last N hours).
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Dict, List, Tuple

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


def _format_sender(from_full: str) -> str:
    email_match = re.search(r"<(.+?)>", from_full)
    if email_match:
        return email_match.group(1)
    email_pattern = re.search(r"[\w\.-]+@[\w\.-]+", from_full)
    return email_pattern.group() if email_pattern else from_full[:40]


def _format_time(date_str: str) -> str:
    dt = _parse_email_dt(date_str)
    if dt:
        try:
            return dt.astimezone().strftime("%H:%M")
        except Exception:
            return dt.strftime("%H:%M")
    time_match = re.search(r"(\d{2}:\d{2})", date_str)
    return time_match.group() if time_match else ""


def _build_summary_lines(emails: List[Dict], hours: int, important_info: Dict) -> List[str]:
    lines = [f"🕘 Résumé des {hours} dernières heures", ""]

    important_items = important_info.get("important", []) if isinstance(important_info, dict) else []
    important_map: List[Tuple[int, str]] = []
    for item in important_items:
        try:
            idx = int(item.get("index", 0))
            explanation = (item.get("explanation") or "").strip()
            if idx > 0:
                important_map.append((idx, explanation))
        except Exception:
            continue

    important_idx_set = {idx for idx, _ in important_map}

    lines.append("📌 Emails importants et pertinents:")
    if not important_map:
        lines.append("Aucun email important.")
    else:
        for pos, (idx, explanation) in enumerate(important_map, 1):
            if idx < 1 or idx > len(emails):
                continue
            email = emails[idx - 1]
            sender = _format_sender(email.get("from", "Unknown"))
            subject = email.get("subject", "Sans sujet")
            time_str = _format_time(email.get("date", ""))
            explanation_part = explanation if explanation else f"À vérifier: {subject}"
            lines.append(f"{pos}. {explanation_part} — {sender} | {subject} | {time_str}")

    lines.append("")
    lines.append(f"📭 Autres emails ({hours}h):")
    other_emails = []
    for idx, email in enumerate(emails, 1):
        if idx in important_idx_set:
            continue
        other_emails.append(email)

    if not other_emails:
        lines.append("Aucun autre email.")
    else:
        for idx, email in enumerate(other_emails, 1):
            sender = _format_sender(email.get("from", "Unknown"))
            subject = email.get("subject", "Sans sujet")
            time_str = _format_time(email.get("date", ""))
            lines.append(f"{idx}. {sender} | {subject} | {time_str}")

    return lines


def generate_summary_lines(hours: int = 12) -> List[str]:
    # Build summary lines for the last N hours.
    mistral_client = MistralClient()

    imap_client = IMAPClient()
    imap_client.connect()
    all_emails = imap_client.get_emails_last_24h(days=1)
    imap_client.disconnect()

    recent_emails = _filter_last_hours(all_emails, hours)
    if recent_emails:
        recent_emails.sort(
            key=lambda e: _parse_email_dt(e.get("date", "")) or datetime.min,
            reverse=True,
        )

    important_info = mistral_client.classify_important_emails(
        recent_emails,
        window_label=f"{hours}h",
    )
    return _build_summary_lines(recent_emails, hours, important_info)


def run_summary(hours: int = 12) -> None:
    # Fetch emails and send summary to Telegram.
    try:
        telegram_client = TelegramClient()
        lines = generate_summary_lines(hours)

        message = "\n".join(lines)
        if len(message) <= 3900:
            telegram_client.send_message(message)
        else:
            from app.telegram.commands._shared import send_in_chunks

            send_in_chunks(telegram_client, telegram_client.chat_id, lines)

        logger.info(f"Scheduled summary sent | hours={hours}")
    except Exception as e:
        logger.error(f"Scheduled summary failed | error={e}")
