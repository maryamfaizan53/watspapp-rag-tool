"""
Health & diagnostics.

SECURITY NOTE: the previous version of this module exposed ~10 unauthenticated
/debug/* endpoints that could send real WhatsApp/Telegram messages on behalf
of tenants, leak token prefixes and message content, and burn LLM quota.
They have been removed. The single remaining diagnostic endpoint requires an
authenticated admin AND is disabled entirely when ENVIRONMENT=production.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import text

from app.api.auth import get_current_admin
from app.config import settings
from app.db import faiss_store
from app.db.postgres import AsyncSessionLocal
from app.db.redis import get_redis
from app.db.models import AdminUser, Tenant
from app.services import embeddings

router = APIRouter(tags=["Health"])


async def require_debug_access(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """Debug endpoints: admin-only, and never available in production."""
    if settings.environment.lower() == "production":
        # 404 (not 403) so production doesn't even reveal these routes exist
        raise HTTPException(status_code=404, detail="Not found")
    return admin


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
            # Don't burn tokens on health checks — just confirm a key exists
            deps["gemini"] = "configured"
    elif provider == "openai":
        deps["openai"] = "configured" if settings.openai_api_key else "missing_api_key"

    # Redis
    try:
        await get_redis().ping()
        deps["redis"] = "ok"
    except Exception:
        deps["redis"] = "down"

    overall = "ok" if all(v in ["ok", "configured"] for v in deps.values()) else "degraded"

    return {"status": overall, "version": "0.1.0", "dependencies": deps}


@router.get("/debug/pipeline/{tenant_id}")
async def debug_pipeline(
    tenant_id: str,
    _: AdminUser = Depends(require_debug_access),
) -> dict:
    """
    Admin-only, non-production: smoke-test embed + FAISS + channel config for a
    tenant. Never returns secret values — only SET/MISSING flags.
    """
    result: dict = {}
    vec = None
    try:
        vec = embeddings.embed_text("test query about PSX")
        result["embed"] = f"ok (dim={len(vec)})"
    except Exception as e:
        result["embed"] = f"FAILED: {e}"

    try:
        if vec is not None:
            hits = faiss_store.search(tenant_id, vec, top_k=3)
            result["faiss"] = f"ok ({len(hits)} hits)"
        else:
            result["faiss"] = "skipped (embed failed)"
    except Exception as e:
        result["faiss"] = f"FAILED: {e}"

    try:
        from uuid import UUID
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, UUID(tenant_id))
            if tenant:
                ch = tenant.channels or {}
                tg = ch.get("telegram", {})
                wa = ch.get("whatsapp", {})
                result["channels"] = {
                    "telegram_token": "SET" if tg.get("bot_token") else "MISSING",
                    "telegram_webhook_secret": "SET" if tg.get("webhook_secret_token") else "MISSING",
                    "whatsapp_access_token": "SET" if wa.get("access_token") else "MISSING",
                    "whatsapp_app_secret": "SET" if wa.get("app_secret") else "MISSING",
                    "whatsapp_verify_token": "SET" if wa.get("verify_token") else "MISSING",
                }
            else:
                result["channels"] = "tenant not found"
    except Exception as e:
        result["channels"] = f"FAILED: {e}"

    return result
