import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.db import get_db, AsyncSessionLocal
from app.db.models import Tenant, Message, BotUser, Conversation
from app.schemas.bot_user import Platform
from app.schemas.message import ContentType, MessageRole
from app.providers import telegram as tg_provider
from app.providers.telegram import AudioTooLongError, UnsupportedMessageTypeError
from app.services import bot_user_service, rag
from app.services.rate_limiter import limiter
from app.services.transcription import TranscriptionError, transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _get_tenant(db: AsyncSession, tenant_id: str | UUID) -> Tenant:
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    query = select(Tenant).where(Tenant.id == tid, Tenant.status == "active")
    result = await db.execute(query)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")
    return tenant


async def _persist_message(
    db: AsyncSession,
    conversation_id: UUID,
    tenant_id: UUID,
    role: MessageRole,
    content_type: ContentType,
    content: str,
    transcription: str | None = None,
    rag_context_ids: list[str] | None = None,
    latency_ms: int | None = None,
) -> None:
    msg = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role.value,
        content_type=content_type.value,
        content=content,
        transcription=transcription,
        rag_context_ids=rag_context_ids or [],
        latency_ms=latency_ms,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(msg)
    await db.commit()


# ── Telegram ──────────────────────────────────────────────────────────


async def _handle_telegram_message(update_data: dict, tenant_id: UUID) -> None:
    # We use a new session because this runs in a BackgroundTask
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant or tenant.status != "active":
            return

        bot_token = tenant.channels.get("telegram", {}).get("bot_token")
        if not bot_token:
            logger.warning("Tenant %s has no Telegram bot token configured", tenant_id)
            return

        chat_id: str | None = None
        try:
            parsed = tg_provider.parse_update(update_data)
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
                db, tenant_id, Platform.telegram, chat_id
            )
            conversation = await rag.get_or_create_conversation(
                db, tenant_id, bot_user.id, Platform.telegram.value
            )

            # Persist user message
            await _persist_message(
                db,
                conversation.id,
                tenant_id,
                MessageRole.user,
                content_type,
                content=audio_content_ref if content_type == ContentType.audio else query_text,
                transcription=transcription,
            )

            # Run RAG pipeline
            start_ts = time.monotonic()
            answer, chunk_ids = await rag.answer_query(db, tenant_id, conversation.id, query_text)
            latency_ms = int((time.monotonic() - start_ts) * 1000)

            # Persist bot message
            await _persist_message(
                db,
                conversation.id,
                tenant_id,
                MessageRole.bot,
                ContentType.text,
                content=answer,
                rag_context_ids=chunk_ids,
                latency_ms=latency_ms,
            )

            # Update conversation + usage counter
            await rag.update_conversation(db, conversation.id)
            
            # Update tenant usage
            # We use atomic increment
            # SQLAlchemy doesn't have a direct $inc but we can use values(count = count + 1)
            # Actually, we can update the object directly if we have it in session
            if tenant.usage is None:
                tenant.usage = {"message_count_month": 0, "active_users_month": 0}
            
            new_usage = tenant.usage.copy()
            new_usage["message_count_month"] = new_usage.get("message_count_month", 0) + 1
            tenant.usage = new_usage
            await db.commit()

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
    db: AsyncSession = Depends(get_db),
    secret_token: str | None = None,
) -> dict:
    tenant = await _get_tenant(db, tenant_id)

    # Validate Telegram secret_token
    stored_token = (
        tenant.channels.get("telegram", {}).get("webhook_secret_token")
    )
    if stored_token and secret_token != stored_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    update_data = await request.json()
    background_tasks.add_task(_handle_telegram_message, update_data, tenant.id)
    return {"ok": True}
