import logging
import time
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.db.mongo import get_db
from app.models.bot_user import Platform
from app.models.message import ContentType, Message, MessageRole
from app.providers import telegram as tg_provider
from app.providers.telegram import AudioTooLongError, UnsupportedMessageTypeError
from app.services import bot_user_service, rag
from app.services.rate_limiter import limiter
from app.services.transcription import TranscriptionError, transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _get_tenant(tenant_id: str) -> dict:
    db = get_db()
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id), "status": "active"})
    if not doc:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")
    doc["_id"] = str(doc["_id"])
    return doc


async def _persist_message(
    conversation_id: str,
    tenant_id: str,
    role: MessageRole,
    content_type: ContentType,
    content: str,
    transcription: str | None = None,
    rag_context_ids: list[str] | None = None,
    latency_ms: int | None = None,
) -> None:
    db = get_db()
    msg = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content_type=content_type,
        content=content,
        transcription=transcription,
        rag_context_ids=rag_context_ids or [],
        latency_ms=latency_ms,
    )
    await db.messages.insert_one(msg.to_doc())


# ── Telegram ──────────────────────────────────────────────────────────


async def _handle_telegram_message(update: dict, tenant: dict) -> None:
    tenant_id = tenant["_id"]
    bot_token = tenant.get("channels", {}).get("telegram", {}).get("bot_token")
    if not bot_token:
        logger.warning("Tenant %s has no Telegram bot token configured", tenant_id)
        return

    chat_id: str | None = None
    try:
        parsed = tg_provider.parse_update(update)
        if not parsed:
            return

        chat_id = parsed.chat_id
        query_text: str = ""
        content_type = ContentType.text
        transcription: str | None = None
        audio_content_ref = ""

        if parsed.content_type == tg_provider.TelegramContentType.text:
            query_text = parsed.text or ""

        elif parsed.content_type in (
            tg_provider.TelegramContentType.voice,
            tg_provider.TelegramContentType.audio,
        ):
            content_type = ContentType.audio
            file_bytes, file_path = await tg_provider.get_file_bytes(
                bot_token, parsed.file_id
            )
            audio_content_ref = file_path
            try:
                transcription = await transcribe_audio(file_bytes, parsed.mime_type or "audio/ogg")
                query_text = transcription
            except TranscriptionError:
                await tg_provider.send_text_reply(
                    bot_token,
                    chat_id,
                    "Sorry, I couldn't understand the audio. Please resend a clearer message.",
                )
                return

        if not query_text.strip():
            return

        # Get or create BotUser and Conversation
        bot_user = await bot_user_service.get_or_create_bot_user(
            tenant_id, Platform.telegram, chat_id
        )
        conversation = await rag.get_or_create_conversation(
            tenant_id, bot_user.id, Platform.telegram.value
        )

        # Persist user message
        await _persist_message(
            conversation.id,
            tenant_id,
            MessageRole.user,
            content_type,
            content=audio_content_ref if content_type == ContentType.audio else query_text,
            transcription=transcription,
        )

        # Run RAG pipeline
        start_ts = time.monotonic()
        answer, chunk_ids = await rag.answer_query(tenant_id, conversation.id, query_text)
        latency_ms = int((time.monotonic() - start_ts) * 1000)

        # Persist bot message
        await _persist_message(
            conversation.id,
            tenant_id,
            MessageRole.bot,
            ContentType.text,
            content=answer,
            rag_context_ids=chunk_ids,
            latency_ms=latency_ms,
        )

        # Update conversation + usage counter
        await rag.update_conversation(conversation.id)
        db = get_db()
        await db.tenants.update_one(
            {"_id": ObjectId(tenant_id)},
            {"$inc": {"usage.message_count_month": 1}},
        )

        await tg_provider.send_text_reply(bot_token, chat_id, answer)

    except AudioTooLongError as exc:
        if chat_id:
            await tg_provider.send_text_reply(bot_token, chat_id, str(exc))
    except UnsupportedMessageTypeError as exc:
        if chat_id:
            await tg_provider.send_text_reply(bot_token, chat_id, str(exc))
    except Exception as exc:
        logger.exception("Unhandled error in Telegram handler for tenant %s: %s", tenant_id, exc)
        if chat_id:
            await tg_provider.send_text_reply(
                bot_token,
                chat_id,
                "An unexpected error occurred. Please try again.",
            )


@router.post("/telegram/{tenant_id}", status_code=200)
@limiter.limit("60/minute")
async def telegram_webhook(
    tenant_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    secret_token: str | None = None,
) -> dict:
    tenant = await _get_tenant(tenant_id)

    # Validate Telegram secret_token
    stored_token = (
        tenant.get("channels", {}).get("telegram", {}).get("webhook_secret_token")
    )
    if stored_token and secret_token != stored_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    update = await request.json()
    background_tasks.add_task(_handle_telegram_message, update, tenant)
    return {"ok": True}
