import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, AsyncSessionLocal
from app.db.models import Tenant, Message
from app.schemas.bot_user import Platform
from app.schemas.message import ContentType, MessageRole
from app.providers import telegram as tg_provider
from app.providers.telegram import AudioTooLongError, UnsupportedMessageTypeError
from app.providers import whatsapp as wa_provider
from app.providers.whatsapp import InvalidSignatureError
from app.services import bot_user_service, rag
from app.services.crypto import decrypt_secret
from app.services.rate_limiter import limiter
from app.services.transcription import TranscriptionError, transcribe_audio
from app.services.usage_service import QUOTA_EXCEEDED_REPLY, consume_message_quota

_MAX_TG_TEXT = 4096

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _get_tenant(db: AsyncSession, tenant_id: str | UUID) -> Tenant:
    try:
        tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    except ValueError:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")
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


def _tg_reply(chat_id: str, text: str) -> dict:
    """Build a Telegram webhook-response sendMessage payload (no outbound call needed)."""
    return {"method": "sendMessage", "chat_id": int(chat_id), "text": text[:_MAX_TG_TEXT]}


# ── WhatsApp (Meta Cloud API) ─────────────────────────────────────────


async def _handle_whatsapp_message(payload: dict, tenant_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant or tenant.status != "active":
            return

        wa_config = tenant.channels.get("whatsapp", {})
        access_token = decrypt_secret(wa_config.get("access_token"))
        phone_number_id = wa_config.get("phone_number_id")

        if not all([access_token, phone_number_id]):
            logger.warning("Tenant %s missing Meta WhatsApp credentials", tenant_id)
            return

        msg = wa_provider.parse_webhook(payload)
        if not msg:
            return

        # Non-text messages (voice notes, images, stickers...) — reply politely
        # instead of silently dropping. Keeps users from thinking the bot is dead.
        if msg.unsupported:
            try:
                await wa_provider.send_text_reply(
                    access_token, phone_number_id, msg.from_number,
                    "I can only read text messages on WhatsApp right now. "
                    "Please type your question.",
                )
            except Exception:
                logger.exception("Failed to send unsupported-type notice (tenant %s)", tenant_id)
            return

        if not msg.body.strip():
            return

        try:
            # Quota gate BEFORE any LLM/embedding work — over-quota tenants
            # must not burn tokens. Counter is row-locked and month-aware.
            if not await consume_message_quota(db, tenant_id):
                await wa_provider.send_text_reply(
                    access_token, phone_number_id, msg.from_number, QUOTA_EXCEEDED_REPLY
                )
                return

            bot_user = await bot_user_service.get_or_create_bot_user(
                db, tenant_id, Platform.whatsapp, msg.from_number
            )
            conversation = await rag.get_or_create_conversation(
                db, tenant_id, bot_user.id, Platform.whatsapp.value
            )

            await _persist_message(
                db, conversation.id, tenant_id,
                MessageRole.user, ContentType.text, msg.body,
            )

            start_ts = time.monotonic()
            answer, chunk_ids = await rag.answer_query(db, tenant_id, conversation.id, msg.body)
            latency_ms = int((time.monotonic() - start_ts) * 1000)

            await _persist_message(
                db, conversation.id, tenant_id,
                MessageRole.bot, ContentType.text, answer,
                rag_context_ids=chunk_ids, latency_ms=latency_ms,
            )

            await rag.update_conversation(db, conversation.id)

            await wa_provider.send_text_reply(
                access_token, phone_number_id, msg.from_number, answer
            )

        except Exception as exc:
            logger.exception("Unhandled error in WhatsApp handler for tenant %s: %s", tenant_id, exc)


@router.get("/whatsapp/{tenant_id}", status_code=200)
async def whatsapp_verify(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> object:
    """Meta webhook verification handshake (GET)."""
    tenant = await _get_tenant(db, tenant_id)
    verify_token = tenant.channels.get("whatsapp", {}).get("verify_token", "")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and verify_token and token == verify_token:
        logger.info("WhatsApp webhook verified for tenant %s", tenant_id)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/{tenant_id}", status_code=200)
@limiter.limit("60/minute")
async def whatsapp_webhook(
    tenant_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await _get_tenant(db, tenant_id)
    wa_config = tenant.channels.get("whatsapp", {})
    app_secret = decrypt_secret(wa_config.get("app_secret")) or ""

    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # SECURITY: when an app secret is configured the signature is MANDATORY.
    # Meta signs every webhook delivery — a missing or invalid signature means
    # the request did not come from Meta and must be rejected, otherwise anyone
    # can forge payloads and make the bot message arbitrary numbers.
    if app_secret:
        if not signature:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing signature")
        try:
            wa_provider.verify_signature(app_secret, body_bytes, signature)
        except InvalidSignatureError:
            logger.warning("WhatsApp signature verification FAILED for tenant %s — rejected", tenant_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    else:
        # No secret configured → cannot verify. Allow (so onboarding works)
        # but warn loudly; admins should always set the app secret.
        logger.warning(
            "Tenant %s has no WhatsApp app_secret configured — webhook NOT verified. "
            "Set it in channel config.",
            tenant_id,
        )

    payload = await request.json()
    background_tasks.add_task(_handle_whatsapp_message, payload, tenant.id)
    return {"ok": True}


@router.post("/telegram/{tenant_id}", status_code=200)
@limiter.limit("60/minute")
async def telegram_webhook(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await _get_tenant(db, tenant_id)

    # SECURITY: Telegram sends the webhook secret in this HTTP header
    # (NOT as a query parameter). It must match the secret_token value
    # registered via setWebhook.
    stored_token = decrypt_secret(
        tenant.channels.get("telegram", {}).get("webhook_secret_token")
    )
    if stored_token:
        header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header_token != stored_token:
            logger.warning("Telegram secret-token mismatch for tenant %s — rejected", tenant_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")
    else:
        logger.warning(
            "Tenant %s has no Telegram webhook_secret_token configured — webhook NOT verified. "
            "Set it in channel config and pass the same value as secret_token to setWebhook.",
            tenant_id,
        )

    bot_token = decrypt_secret(tenant.channels.get("telegram", {}).get("bot_token"))
    if not bot_token:
        logger.warning("Tenant %s has no Telegram bot token", tenant_id)
        return {"ok": True}

    update_data = await request.json()
    chat_id: str | None = None

    try:
        parsed = tg_provider.parse_update(update_data)
        if not parsed:
            return {"ok": True}

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
            file_bytes, file_path = await tg_provider.get_file_bytes(bot_token, parsed.file_id)
            audio_content_ref = file_path
            try:
                transcription = await transcribe_audio(file_bytes, parsed.mime_type or "audio/ogg")
                query_text = transcription
            except TranscriptionError:
                return _tg_reply(chat_id, "Sorry, I couldn't understand the audio. Please resend a clearer message.")

        if not query_text.strip():
            return {"ok": True}

        # Quota gate BEFORE any LLM/embedding work.
        if not await consume_message_quota(db, tenant.id):
            return _tg_reply(chat_id, QUOTA_EXCEEDED_REPLY)

        bot_user = await bot_user_service.get_or_create_bot_user(
            db, tenant.id, Platform.telegram, chat_id
        )
        conversation = await rag.get_or_create_conversation(
            db, tenant.id, bot_user.id, Platform.telegram.value
        )

        await _persist_message(
            db, conversation.id, tenant.id, MessageRole.user, content_type,
            content=audio_content_ref if content_type == ContentType.audio else query_text,
            transcription=transcription,
        )

        start_ts = time.monotonic()
        answer, chunk_ids = await rag.answer_query(db, tenant.id, conversation.id, query_text)
        latency_ms = int((time.monotonic() - start_ts) * 1000)

        await _persist_message(
            db, conversation.id, tenant.id, MessageRole.bot, ContentType.text,
            content=answer, rag_context_ids=chunk_ids, latency_ms=latency_ms,
        )

        await rag.update_conversation(db, conversation.id)

        return _tg_reply(chat_id, answer)

    except AudioTooLongError as exc:
        return _tg_reply(chat_id, str(exc)) if chat_id else {"ok": True}
    except UnsupportedMessageTypeError as exc:
        return _tg_reply(chat_id, str(exc)) if chat_id else {"ok": True}
    except Exception as exc:
        logger.exception("Unhandled error in Telegram handler for tenant %s: %s", tenant_id, exc)
        return _tg_reply(chat_id, "An unexpected error occurred. Please try again.") if chat_id else {"ok": True}
