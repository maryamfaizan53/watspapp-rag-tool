import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def _get_tenant_id(request) -> str:  # type: ignore[no-untyped-def]
    """Extract tenant_id from path parameters for per-tenant rate limiting."""
    tenant_id = request.path_params.get("tenant_id")
    if tenant_id:
        return f"tenant:{tenant_id}"
    return get_remote_address(request)


# Redis-backed storage so limits survive restarts and are shared across
# workers/replicas. Falls back to in-memory if Redis is unreachable at boot
# (logged loudly — in-memory limits are per-process and reset on restart).
try:
    limiter = Limiter(
        key_func=_get_tenant_id,
        default_limits=["60/minute"],
        storage_uri=settings.redis_url,
    )
except Exception as exc:  # pragma: no cover
    logger.error("Redis rate-limit storage unavailable (%s) — falling back to in-memory", exc)
    limiter = Limiter(key_func=_get_tenant_id, default_limits=["60/minute"])
