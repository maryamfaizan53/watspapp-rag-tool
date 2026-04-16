import httpx
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.postgres import AsyncSessionLocal
from app.db.redis import get_redis

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
