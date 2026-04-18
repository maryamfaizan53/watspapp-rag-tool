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
