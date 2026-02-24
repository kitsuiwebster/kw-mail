# Tool definitions for Mistral function calling.

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
                        "default": "",
                    },
                    "search_days": {
                        "type": "integer",
                        "description": "How many days back to search (default: 7, max: 30)",
                        "default": 7,
                    },
                },
                "required": ["target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_emails",
            "description": "List ALL emails from last N days (range, not specific date). Use when user says: 'tous les mails', 'depuis lundi' (= range from Mon to today), 'dernière semaine', 'les 5 derniers mails'. Returns formatted string. DETERMINISTIC - ONE call only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Days back: 1 (24h), 7 (week), 30 (month). 'depuis lundi' (Mon to today) = count days.",
                        "default": 1,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Limit to N most recent emails. Use for 'les 5 derniers', 'les 10 derniers'. 0 = no limit (all). Default: 0",
                        "default": 0,
                    }
                },
                "required": [],
            },
        },
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
                        "default": "",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results. Default: 10.",
                        "default": 10,
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days back: 1 (24h), 7 (week), 30 (month). Default: 1",
                        "default": 1,
                    },
                },
                "required": [],
            },
        },
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
                        "description": "Email ID from search_emails or list_all_emails",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days back (must match previous search). Default: 1",
                        "default": 1,
                    },
                },
                "required": ["email_id"],
            },
        },
    },
]
