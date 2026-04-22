import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db import faiss_store
from app.db.postgres import AsyncSessionLocal
from app.db.redis import get_redis
from app.db.models import Tenant
from app.services import embeddings

router = APIRouter(tags=["Health"])


@router.get("/debug/whatsapp-send/{tenant_id}/{to_number}")
async def debug_whatsapp_send(tenant_id: str, to_number: str) -> dict:
    """Test WhatsApp send directly — bypasses webhook, sends a real message."""
    import traceback
    from uuid import UUID
    from app.providers import whatsapp as wa
    result: dict = {}
    try:
        async with AsyncSessionLocal() as db:
            from app.db.models import Tenant as T
            tenant = await db.get(T, UUID(tenant_id))
            if not tenant:
                return {"error": "tenant not found"}
            wa_cfg = (tenant.channels or {}).get("whatsapp", {})
            result["access_token_set"] = bool(wa_cfg.get("access_token"))
            result["phone_number_id_set"] = bool(wa_cfg.get("phone_number_id"))
            result["phone_number_id"] = wa_cfg.get("phone_number_id", "MISSING")
            if not wa_cfg.get("access_token") or not wa_cfg.get("phone_number_id"):
                return result
            await wa.send_text_reply(
                wa_cfg["access_token"],
                wa_cfg["phone_number_id"],
                to_number,
                "✅ Test message from BotIQ — WhatsApp channel is working!",
            )
            result["sent"] = True
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()[-800:]
    return result


@router.get("/health")
async def health_check() -> dict:
    deps: dict[str, str] = {}

    # PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            deps["postgresql"] = "ok"
    except Exception:
        deps["postgresql"] = "down"

    # LLM
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                deps["ollama"] = "ok" if resp.status_code == 200 else "degraded"
        except Exception:
            deps["ollama"] = "down"
    elif provider == "gemini":
        if not settings.gemini_api_key or "your-gemini-api-key" in settings.gemini_api_key:
            deps["gemini"] = "missing_api_key"
        else:
            # We don't want to burn tokens on health check, just check key exists for now
            # Or do a minimal model check
            deps["gemini"] = "configured"

    # Redis
    try:
        await get_redis().ping()
        deps["redis"] = "ok"
    except Exception:
        deps["redis"] = "down"

    overall = "ok" if all(v in ["ok", "configured"] for v in deps.values()) else "degraded"

    return {"status": overall, "version": "0.1.0", "dependencies": deps}


@router.get("/debug/full-pipeline/{tenant_id}/{chat_id}")
async def debug_full_pipeline(tenant_id: str, chat_id: str) -> dict:
    """Run the full RAG pipeline inline and attempt Telegram reply. Returns every step."""
    import traceback
    from app.services import rag, llm
    result: dict = {"steps": []}

    try:
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, tenant_id)
            if not tenant:
                return {"error": "tenant not found"}
            bot_token = (tenant.channels or {}).get("telegram", {}).get("bot_token")
            result["bot_token"] = "SET" if bot_token else "MISSING"
            result["channels_raw_keys"] = list((tenant.channels or {}).get("telegram", {}).keys())
            if not bot_token:
                return result
            result["steps"].append("got_bot_token")

            vec = embeddings.embed_text("What is KSE-100?")
            hits = faiss_store.search(tenant_id, vec, top_k=3)
            result["faiss_hits"] = len(hits)
            result["steps"].append("faiss_searched")

            answer = await llm.safe_generate_with_tools(f"User asks: What is KSE-100? Context: PSX is Pakistan Stock Exchange.", [])
            result["llm_answer"] = (answer or "")[:200]
            result["steps"].append("llm_answered")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": int(chat_id), "text": answer or "Test reply"},
            )
            result["telegram_status"] = resp.status_code
            result["telegram_ok"] = resp.json().get("ok")
            result["steps"].append("telegram_sent")

    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()[-500:]

    return result


@router.get("/debug/send-test/{tenant_id}/{chat_id}")
async def debug_send_test(tenant_id: str, chat_id: str) -> dict:
    """Send a test Telegram reply directly — bypasses background task."""
    import httpx
    from app.db.models import Tenant
    from app.services import embeddings
    result: dict = {}
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            return {"error": "tenant not found"}
        bot_token = (tenant.channels or {}).get("telegram", {}).get("bot_token")
        result["bot_token_present"] = bool(bot_token)
        if not bot_token:
            return result

    # Test embed + faiss
    try:
        vec = embeddings.embed_text("What is PSX?")
        hits = faiss_store.search(tenant_id, vec, top_k=3)
        result["faiss_hits"] = len(hits)
    except Exception as e:
        result["faiss_error"] = str(e)
        return result

    # Send test message via Telegram
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": f"Test OK — FAISS hits: {len(hits)}"},
            )
            result["telegram_send"] = resp.status_code
            result["telegram_response"] = resp.json()
    except Exception as e:
        result["telegram_error"] = str(e)

    return result


@router.get("/debug/telegram-reply/{tenant_id}")
async def debug_telegram_reply(tenant_id: str, text: str = "What is PSX?") -> dict:
    """Simulate an inline Telegram webhook message and return what the bot would reply."""
    import traceback
    from uuid import UUID
    from app.services import rag, bot_user_service
    from app.schemas.bot_user import Platform
    from app.schemas.message import ContentType, MessageRole
    result: dict = {"query": text}
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.db.models import Tenant as T
            tid = UUID(tenant_id)
            tenant = await db.get(T, tid)
            if not tenant:
                return {"error": "tenant not found"}
            result["tenant_status"] = tenant.status

            bot_user = await bot_user_service.get_or_create_bot_user(
                db, tid, Platform.telegram, "debug_user"
            )
            result["bot_user_id"] = str(bot_user.id)

            conversation = await rag.get_or_create_conversation(
                db, tid, bot_user.id, Platform.telegram.value
            )
            result["conversation_id"] = str(conversation.id)

            answer, chunk_ids = await rag.answer_query(db, tid, conversation.id, text)
            result["answer"] = answer
            result["chunk_ids"] = chunk_ids
            result["webhook_response"] = {
                "method": "sendMessage",
                "chat_id": "<user_chat_id>",
                "text": answer[:200]
            }
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()[-1000:]
    return result


@router.get("/debug/pipeline/{tenant_id}")
async def debug_pipeline(tenant_id: str) -> dict:
    """Debug endpoint: tests embed + FAISS + channels for a tenant."""
    result: dict = {}
    try:
        vec = embeddings.embed_text("test query about PSX")
        result["embed"] = f"ok (dim={len(vec)})"
    except Exception as e:
        result["embed"] = f"FAILED: {e}"

    try:
        hits = faiss_store.search(tenant_id, vec if "vec" in dir() else None, top_k=3)
        result["faiss"] = f"ok ({len(hits)} hits)"
    except Exception as e:
        result["faiss"] = f"FAILED: {e}"

    try:
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, tenant_id)
            if tenant:
                ch = tenant.channels or {}
                tg = ch.get("telegram", {})
                wa = ch.get("whatsapp", {})
                result["channels"] = {
                    "telegram_token": "SET" if tg.get("bot_token") else "MISSING",
                    "whatsapp_verify_token": "SET" if wa.get("verify_token") else "MISSING",
                }
            else:
                result["channels"] = "tenant not found"
    except Exception as e:
        result["channels"] = f"FAILED: {e}"

    return result
