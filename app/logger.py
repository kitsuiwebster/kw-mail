# Clean, professional logging for KW Email Reader.
import logging
import sys


class ColoredFormatter(logging.Formatter):
    # Custom formatter with colors and emojis.

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m',
    }

    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '👉',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💥',
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '')
        reset = self.COLORS['RESET']

        # Format: [👉] Message
        log_message = f"{color}{emoji} {record.getMessage()}{reset}"
        return log_message


class UvicornFormatter(logging.Formatter):
    # Custom formatter for uvicorn logs to match our style.

    def format(self, record):
        message = record.getMessage()

        # Simplify startup messages
        if "Started server process" in message:
            return "🚀 Server started"
        elif "Waiting for application startup" in message:
            # Mark to skip
            record._skip = True
            return ""
        elif "Application startup complete" in message:
            return "👉 Application ready"
        elif "Uvicorn running on" in message:
            port = message.split(":")[-1].split()[0]
            return f"👉 Listening on port {port}"

        return f"ℹ📌  {message}"


class SkipMarkedFilter(logging.Filter):
    # Filter to skip messages marked with _skip attribute.

    def filter(self, record):
        return not getattr(record, '_skip', False)


def setup_logger(name: str = "kw-mail") -> logging.Logger:
    # Setup and return a configured logger.
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


# Global logger instance
logger = setup_logger()
