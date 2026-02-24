# FastAPI server entry point for KW Email Reader Telegram bot.
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from app.config import AUTHORIZED_CHAT_IDS
from app.handlers.query import handle_query
from app.logger import logger
from app.mistral.client import MistralClient
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


@app.get("/")
async def root():
    # Health check endpoint
    return {"status": "ok", "service": "KW Email Reader"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Webhook endpoint for receiving Telegram updates
    try:
        data = await request.json()

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
        await handle_all(command, chat_id, telegram_client)
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


@app.get("/webhook/info")
async def webhook_info():
    # Get current webhook configuration
    return telegram_client.get_webhook_info()


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
