import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status
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
from app.providers import whatsapp as wa_provider
from app.providers.whatsapp import InvalidSignatureError
from app.services import bot_user_service, rag
from app.services.rate_limiter import limiter
from app.services.transcription import TranscriptionError, transcribe_audio

_MAX_TG_TEXT = 4096

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# In-memory tracker for last received WhatsApp webhook (debug only)
_last_wa_webhook: dict = {}


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


def _tg_reply(chat_id: str, text: str) -> dict:
    """Build a Telegram webhook-response sendMessage payload (no outbound call needed)."""
    return {"method": "sendMessage", "chat_id": int(chat_id), "text": text[:_MAX_TG_TEXT]}


# ── WhatsApp (Twilio) ─────────────────────────────────────────────────


async def _handle_whatsapp_message(payload: dict, tenant_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant or tenant.status != "active":
            return

        wa_config = tenant.channels.get("whatsapp", {})
        access_token = wa_config.get("access_token")
        phone_number_id = wa_config.get("phone_number_id")

        if not all([access_token, phone_number_id]):
            logger.warning("Tenant %s missing Meta WhatsApp credentials", tenant_id)
            return

        msg = wa_provider.parse_webhook(payload)
        if not msg or not msg.body.strip():
            import json as _json
            try:
                from app.db.redis import get_redis
                await get_redis().set("debug:wa_parse_none", _json.dumps({
                    "payload_entry_keys": list((payload.get("entry", [{}])[0]).keys()),
                    "changes": str(payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", "NO_MESSAGES"))[:300],
                    "msg_was_none": msg is None,
                    "body_empty": bool(msg) and not msg.body.strip(),
                }), ex=3600)
            except Exception:
                pass
            return

        try:
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

            if tenant.usage is None:
                tenant.usage = {"message_count_month": 0, "active_users_month": 0}
            new_usage = tenant.usage.copy()
            new_usage["message_count_month"] = new_usage.get("message_count_month", 0) + 1
            tenant.usage = new_usage
            await db.commit()

            import json as _json
            from app.db.redis import get_redis
            await get_redis().set("debug:wa_pre_send", _json.dumps({
                "from_number": msg.from_number,
                "phone_number_id": phone_number_id,
                "answer_preview": answer[:100],
                "access_token_prefix": access_token[:12] + "...",
            }), ex=3600)

            # Isolated send with its own error capture
            try:
                await wa_provider.send_text_reply(access_token, phone_number_id, msg.from_number, answer)
                await get_redis().set("debug:wa_send_ok", _json.dumps({"to": msg.from_number, "sent": True}), ex=3600)
                await get_redis().delete("debug:wa_send_error")
            except Exception as send_exc:
                import traceback as _tb
                logger.exception("WhatsApp send failed for tenant %s: %s", tenant_id, send_exc)
                await get_redis().set("debug:wa_send_error", _json.dumps({
                    "error": str(send_exc),
                    "type": type(send_exc).__name__,
                    "traceback": _tb.format_exc()[-1000:],
                    "phone_number_id": phone_number_id,
                    "to": msg.from_number,
                }), ex=3600)

        except Exception as exc:
            import traceback as _tb, json as _json
            logger.exception("Unhandled error in WhatsApp handler for tenant %s: %s", tenant_id, exc)
            err_data = {"error": str(exc), "traceback": _tb.format_exc()[-1000:]}
            try:
                from app.db.redis import get_redis
                await get_redis().set("debug:last_wa_error", _json.dumps(err_data), ex=3600)
            except Exception:
                pass


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
    if mode == "subscribe" and token == verify_token:
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
    app_secret = wa_config.get("app_secret", "")

    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Track BEFORE signature check so we can see if Meta is calling us at all
    import datetime as _dt, json as _json
    global _last_wa_webhook
    sig_valid: str = "skipped"
    if app_secret and signature:
        try:
            wa_provider.verify_signature(app_secret, body_bytes, signature)
            sig_valid = "ok"
        except InvalidSignatureError:
            sig_valid = "failed"
            logger.warning("WhatsApp signature verification failed for tenant %s — proceeding anyway for debug", tenant_id)

    payload = await request.json()

    _last_wa_webhook = {
        "received_at": _dt.datetime.utcnow().isoformat(),
        "tenant_id": tenant_id,
        "payload_keys": list(payload.keys()),
        "has_messages": bool(payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages")),
        "signature_check": sig_valid,
        "app_secret_set": bool(app_secret),
    }
    try:
        from app.db.redis import get_redis
        await get_redis().set("debug:last_wa_webhook", _json.dumps(_last_wa_webhook), ex=3600)
    except Exception:
        pass

    background_tasks.add_task(_handle_whatsapp_message, payload, tenant.id)
    return {"ok": True}


@router.post("/telegram/{tenant_id}", status_code=200)
@limiter.limit("60/minute")
async def telegram_webhook(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    secret_token: str | None = None,
) -> dict:
    tenant = await _get_tenant(db, tenant_id)

    stored_token = tenant.channels.get("telegram", {}).get("webhook_secret_token")
    if stored_token and secret_token != stored_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    bot_token = tenant.channels.get("telegram", {}).get("bot_token")
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

        if tenant.usage is None:
            tenant.usage = {"message_count_month": 0, "active_users_month": 0}
        new_usage = tenant.usage.copy()
        new_usage["message_count_month"] = new_usage.get("message_count_month", 0) + 1
        tenant.usage = new_usage
        await db.commit()

        return _tg_reply(chat_id, answer)

    except AudioTooLongError as exc:
        return _tg_reply(chat_id, str(exc)) if chat_id else {"ok": True}
    except UnsupportedMessageTypeError as exc:
        return _tg_reply(chat_id, str(exc)) if chat_id else {"ok": True}
    except Exception as exc:
        logger.exception("Unhandled error in Telegram handler for tenant %s: %s", tenant_id, exc)
        return _tg_reply(chat_id, "An unexpected error occurred. Please try again.") if chat_id else {"ok": True}
