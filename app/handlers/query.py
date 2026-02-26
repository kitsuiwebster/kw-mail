# Query handler for natural language email queries with AI tool calling.
import re
from datetime import datetime

from app.email.imap_client import IMAPClient
from app.logger import logger
from app.mistral.client import MistralClient
from app.mistral.prompts import SYSTEM_PROMPT
from app.mistral.tool_definitions import TOOL_DEFINITIONS
from app.mistral.tools import execute_tool, search_emails_by_address
from app.telegram.client import TelegramClient
from app.telegram.commands._shared import send_in_chunks
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
        def _split_text(text: str, chunk_size: int = 3500) -> list[str]:
            if not text:
                return []
            return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

        def _send_email_list_with_prompt(
            emails: list[dict],
            header: str,
            chat_id: str,
        ):
            lines = [header, ""]
            for idx, email in enumerate(emails, 1):
                from_full = email.get("from", "Unknown")
                subject = email.get("subject", "Sans sujet")
                date = email.get("date", "Unknown")
                lines.append(f"{idx}. {from_full}")
                lines.append(f"Sujet : {subject}")
                lines.append(f"Date : {date}")
                lines.append("")
            send_in_chunks(telegram_client, chat_id, lines)

        normalized_query = query.strip().lower()

        # Direct email address search to avoid extra tool calls
        email_match = re.search(r"[\w\.-]+@[\w\.-]+", normalized_query)
        if email_match:
            telegram_client.send_message("✨ Chargement...", chat_id)
            address = email_match.group(0)
            results = search_emails_by_address(address=address, max_results=10, days=7)
            if results:
                last_search_results[chat_id] = results
                logger.info(f"Search by address (direct) | chat={chat_id} | count={len(results)}")
                header = f"📌 {len(results)} email(s) trouvé(s) pour cette adresse :"
                _send_email_list_with_prompt(results, header, chat_id)
            else:
                telegram_client.send_message("Aucun email trouvé pour cette adresse.", chat_id)
            return

        if normalized_query in {"oui", "ok", "okay", "vas-y", "oui vas-y", "lis", "lis-le", "lis le", "li le", "lire", "go"}:
            if chat_id in last_search_results:
                cached = last_search_results[chat_id]
                if len(cached) == 1:
                    email_id = cached[0].get("id")
                    if email_id:
                        imap_client = IMAPClient()
                        imap_client.connect()
                        full_email = None
                        for days in (7, 30):
                            full_email = None
                            for email in imap_client.get_emails_last_24h(days=days):
                                if email.get("id") == email_id:
                                    full_email = email
                                    break
                            if full_email:
                                break
                        imap_client.disconnect()

                        if full_email:
                            from_full = full_email.get("from", "Unknown")
                            subject = full_email.get("subject", "Sans sujet")
                            date = full_email.get("date", "Unknown")
                            cc = full_email.get("cc", "")
                            folder = full_email.get("folder", "")
                            body = (full_email.get("body", "") or "").strip()
                            preview = body[:4000] + ("…" if len(body) > 4000 else "")

                            lines = [
                                "📨 Email",
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
                                lines.extend(_split_text(preview))

                            send_in_chunks(telegram_client, chat_id, lines)
                            return

                        telegram_client.send_message(
                            "Je n'ai pas pu récupérer le contenu. Dis-moi par exemple: \"lis le 1\".",
                            chat_id,
                        )
                        return
                elif len(cached) > 1:
                    telegram_client.send_message(
                        "Je peux le lire, mais indique le numéro (ex: \"lis le 2\").",
                        chat_id,
                    )
                    return

        m = re.match(r"^\s*(?:c[' ]?quoi|cest\s*quoi|quoi|quel\s+est)?\s*(?:le|la)?\s*(\d{1,3})\s*\??\s*$", query.lower())
        if m and chat_id in last_search_results:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(last_search_results[chat_id]):
                telegram_client.send_message("🌀 Chargement...", chat_id)
                cached = last_search_results[chat_id][idx]
                email_id = cached.get("id")
                if not email_id:
                    telegram_client.send_message("Email introuvable. Essaie un autre numéro.", chat_id)
                    return

                imap_client = IMAPClient()
                imap_client.connect()
                full_email = None
                for days in (7, 30):
                    for email in imap_client.get_emails_last_24h(days=days):
                        if email.get("id") == email_id:
                            full_email = email
                            break
                    if full_email:
                        break
                imap_client.disconnect()

                if not full_email:
                    telegram_client.send_message("Je n'ai pas pu récupérer le contenu complet.", chat_id)
                    return

                summary = mistral_client.summarize_email(full_email)
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "Body", "callback_data": f"body:{email_id}"}]
                    ]
                }
                telegram_client.send_message(summary, chat_id, reply_markup=reply_markup)
                return

        telegram_client.send_message("✨ Chargement...", chat_id)

        if chat_id not in conversation_history:
            conversation_history[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        conversation_history[chat_id].append({"role": "user", "content": query})

        logger.info(f"Query processing | chat={chat_id} | query='{query}' | history={len(conversation_history[chat_id])} msgs")

        list_tool_used = {"used": False}

        def tool_executor_with_context(tool_name, arguments):
            result = execute_tool(tool_name, arguments)

            if tool_name in ["list_all_emails", "list_emails_by_date"] and isinstance(result, str):
                list_tool_used["used"] = True

                if len(result) > 4000:
                    logger.info(f"Tool result chunked | tool={tool_name} | size={len(result)} chars")
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
                logger.info(f"Search results cached | chat={chat_id} | count={len(result)}")
            if tool_name == "search_emails_by_address" and result:
                last_search_results[chat_id] = result
                logger.info(f"Search by address cached | chat={chat_id} | count={len(result)}")
                list_tool_used["used"] = True
                header = f"📌 {len(result)} email(s) trouvé(s) pour cette adresse :"
                _send_email_list_with_prompt(result, header, chat_id)
                return "✅ Liste envoyée"

            if tool_name == "list_all_emails" and isinstance(result, str):
                imap_client_temp = IMAPClient()
                imap_client_temp.connect()
                emails = imap_client_temp.get_emails_last_24h(days=arguments.get("days", 1))
                imap_client_temp.disconnect()
                last_search_results[chat_id] = emails
                logger.info(f"List results cached | chat={chat_id} | count={len(emails)}")

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
                    logger.info(f"Filtered results cached | chat={chat_id} | count={len(filtered)}")
                except Exception:
                    pass

            if tool_name == "get_full_email":
                email_id = arguments.get("email_id", "")
                if chat_id in last_search_results:
                    try:
                        idx = int(email_id) - 1
                        if 0 <= idx < len(last_search_results[chat_id]):
                            real_id = last_search_results[chat_id][idx]["id"]
                            logger.info(f"Email index resolved | index={email_id} | id={real_id}")
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
            telegram_client.send_message("🧠 Mémoire réinitialisée (limite atteinte)", chat_id)
            conversation_history[chat_id] = [conversation_history[chat_id][0]]

        if not list_tool_used["used"]:
            telegram_client.send_message(clean_response, chat_id)
        else:
            logger.info(f"Response skipped | chat={chat_id} | reason=list_tool_sent")

    except Exception as e:
        logger.error(f"Query handling failed | chat={chat_id} | error={e}")
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)
