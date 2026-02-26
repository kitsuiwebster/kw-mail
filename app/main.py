# FastAPI server entry point for KW Email Reader Telegram bot.
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from app.config import AUTHORIZED_CHAT_IDS
from app.handlers.query import handle_query
from app.logger import logger
from app.mistral.client import MistralClient
from app.scheduler import run_summary
from app.telegram.client import TelegramClient
from app.telegram.commands import (
    handle_all,
    handle_help,
    handle_menu,
    handle_reset,
    handle_start,
    handle_summary,
    handle_today,
    handle_unknown_command,
)

# Load environment variables
load_dotenv()

app = FastAPI(title="KW Email Reader")

telegram_client = TelegramClient()
mistral_client = MistralClient()

conversation_history = {}
last_search_results = {}
summary_scheduler = None


def _schedule_daily_summaries():
    enabled = os.getenv("SUMMARY_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("Summary scheduler disabled")
        return None

    times = os.getenv("SUMMARY_CRON_TIMES", "09:00,21:00")
    tz = os.getenv("SUMMARY_TZ", "Europe/Paris")
    hours = int(os.getenv("SUMMARY_HOURS", "12"))

    scheduler = BackgroundScheduler(timezone=tz)
    for time_str in [t.strip() for t in times.split(",") if t.strip()]:
        hh, mm = time_str.split(":")
        trigger = CronTrigger(hour=int(hh), minute=int(mm), timezone=tz)
        scheduler.add_job(run_summary, trigger=trigger, args=[hours], id=f"summary_{hh}{mm}")

    scheduler.start()
    logger.info(f"Summary scheduler started | times={times} tz={tz} hours={hours}")
    return scheduler


@app.get("/")
async def root():
    # Health check endpoint
    return {"status": "ok", "service": "KW Email Reader"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Webhook endpoint for receiving Telegram updates
    try:
        data = await request.json()

        if "callback_query" in data:
            callback = data["callback_query"]
            message = callback.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))
            user_id = str(callback.get("from", {}).get("id", ""))
            data_str = callback.get("data", "")

            if chat_id not in AUTHORIZED_CHAT_IDS and user_id not in AUTHORIZED_CHAT_IDS:
                username = callback.get("from", {}).get("username", "unknown")
                logger.warning(f"Unauthorized callback denied | user={username} | chat={chat_id}")
                telegram_client.send_message("🚫 Accès non autorisé. Ce bot est privé.", chat_id)
                return {"ok": True}

            await handle_callback(data_str, chat_id)
            return {"ok": True}

        if "message" not in data:
            return {"ok": True}

        message = data["message"]
        chat_id = str(message["chat"]["id"])
        user_text = message.get("text", "")

        logger.info(f"Message received | chat={chat_id} | text='{user_text}'")

        if chat_id not in AUTHORIZED_CHAT_IDS:
            username = message.get("from", {}).get("username", "unknown")
            logger.warning(f"Unauthorized access denied | user={username} | chat={chat_id}")
            telegram_client.send_message("🚫 Accès non autorisé. Ce bot est privé.", chat_id)
            return {"ok": True}

        if user_text.startswith("/"):
            await handle_command(user_text, chat_id)
        else:
            await handle_query(
                user_text,
                chat_id,
                telegram_client,
                mistral_client,
                conversation_history,
                last_search_results,
            )

        return {"ok": True}

    except Exception as e:
        logger.error(f"Webhook processing failed | error={e}")
        return {"ok": False, "error": str(e)}


async def handle_command(command: str, chat_id: str):
    # Route commands to appropriate handlers
    if command == "/today":
        await handle_today(chat_id, telegram_client, last_search_results)
    elif command.startswith("/all") or command.startswith("/tous"):
        await handle_all(command, chat_id, telegram_client, last_search_results)
    elif command == "/summary":
        await handle_summary(chat_id, telegram_client, mistral_client)
    elif command == "/menu":
        await handle_menu(chat_id, telegram_client)
    elif command == "/start":
        await handle_start(chat_id, telegram_client)
    elif command == "/help":
        await handle_help(chat_id, telegram_client)
    elif command == "/reset":
        await handle_reset(chat_id, telegram_client, conversation_history)
    else:
        await handle_unknown_command(command, chat_id, telegram_client)


async def handle_callback(data_str: str, chat_id: str):
    # Handle inline button callbacks
    if data_str.startswith("body:") or data_str.startswith("eml:"):
        action, email_id = data_str.split(":", 1)
        if not email_id:
            telegram_client.send_message("Email introuvable.", chat_id)
            return

        telegram_client.send_message("🌀 Chargement...", chat_id)

        from app.email.imap_client import IMAPClient
        from app.telegram.commands._shared import send_in_chunks

        folder = None
        cached = last_search_results.get(chat_id, [])
        for email in cached:
            if email.get("id") == email_id:
                folder = email.get("folder")
                break

        imap_client = IMAPClient()
        imap_client.connect()
        raw_email = imap_client.get_email_raw_by_id(email_id, folder=folder)
        imap_client.disconnect()

        if not raw_email:
            telegram_client.send_message("Je n'ai pas pu récupérer le contenu.", chat_id)
            return

        if action == "eml":
            filename = f"email-{email_id}.eml"
            telegram_client.send_document(raw_email, filename, chat_id)
            return

        # action == "body"
        from email import policy
        from email.parser import BytesParser
        msg = BytesParser(policy=policy.default).parsebytes(raw_email)
        body = IMAPClient()._extract_body(msg)
        if not body:
            telegram_client.send_message("Email vide.", chat_id)
            return

        lines = ["📨 Body", ""]
        for chunk in [body[i : i + 3500] for i in range(0, len(body), 3500)]:
            lines.append(chunk)
        send_in_chunks(telegram_client, chat_id, lines)


@app.get("/webhook/info")
async def webhook_info():
    # Get current webhook configuration
    return telegram_client.get_webhook_info()


@app.on_event("startup")
async def _on_startup():
    global summary_scheduler
    summary_scheduler = _schedule_daily_summaries()


@app.on_event("shutdown")
async def _on_shutdown():
    if summary_scheduler:
        summary_scheduler.shutdown()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "uvicorn": {
                    "()": "app.logger.UvicornFormatter",
                },
            },
            "filters": {
                "skip_marked": {
                    "()": "app.logger.SkipMarkedFilter",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "uvicorn",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "filters": ["skip_marked"],
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},  # Skip normal HTTP logs
            },
        },
    )
