from app.telegram.client import TelegramClient


def send_in_chunks(telegram_client: TelegramClient, chat_id: str, lines: list[str]):
    # Send message in chunks if too long
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
