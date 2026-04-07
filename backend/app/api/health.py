import httpx
from fastapi import APIRouter

from app.config import settings
from app.db.mongo import get_db
from app.db.redis import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    deps: dict[str, str] = {}

    # MongoDB
    try:
        await get_db().command("ping")
        deps["mongodb"] = "ok"
    except Exception:
        deps["mongodb"] = "down"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            deps["ollama"] = "ok" if resp.status_code == 200 else "degraded"
    except Exception:
        deps["ollama"] = "down"

    # Redis
    try:
        await get_redis().ping()
        deps["redis"] = "ok"
    except Exception:
        deps["redis"] = "down"

    overall = "ok" if all(v == "ok" for v in deps.values()) else "degraded"
    status_code = 200 if overall != "down" else 503

    return {"status": overall, "version": "0.1.0", "dependencies": deps}
