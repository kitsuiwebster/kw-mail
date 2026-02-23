"""
Email tools for LLM to search and retrieve emails.

These tools are called by Mistral when the user asks questions about their emails.
"""

from typing import List, Dict, Optional
from .imap_client import IMAPClient


def search_emails(query: str = "", max_results: int = 10, days: int = 1) -> List[Dict]:
    """
    Search for emails matching the query.

    Searches in:
    - From (sender email/name)
    - Subject
    - Body content (case-insensitive)

    Args:
        query: Search term (e.g., "INPI", "john@example.com", "urgent").
               If empty or very short, returns all emails.
        max_results: Maximum number of results to return (default: 10)
        days: Number of days to look back (default: 1 = last 24h)

    Returns:
        List of matching emails with: id, from, subject, date, cc, preview (first 100 chars of body)
    """
    imap_client = IMAPClient()
    imap_client.connect()

    # Get emails from last N days
    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return []

    # If query is empty or very short (1-2 chars), return all emails
    if not query or len(query.strip()) <= 2:
        # Return all emails (limited by max_results)
        matching_emails = []
        for email in all_emails[:max_results]:
            body_preview = email.get('body', '')[:100].strip()
            matching_emails.append({
                'id': email['id'],
                'from': email['from'],
                'subject': email['subject'],
                'date': email['date'],
                'cc': email.get('cc', ''),
                'preview': body_preview
            })
        print(f"  → Returning {len(matching_emails)} emails (from {len(all_emails)} total)")
        return matching_emails

    # Filter emails matching query (case-insensitive)
    query_lower = query.lower()
    matching_emails = []

    for email in all_emails:
        # Search in From, Subject, and Body
        from_field = email.get('from', '').lower()
        subject_field = email.get('subject', '').lower()
        body_field = email.get('body', '').lower()

        if (query_lower in from_field or
            query_lower in subject_field or
            query_lower in body_field):

            # Return headers + body preview (first 100 chars)
            body_preview = email.get('body', '')[:100].strip()
            matching_emails.append({
                'id': email['id'],
                'from': email['from'],
                'subject': email['subject'],
                'date': email['date'],
                'cc': email.get('cc', ''),
                'preview': body_preview  # Add preview
            })

            if len(matching_emails) >= max_results:
                break

    return matching_emails


def list_emails_by_date(target_date: str, search_days: int = 7) -> str:
    """
    List emails from a specific date only.

    Args:
        target_date: Date in format "YYYY-MM-DD" (e.g., "2026-02-20")
        search_days: How many days back to search (default: 7)

    Returns:
        Formatted string with emails from that specific date
    """
    import re
    from datetime import datetime

    imap_client = IMAPClient()
    imap_client.connect()
    all_emails = imap_client.get_emails_last_24h(days=search_days)
    imap_client.disconnect()

    if not all_emails:
        return f"Aucun email trouvé pour {target_date}"

    # Parse target date
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    except:
        return f"Format de date invalide: {target_date} (attendu: YYYY-MM-DD)"

    # Filter emails matching the target date
    matching_emails = []
    for email in all_emails:
        date_str = email.get('date', '')
        # Try to extract date from email header (various formats)
        # Common format: "Thu, 20 Feb 2026 14:30:00 +0100"
        date_match = re.search(r'\d{1,2}\s+\w{3}\s+\d{4}', date_str)
        if date_match:
            try:
                email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                if email_date.date() == target_dt.date():
                    matching_emails.append(email)
            except:
                continue

    if not matching_emails:
        return f"Aucun email trouvé pour le {target_dt.strftime('%d %b %Y')}"

    # Format matched emails
    lines = [f"📧 {len(matching_emails)} emails du {target_dt.strftime('%d %b %Y')}:\n"]

    for idx, email in enumerate(matching_emails, 1):
        # Extract full email address
        from_full = email.get('from', 'Unknown')
        email_match = re.search(r'<(.+?)>', from_full)
        if email_match:
            sender = email_match.group(1)
        else:
            email_pattern = re.search(r'[\w\.-]+@[\w\.-]+', from_full)
            sender = email_pattern.group() if email_pattern else from_full[:30]

        # Subject (truncate)
        subject = email.get('subject', 'Sans sujet')[:45]

        # Extract time from date
        date_full = email.get('date', '')
        time_match = re.search(r'(\d{2}:\d{2})', date_full)
        time_str = time_match.group() if time_match else ""

        lines.append(f"{idx}. {sender} - {subject} ({time_str})")

    return "\n".join(lines)


def list_all_emails(days: int = 1) -> str:
    """
    List ALL emails in a formatted string (deterministic output).

    This bypasses search limits and returns a complete formatted list.
    Used when user explicitly asks for "tous", "all", "liste complète", etc.

    Args:
        days: Number of days to look back (default: 1 = last 24h)

    Returns:
        Formatted string with ALL emails numbered and ready to send to user
    """
    import re

    imap_client = IMAPClient()
    imap_client.connect()
    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    if not all_emails:
        return f"Aucun email trouvé ({days}j)"

    # Format all emails with sender
    lines = [f"📧 {len(all_emails)} emails ({days}j):\n"]

    for idx, email in enumerate(all_emails, 1):
        # Extract full email address
        from_full = email.get('from', 'Unknown')
        # Extract email between < > or just the email
        email_match = re.search(r'<(.+?)>', from_full)
        if email_match:
            sender = email_match.group(1)
        else:
            # Try to find email pattern
            email_pattern = re.search(r'[\w\.-]+@[\w\.-]+', from_full)
            sender = email_pattern.group() if email_pattern else from_full[:30]

        # Extract short date
        date_full = email.get('date', '')
        date_match = re.search(r'\d{1,2}\s+\w{3}', date_full)
        date_str = date_match.group() if date_match else date_full[:10]

        # Subject (truncate)
        subject = email.get('subject', 'Sans sujet')[:45]

        lines.append(f"{idx}. {sender} - {subject} ({date_str})")

    return "\n".join(lines)


def get_full_email(email_id: str, days: int = 1) -> Optional[Dict]:
    """
    Retrieve the full content of a specific email.

    Args:
        email_id: Email ID returned from search_emails
        days: Number of days to look back (default: 1 = last 24h)

    Returns:
        Full email with all fields including body, or None if not found
    """
    imap_client = IMAPClient()
    imap_client.connect()

    # Get all emails from last N days
    all_emails = imap_client.get_emails_last_24h(days=days)
    imap_client.disconnect()

    # Find the email with matching ID
    for email in all_emails:
        if email['id'] == email_id:
            return email

    return None


# Tool definitions for Mistral
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_emails_by_date",
            "description": "List emails from a SPECIFIC date only (not a range). Use when user asks for emails from ONE specific day: 'jeudi', 'lundi', '20 février', 'hier'. Returns formatted string. DETERMINISTIC - ONE call only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Examples: 'jeudi' (today=2026-02-23, last Thu=2026-02-20) → '2026-02-20'. 'lundi' → '2026-02-17'. 'hier' (yesterday) → '2026-02-22'. You MUST calculate the date.",
                        "default": ""
                    },
                    "search_days": {
                        "type": "integer",
                        "description": "How many days back to search (default: 7, max: 30)",
                        "default": 7
                    }
                },
                "required": ["target_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_emails",
            "description": "List ALL emails from last N days (range, not specific date). Use when user says: 'tous les mails', 'depuis lundi' (= range from Mon to today), 'dernière semaine'. Returns formatted string. DETERMINISTIC - ONE call only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Days back: 1 (24h), 7 (week), 30 (month). 'depuis lundi' (Mon to today) = count days.",
                        "default": 1
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search emails by keyword. Returns: id, from, subject, date, preview. Use for SPECIFIC searches (ex: 'INPI', 'urgent', 'Netflix'). NOT for 'tous' or 'all' (use list_all_emails instead).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term. Examples: 'INPI', 'urgent', 'john@example.com'.",
                        "default": ""
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results. Default: 10.",
                        "default": 10
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days back: 1 (24h), 7 (week), 30 (month). Default: 1",
                        "default": 1
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_full_email",
            "description": "Get FULL body of ONE email. ONLY use if user explicitly asks: 'lis le 2', 'détails du 3', 'contenu complet', 'le 2e'. DO NOT use for listing emails. Requires email_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Email ID from search_emails or list_all_emails"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days back (must match previous search). Default: 1",
                        "default": 1
                    }
                },
                "required": ["email_id"]
            }
        }
    }
]


# Tool execution mapping
TOOL_FUNCTIONS = {
    "list_emails_by_date": list_emails_by_date,
    "list_all_emails": list_all_emails,
    "search_emails": search_emails,
    "get_full_email": get_full_email
}


def execute_tool(tool_name: str, arguments: dict) -> any:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        Tool execution result
    """
    if tool_name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_func = TOOL_FUNCTIONS[tool_name]
    return tool_func(**arguments)


if __name__ == "__main__":
    # Quick test
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing search_emails...")
    results = search_emails("INPI")
    print(f"Found {len(results)} emails matching 'INPI'")
    for email in results:
        print(f"  - {email['subject']} from {email['from']}")

    print()
    print("Testing get_full_email...")
    if results:
        email_id = results[0]['id']
        full_email = get_full_email(email_id)
        if full_email:
            print(f"Retrieved email: {full_email['subject']}")
            print(f"Body preview: {full_email['body'][:200]}...")
