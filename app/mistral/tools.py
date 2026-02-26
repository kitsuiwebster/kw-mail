# Email tools for LLM to search and retrieve emails.
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from app.email.imap_client import IMAPClient
from app.logger import logger
from app.mistral.tool_definitions import TOOL_DEFINITIONS


def search_emails(query: str = "", max_results: int = 10, days: int = 1) -> List[Dict]:
    # Search for emails matching the query in from/subject/body
    imap_client = IMAPClient()
    imap_client.connect()

    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return []

    if not query or len(query.strip()) <= 2:
        matching_emails = []
        for email in all_emails[:max_results]:
            body_preview = email.get("body", "")[:100].strip()
            matching_emails.append(
                {
                    "id": email["id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "date": email["date"],
                    "cc": email.get("cc", ""),
                    "preview": body_preview,
                    "folder": email.get("folder", ""),
                }
            )
        logger.info(f"Search complete | matched={len(matching_emails)} | total={len(all_emails)}")
        return matching_emails

    query_lower = query.lower()
    matching_emails = []

    for email in all_emails:
        from_field = email.get("from", "").lower()
        subject_field = email.get("subject", "").lower()
        body_field = email.get("body", "").lower()

        if query_lower in from_field or query_lower in subject_field or query_lower in body_field:
            body_preview = email.get("body", "")[:100].strip()
            matching_emails.append(
                {
                    "id": email["id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "date": email["date"],
                    "cc": email.get("cc", ""),
                    "preview": body_preview,
                    "folder": email.get("folder", ""),
                }
            )

            if len(matching_emails) >= max_results:
                break

    return matching_emails


def _extract_email_address(from_field: str) -> str:
    import re

    if not from_field:
        return ""

    email_match = re.search(r"<(.+?)>", from_field)
    if email_match:
        return email_match.group(1).strip().lower()

    email_pattern = re.search(r"[\w\.-]+@[\w\.-]+", from_field)
    return email_pattern.group().strip().lower() if email_pattern else ""


def search_emails_by_address(address: str = "", max_results: int = 10, days: int = 1) -> List[Dict]:
    # Search emails by sender email address
    imap_client = IMAPClient()
    imap_client.connect()

    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return []

    address = (address or "").strip().lower()
    if not address:
        return []

    matching_emails = []
    for email in all_emails:
        from_field = email.get("from", "")
        sender_addr = _extract_email_address(from_field)
        if not sender_addr:
            continue

        if address in sender_addr or sender_addr in address or address in from_field.lower():
            body_preview = email.get("body", "")[:100].strip()
            matching_emails.append(
                {
                    "id": email["id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "date": email["date"],
                    "cc": email.get("cc", ""),
                    "preview": body_preview,
                    "folder": email.get("folder", ""),
                }
            )

            if len(matching_emails) >= max_results:
                break

    return matching_emails


def list_emails_by_date(target_date: str, search_days: int = 7) -> str:
    # List emails from one specific date
    import re
    from datetime import datetime

    imap_client = IMAPClient()
    imap_client.connect()
    all_emails = imap_client.get_emails_last_24h(days=search_days)
    imap_client.disconnect()

    if not all_emails:
        return f"Aucun email trouvé pour {target_date}"

    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    except Exception:
        return f"Format de date invalide: {target_date} (attendu: YYYY-MM-DD)"

    matching_emails = []
    for email in all_emails:
        date_str = email.get("date", "")
        date_match = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", date_str)
        if date_match:
            try:
                email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                if email_date.date() == target_dt.date():
                    matching_emails.append(email)
            except Exception:
                continue

    if not matching_emails:
        return f"Aucun email trouvé pour le {target_dt.strftime('%d %b %Y')}"

    lines = [f"📌 {len(matching_emails)} emails du {target_dt.strftime('%d %b %Y')}:\n"]

    for idx, email in enumerate(matching_emails, 1):
        from_full = email.get("from", "Unknown")
        email_match = re.search(r"<(.+?)>", from_full)
        if email_match:
            sender = email_match.group(1)
        else:
            email_pattern = re.search(r"[\w\.-]+@[\w\.-]+", from_full)
            sender = email_pattern.group() if email_pattern else from_full[:30]

        subject = email.get("subject", "Sans sujet")[:45]

        date_full = email.get("date", "")
        time_match = re.search(r"(\d{2}:\d{2})", date_full)
        time_str = time_match.group() if time_match else ""

        lines.append(f"{idx}. {sender} - {subject} ({time_str})")

    return "\n".join(lines)


def list_all_emails(days: int = 1, max_results: int = 0) -> str:
    # List all emails over a date range (optionally limit to max_results most recent)
    import re

    imap_client = IMAPClient()
    imap_client.connect()
    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return f"Aucun email trouvé ({days}j)"

    # Limit to max_results if specified (most recent first)
    emails_to_show = all_emails[:max_results] if max_results > 0 else all_emails

    if max_results > 0:
        lines = [f"📌 {len(emails_to_show)} derniers emails ({days}j):\n"]
    else:
        lines = [f"📌 {len(emails_to_show)} emails ({days}j):\n"]

    for idx, email in enumerate(emails_to_show, 1):
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

    return "\n".join(lines)


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


def _filter_last_hours(emails: List[Dict], hours: int) -> List[Dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for email in emails:
        dt = _parse_email_dt(email.get("date", ""))
        if dt and dt >= cutoff:
            recent.append(email)
    return recent


def list_emails_last_hours(hours: int = 12, max_results: int = 0) -> str:
    # List all emails from the last N hours (rolling window)
    import math
    import re

    if hours <= 0:
        return "Heures invalides (doit être > 0)"

    imap_client = IMAPClient()
    imap_client.connect()
    days = max(1, int(math.ceil(hours / 24)))
    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return f"Aucun email trouvé ({hours}h)"

    recent_emails = _filter_last_hours(all_emails, hours)
    if not recent_emails:
        return f"Aucun email trouvé ({hours}h)"

    # Most recent first
    recent_emails.sort(key=lambda e: _parse_email_dt(e.get("date", "")) or datetime.min, reverse=True)

    emails_to_show = recent_emails[:max_results] if max_results > 0 else recent_emails

    if max_results > 0:
        lines = [f"📌 {len(emails_to_show)} derniers emails ({hours}h):\n"]
    else:
        lines = [f"📌 {len(emails_to_show)} emails ({hours}h):\n"]

    for idx, email in enumerate(emails_to_show, 1):
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

    return "\n".join(lines)


def get_full_email(email_id: str, days: int = 1) -> Optional[Dict]:
    # Retrieve the full content of a specific email
    imap_client = IMAPClient()
    imap_client.connect()

    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    for email in all_emails:
        if email["id"] == email_id:
            return email

    return None


TOOL_FUNCTIONS = {
    "list_emails_by_date": list_emails_by_date,
    "list_all_emails": list_all_emails,
    "list_emails_last_hours": list_emails_last_hours,
    "search_emails": search_emails,
    "search_emails_by_address": search_emails_by_address,
    "get_full_email": get_full_email,
}


def execute_tool(tool_name: str, arguments: dict) -> any:
    # Execute a tool by name with given arguments
    if tool_name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_func = TOOL_FUNCTIONS[tool_name]
    return tool_func(**arguments)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    logger.info("Testing search_emails...")
    results = search_emails("INPI")
    logger.info(f"Found {len(results)} emails matching 'INPI'")
    for email in results:
        logger.info(f"  - {email['subject']} from {email['from']}")

    logger.info("")
    logger.info("Testing get_full_email...")
    if results:
        email_id = results[0]["id"]
        full_email = get_full_email(email_id)
        if full_email:
            logger.info(f"Retrieved email: {full_email['subject']}")
            logger.info(f"Body preview: {full_email['body'][:200]}...")
