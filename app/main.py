import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from typing import Dict

from .telegram import TelegramClient
from .mistral_client import MistralClient
from .imap_client import IMAPClient
from .tools import TOOL_DEFINITIONS, execute_tool

# Load environment variables
load_dotenv()

app = FastAPI(title="KW Email Reader")

# Initialize clients
telegram_client = TelegramClient()
mistral_client = MistralClient()

# Whitelist of authorized chat IDs (only you can use the bot)
AUTHORIZED_CHAT_IDS = [os.getenv("TELEGRAM_CHAT_ID")]

# Conversation history storage (chat_id -> list of messages)
# Format: {chat_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
conversation_history = {}

# Last search results per chat (chat_id -> list of emails)
# Used to resolve "le 2e", "email #3", etc.
last_search_results = {}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "KW Email Reader"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Webhook endpoint for receiving Telegram updates.

    Telegram will POST updates here when users send messages to the bot.
    """
    try:
        data = await request.json()

        # Extract message
        if "message" not in data:
            return {"ok": True}

        message = data["message"]
        chat_id = str(message["chat"]["id"])
        user_text = message.get("text", "")

        print(f"Received message from {chat_id}: {user_text}")

        # Security: Check if user is authorized
        if chat_id not in AUTHORIZED_CHAT_IDS:
            username = message.get("from", {}).get("username", "unknown")
            print(f"⚠️  Unauthorized access attempt from {username} (chat_id: {chat_id})")
            telegram_client.send_message(
                "🚫 Accès non autorisé. Ce bot est privé.",
                chat_id
            )
            return {"ok": True}

        # Handle commands
        if user_text.startswith("/"):
            await handle_command(user_text, chat_id)
        else:
            # Send to Mistral for response
            await handle_query(user_text, chat_id)

        return {"ok": True}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"ok": False, "error": str(e)}


async def handle_command(command: str, chat_id: str):
    """Handle bot commands."""
    # Handle /today
    if command == "/today":
        # Show today's emails only
        try:
            from datetime import datetime
            import re

            telegram_client.send_message("⏳ Récupération des emails d'aujourd'hui...", chat_id)

            imap_client = IMAPClient()
            imap_client.connect()
            all_emails = imap_client.get_emails_last_24h(days=1)
            imap_client.disconnect()

            if not all_emails:
                telegram_client.send_message("Aucun email aujourd'hui", chat_id)
                return

            # Filter only today's emails
            today = datetime.now().date()
            today_emails = []

            for email in all_emails:
                date_str = email.get('date', '')
                date_match = re.search(r'\d{1,2}\s+\w{3}\s+\d{4}', date_str)
                if date_match:
                    try:
                        email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                        if email_date.date() == today:
                            today_emails.append(email)
                    except:
                        continue

            if not today_emails:
                telegram_client.send_message("Aucun email reçu aujourd'hui", chat_id)
                return

            # Format emails
            lines = [f"📧 {len(today_emails)} emails aujourd'hui:\n"]

            for idx, email in enumerate(today_emails, 1):
                # Extract email address
                from_full = email.get('from', 'Unknown')
                email_match = re.search(r'<(.+?)>', from_full)
                if email_match:
                    sender = email_match.group(1)
                else:
                    email_pattern = re.search(r'[\w\.-]+@[\w\.-]+', from_full)
                    sender = email_pattern.group() if email_pattern else from_full[:30]

                # Extract time
                date_full = email.get('date', '')
                time_match = re.search(r'(\d{2}:\d{2})', date_full)
                time_str = time_match.group() if time_match else ""

                subject = email.get('subject', 'Sans sujet')[:45]
                lines.append(f"{idx}. {sender} - {subject} ({time_str})")

            # Send in chunks
            full_text = "\n".join(lines)
            chunks = []
            current_chunk = ""

            for line in lines:
                if len(current_chunk) + len(line) + 1 > 4000:
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"

            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                telegram_client.send_message(chunk.strip(), chat_id)

        except Exception as e:
            telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)

    # Handle /all, /tous, /all 7, /all 30, etc.
    elif command.startswith("/all") or command.startswith("/tous"):
        # Direct listing of ALL emails - bypass AI
        try:
            # Parse days parameter
            parts = command.split()
            days = 1
            if len(parts) > 1:
                try:
                    days = int(parts[1])
                except ValueError:
                    days = 1

            telegram_client.send_message(f"⏳ Récupération de tous les emails ({days}j)...", chat_id)

            imap_client = IMAPClient()
            imap_client.connect()
            emails = imap_client.get_emails_last_24h(days=days)
            imap_client.disconnect()

            if not emails:
                telegram_client.send_message("Aucun email trouvé", chat_id)
                return

            # Format all emails with sender
            import re
            lines = [f"📧 {len(emails)} emails ({days}j):\n"]

            for idx, email in enumerate(emails, 1):
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

            # Split into chunks (Telegram limit: 4096 chars)
            full_text = "\n".join(lines)
            chunks = []
            current_chunk = ""

            for line in lines:
                if len(current_chunk) + len(line) + 1 > 4000:  # Safety margin
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"

            if current_chunk:
                chunks.append(current_chunk)

            # Send chunks
            for chunk in chunks:
                telegram_client.send_message(chunk.strip(), chat_id)

        except Exception as e:
            telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)

    elif command == "/menu":
        menu_text = """
📋 COMMANDES DISPONIBLES

📧 Lister les emails:
/today - Emails d'aujourd'hui uniquement
/all - Tous les emails (24h)
/all 7 - Tous les emails (7 jours)
/all 30 - Tous les emails (30 jours)

📊 Résumé:
/summary - Résumé IA des emails (24h)

🔧 Utilitaires:
/reset - Réinitialiser la conversation
/menu - Afficher ce menu
/help - Aide détaillée
        """
        telegram_client.send_message(menu_text, chat_id)

    elif command == "/start":
        welcome_text = """
🚀 Bienvenue sur KW Email Reader !

⚡ Commandes rapides :
/today - Emails d'aujourd'hui
/all - Tous les emails (24h)
/menu - Voir toutes les commandes
/help - Aide complète

💬 Questions naturelles :
• "mails de jeudi"
• "mails INPI du dernier mois"
• "lis le 2e email"

🧠 Je garde la mémoire de nos échanges
        """
        telegram_client.send_message(welcome_text, chat_id)

    elif command == "/summary":
        # Get email summary
        try:
            telegram_client.send_message("⏳ Récupération des emails...", chat_id)

            # Fetch emails
            imap_client = IMAPClient()
            imap_client.connect()
            emails = imap_client.get_emails_last_24h()
            imap_client.disconnect()

            if not emails:
                telegram_client.send_message("Aucun email reçu dans les dernières 24h.", chat_id)
                return

            # Generate summary
            summary = mistral_client.summarize_emails(emails)
            clean_summary = remove_markdown(summary)
            telegram_client.send_message(f"📊 Résumé des emails (24h)\n\n{clean_summary}", chat_id)

        except Exception as e:
            telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)

    elif command == "/help":
        help_text = """
📋 AIDE KW EMAIL READER

⚡ Commandes principales:
/menu - Liste complète des commandes
/today - Emails d'aujourd'hui uniquement
/all - Tous les emails (24h)
/all 7 - Tous les emails (semaine)
/summary - Résumé IA (24h)
/reset - Reset conversation

💬 Questions naturelles (IA):

📅 Par date:
• "mails de jeudi"
• "mails du 20 février"
• "mails d'hier"

🔍 Par contenu:
• "mails INPI"
• "mails Etsy du dernier mois"
• "ai-je reçu quelque chose d'urgent ?"

📧 Détails:
• "lis le 2"
• "détails du 5"

🧠 Mémoire: dites "le 2e" ou "celui-là"

🔍 Périodes supportées:
• "24h" / "aujourd'hui" / "hier"
• "jeudi" / "lundi" (jour précis)
• "semaine" / "7 jours"
• "mois" / "30 jours"
• "depuis lundi" (plage)
        """
        telegram_client.send_message(help_text, chat_id)

    elif command == "/reset":
        # Clear conversation history
        if chat_id in conversation_history:
            del conversation_history[chat_id]
        telegram_client.send_message("✓ Conversation réinitialisée !", chat_id)

    else:
        telegram_client.send_message(f"Commande inconnue : {command}\nUtilisez /help pour voir les commandes.", chat_id)


def remove_markdown(text: str) -> str:
    """Remove all markdown syntax from text."""
    import re
    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic (*text* or _text_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    # Remove code (`text`)
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove headers (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove links [text](url) → text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    return text


async def handle_query(query: str, chat_id: str):
    """
    Handle user queries using Mistral with tool calling.

    Mistral can call search_emails and get_full_email tools to answer questions.
    Maintains conversation history per chat_id.
    """
    try:
        telegram_client.send_message("⏳ Traitement de votre question...", chat_id)

        # Get or create conversation history for this chat
        if chat_id not in conversation_history:
            # Initialize with system message
            conversation_history[chat_id] = [
                {
                    "role": "system",
                    "content": """Assistant email. Aujourd'hui: dimanche 23 février 2026.

4 outils (UN SEUL appel par question):
1. list_emails_by_date(target_date, search_days) → emails d'UNE date précise
2. list_all_emails(days) → emails d'une PLAGE de jours
3. search_emails(query, max_results, days) → recherche par mot-clé
4. get_full_email(email_id, days) → contenu complet d'UN email

RÈGLE #1 - UN SEUL APPEL:
Choisis LE BON outil et appelle-le UNE FOIS. Pas 2, pas 3. UN.

RÈGLE #2 - Dates spécifiques vs plages:
- "mails de jeudi" / "mails du 20" → list_emails_by_date (UNE date)
- "tous les mails" / "depuis lundi" → list_all_emails (PLAGE)

Calcul dates (aujourd'hui = dim 23 fév 2026):
- "jeudi" = jeudi dernier = 20 fév → "2026-02-20"
- "lundi" = lundi dernier = 17 fév → "2026-02-17"
- "hier" = sam 22 fév → "2026-02-22"
- "20 février" → "2026-02-20"

Exemples CORRECTS:
User: "mails de jeudi"
→ list_emails_by_date("2026-02-20") [UN appel]

User: "tous les mails"
→ list_all_emails(1) [UN appel]

User: "mails INPI"
→ search_emails("INPI") [UN appel]

Les outils list_* envoient DIRECTEMENT. Tu réponds juste "✅".

ZERO markdown. UN SEUL appel outil.

"le 2" → email_id="2" """
                }
            ]

        # Add user message to history
        conversation_history[chat_id].append({
            "role": "user",
            "content": query
        })

        print(f"Processing query with tools (chat {chat_id}): {query}")
        print(f"Conversation history: {len(conversation_history[chat_id])} messages")

        # Track if list tools were used (to skip final response)
        list_tool_used = {"used": False}

        # Create tool executor wrapper to store search results
        def tool_executor_with_context(tool_name, arguments):
            result = execute_tool(tool_name, arguments)

            # Handle list tools - send directly and mark as used
            if tool_name in ["list_all_emails", "list_emails_by_date"] and isinstance(result, str):
                list_tool_used["used"] = True

                # Send result in chunks if too long
                if len(result) > 4000:
                    print(f"  → {tool_name} result too long ({len(result)} chars), sending in chunks")
                    chunks = []
                    current_chunk = ""

                    for line in result.split('\n'):
                        if len(current_chunk) + len(line) + 1 > 4000:
                            chunks.append(current_chunk)
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"

                    if current_chunk:
                        chunks.append(current_chunk)

                    # Send all chunks
                    for chunk in chunks:
                        telegram_client.send_message(chunk.strip(), chat_id)

                    # Return confirmation for Mistral (won't be sent to user)
                    return f"✅ Liste envoyée"
                else:
                    # Send directly
                    telegram_client.send_message(result, chat_id)
                    return f"✅ Liste envoyée"

            # Store search results for this chat
            if tool_name == "search_emails" and result:
                last_search_results[chat_id] = result
                print(f"  Stored {len(result)} search results for chat {chat_id}")

            # Store list results for "le 2" references
            if tool_name == "list_all_emails" and isinstance(result, str):
                # Store all emails for numeric references
                imap_client_temp = IMAPClient()
                imap_client_temp.connect()
                emails = imap_client_temp.get_emails_last_24h(days=arguments.get('days', 1))
                imap_client_temp.disconnect()
                last_search_results[chat_id] = emails
                print(f"  Stored {len(emails)} emails from list_all for chat {chat_id}")

            if tool_name == "list_emails_by_date" and isinstance(result, str):
                # Store filtered emails for numeric references
                imap_client_temp = IMAPClient()
                imap_client_temp.connect()
                all_emails = imap_client_temp.get_emails_last_24h(days=arguments.get('search_days', 7))
                imap_client_temp.disconnect()

                # Filter by date
                import re
                from datetime import datetime
                target_date = arguments.get('target_date', '')
                try:
                    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                    filtered = []
                    for email in all_emails:
                        date_str = email.get('date', '')
                        date_match = re.search(r'\d{1,2}\s+\w{3}\s+\d{4}', date_str)
                        if date_match:
                            try:
                                email_date = datetime.strptime(date_match.group(), "%d %b %Y")
                                if email_date.date() == target_dt.date():
                                    filtered.append(email)
                            except:
                                continue
                    last_search_results[chat_id] = filtered
                    print(f"  Stored {len(filtered)} emails from list_by_date for chat {chat_id}")
                except:
                    pass

            # If get_full_email with numeric reference (1, 2, 3), resolve it
            if tool_name == "get_full_email":
                email_id = arguments.get("email_id", "")
                # Check if it's a number or looks like "le 2", "email 3", etc.
                if chat_id in last_search_results:
                    try:
                        # Try to parse as index (1-based)
                        idx = int(email_id) - 1
                        if 0 <= idx < len(last_search_results[chat_id]):
                            real_id = last_search_results[chat_id][idx]['id']
                            print(f"  Resolved index {email_id} to ID {real_id}")
                            arguments["email_id"] = real_id
                            result = execute_tool(tool_name, arguments)
                    except ValueError:
                        pass

            return result

        # Call Mistral with full conversation history
        response = mistral_client.chat_with_tools(
            messages=conversation_history[chat_id],
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor_with_context
        )

        # Remove markdown from response
        clean_response = remove_markdown(response)

        # Add assistant response to history (keep original for context)
        conversation_history[chat_id].append({
            "role": "assistant",
            "content": response
        })

        # Limit history to last 10 messages (5 exchanges) + system message
        # Keep system message + last 10 messages
        if len(conversation_history[chat_id]) > 11:
            # Notify user about memory reset
            telegram_client.send_message("ℹ️ Mémoire réinitialisée (limite atteinte)", chat_id)

            conversation_history[chat_id] = [
                conversation_history[chat_id][0]  # Keep system message
            ] + conversation_history[chat_id][-10:]  # Keep last 10 messages

        # Send cleaned response to user ONLY if list tools weren't used
        if not list_tool_used["used"]:
            telegram_client.send_message(clean_response, chat_id)
        else:
            print(f"  ✓ Skipping final response (list tool already sent result)")

    except Exception as e:
        print(f"Error in handle_query: {e}")
        telegram_client.send_message(f"❌ Erreur : {str(e)}", chat_id)


@app.get("/webhook/info")
async def webhook_info():
    """Get current webhook configuration."""
    info = telegram_client.get_webhook_info()
    return info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
