# Query handler for natural language email queries with AI tool calling.
import re
from datetime import datetime

from app.email.imap_client import IMAPClient
from app.mistral.client import MistralClient
from app.mistral.prompts import SYSTEM_PROMPT
from app.mistral.tool_definitions import TOOL_DEFINITIONS
from app.mistral.tools import execute_tool
from app.telegram.client import TelegramClient
from app.utils import remove_markdown


async def handle_query(
    query: str,
    chat_id: str,
    telegram_client: TelegramClient,
    mistral_client: MistralClient,
    conversation_history: dict,
    last_search_results: dict,
):
    # Handle user queries using Mistral with tool calling
    try:
        # Fast path: numeric follow-up like "c quoi le 13 ?" -> use last list without LLM
        m = re.match(r"^\s*(?:c[' ]?quoi|cest\s*quoi|quoi|quel\s+est)?\s*(?:le|la)?\s*(\d{1,3})\s*\??\s*$", query.lower())
        if m and chat_id in last_search_results:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(last_search_results[chat_id]):
                email = last_search_results[chat_id][idx]
                from_full = email.get("from", "Unknown")
                subject = email.get("subject", "Sans sujet")
                date = email.get("date", "Unknown")
                cc = email.get("cc", "")
                folder = email.get("folder", "")
                body = (email.get("body", "") or "").strip()
                preview = body[:1200] + ("…" if len(body) > 1200 else "")

                lines = [
                    f"📨 Email #{idx+1}",
                    f"De: {from_full}",
                    f"Sujet: {subject}",
                    f"Date: {date}",
                ]
                if cc:
                    lines.append(f"CC: {cc}")
                if folder:
                    lines.append(f"Dossier: {folder}")
                if preview:
                    lines.append("")
                    lines.append(preview)

                telegram_client.send_message("\n".join(lines), chat_id)
                return

        telegram_client.send_message("Chargement...", chat_id)

        if chat_id not in conversation_history:
            conversation_history[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        conversation_history[chat_id].append({"role": "user", "content": query})

        print(f"Processing query with tools (chat {chat_id}): {query}")
        print(f"Conversation history: {len(conversation_history[chat_id])} messages")

        list_tool_used = {"used": False}

        def tool_executor_with_context(tool_name, arguments):
            result = execute_tool(tool_name, arguments)

            if tool_name in ["list_all_emails", "list_emails_by_date"] and isinstance(result, str):
                list_tool_used["used"] = True

                if len(result) > 4000:
                    print(f"  → {tool_name} result too long ({len(result)} chars), sending in chunks")
                    chunks = []
                    current_chunk = ""

                    for line in result.split("\n"):
                        if len(current_chunk) + len(line) + 1 > 4000:
                            chunks.append(current_chunk)
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"

                    if current_chunk:
                        chunks.append(current_chunk)

                    for chunk in chunks:
                        telegram_client.send_message(chunk.strip(), chat_id)

                    return "✅ Liste envoyée"

                telegram_client.send_message(result, chat_id)
                return "✅ Liste envoyée"

            if tool_name == "search_emails" and result:
                last_search_results[chat_id] = result
                print(f"  Stored {len(result)} search results for chat {chat_id}")

            if tool_name == "list_all_emails" and isinstance(result, str):
                imap_client_temp = IMAPClient()
                imap_client_temp.connect()
                emails = imap_client_temp.get_emails_last_24h(days=arguments.get("days", 1))
                imap_client_temp.disconnect()
                last_search_results[chat_id] = emails
                print(f"  Stored {len(emails)} emails from list_all for chat {chat_id}")

            if tool_name == "list_emails_by_date" and isinstance(result, str):
                imap_client_temp = IMAPClient()
                imap_client_temp.connect()
                all_emails = imap_client_temp.get_emails_last_24h(days=arguments.get("search_days", 7))
                imap_client_temp.disconnect()

                target_date = arguments.get("target_date", "")
                try:
                    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                    filtered = []
                    for email in all_emails:
                        date_str = email.get("date", "")
                        date_match = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", date_str)
                        if date_match:
                            try:
                                email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                                if email_date.date() == target_dt.date():
                                    filtered.append(email)
                            except Exception:
                                continue
                    last_search_results[chat_id] = filtered
                    print(f"  Stored {len(filtered)} emails from list_by_date for chat {chat_id}")
                except Exception:
                    pass

            if tool_name == "get_full_email":
                email_id = arguments.get("email_id", "")
                if chat_id in last_search_results:
                    try:
                        idx = int(email_id) - 1
                        if 0 <= idx < len(last_search_results[chat_id]):
                            real_id = last_search_results[chat_id][idx]["id"]
                            print(f"  Resolved index {email_id} to ID {real_id}")
                            arguments["email_id"] = real_id
                            result = execute_tool(tool_name, arguments)
                    except ValueError:
                        pass

            return result

        response = mistral_client.chat_with_tools(
            messages=conversation_history[chat_id],
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor_with_context,
        )

        clean_response = remove_markdown(response)

        conversation_history[chat_id].append({"role": "assistant", "content": response})

        # Reset after 10 full exchanges (user+assistant). System + 20 messages.
        max_messages = 21
        if len(conversation_history[chat_id]) > max_messages:
            telegram_client.send_message("ℹ️ Mémoire réinitialisée (limite atteinte)", chat_id)
            conversation_history[chat_id] = [conversation_history[chat_id][0]]

        if not list_tool_used["used"]:
            telegram_client.send_message(clean_response, chat_id)
        else:
            print("  ✓ Skipping final response (list tool already sent result)")

    except Exception as e:
        print(f"Error in handle_query: {e}")
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)
