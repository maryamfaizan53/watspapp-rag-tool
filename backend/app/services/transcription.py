import logging
import tempfile
import os

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


class TranscriptionError(Exception):
    pass


async def transcribe_audio(file_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Transcribe audio bytes using OpenAI Whisper API.
    Returns transcribed text. Raises TranscriptionError on failure or empty result.
    """
    extension = _mime_to_extension(mime_type)
    client = get_openai_client()

    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
            )
        text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
        if not text:
            raise TranscriptionError("Transcription returned empty result.")
        logger.info("Transcription successful (%d chars)", len(text))
        return text
    except TranscriptionError:
        raise
    except Exception as exc:
        logger.error("Whisper transcription failed: %s", exc)
        raise TranscriptionError(f"Audio transcription failed: {exc}") from exc
    finally:
        os.unlink(tmp_path)


def _mime_to_extension(mime_type: str) -> str:
    mapping = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
    }
    return mapping.get(mime_type, ".ogg")
