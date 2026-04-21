import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MAX_VOICE_DURATION_SECONDS = 300  # 5 minutes
TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramContentType(str, Enum):
    text = "text"
    voice = "voice"
    audio = "audio"
    unsupported = "unsupported"


@dataclass
class TelegramMessage:
    chat_id: str
    content_type: TelegramContentType
    text: Optional[str] = None
    file_id: Optional[str] = None
    file_duration: Optional[int] = None
    mime_type: Optional[str] = None


class AudioTooLongError(Exception):
    pass


class UnsupportedMessageTypeError(Exception):
    pass


def parse_update(update: dict) -> Optional[TelegramMessage]:
    """Parse a Telegram Update dict into a TelegramMessage. Returns None for non-message updates."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None

    chat_id = str(message["chat"]["id"])

    if "text" in message:
        return TelegramMessage(
            chat_id=chat_id,
            content_type=TelegramContentType.text,
            text=message["text"],
        )

    if "voice" in message:
        voice = message["voice"]
        duration = voice.get("duration", 0)
        if duration > MAX_VOICE_DURATION_SECONDS:
            raise AudioTooLongError(
                f"Voice note is {duration}s, maximum allowed is {MAX_VOICE_DURATION_SECONDS}s."
            )
        return TelegramMessage(
            chat_id=chat_id,
            content_type=TelegramContentType.voice,
            file_id=voice["file_id"],
            file_duration=duration,
            mime_type=voice.get("mime_type", "audio/ogg"),
        )

    if "audio" in message:
        audio = message["audio"]
        duration = audio.get("duration", 0)
        if duration > MAX_VOICE_DURATION_SECONDS:
            raise AudioTooLongError(
                f"Audio is {duration}s, maximum allowed is {MAX_VOICE_DURATION_SECONDS}s."
            )
        return TelegramMessage(
            chat_id=chat_id,
            content_type=TelegramContentType.audio,
            file_id=audio["file_id"],
            file_duration=duration,
            mime_type=audio.get("mime_type", "audio/mpeg"),
        )

    raise UnsupportedMessageTypeError(
        "Only text and voice messages are supported. Please send a text or voice message."
    )


async def get_file_bytes(bot_token: str, file_id: str) -> tuple[bytes, str]:
    """Download a file from Telegram servers. Returns (file_bytes, file_path)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get file info
        resp = await client.get(
            f"{TELEGRAM_API_BASE}/bot{bot_token}/getFile",
            params={"file_id": file_id},
        )
        resp.raise_for_status()
        file_path = resp.json()["result"]["file_path"]

        # Download file
        download_resp = await client.get(
            f"{TELEGRAM_API_BASE}/file/bot{bot_token}/{file_path}"
        )
        download_resp.raise_for_status()
        return download_resp.content, file_path


async def send_text_reply(bot_token: str, chat_id: str, text: str) -> None:
    """Send a text message reply via Telegram Bot API."""
    if len(text) > 4000:
        text = text[:4000] + "..."
    # Try python-telegram-bot first (handles connection issues better than raw httpx)
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=int(chat_id), text=text)
        return
    except Exception as exc:
        logger.warning("PTB send failed, falling back to httpx: %s", exc)
    # Fallback: raw httpx with longer timeout
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to send Telegram reply to %s: %s", chat_id, exc)
