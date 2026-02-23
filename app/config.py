# Global configuration values.
import os

from dotenv import load_dotenv


# Whitelist of authorized chat IDs
load_dotenv()
AUTHORIZED_CHAT_IDS = [os.getenv("TELEGRAM_CHAT_ID")]
