from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_tenant_id(request) -> str:  # type: ignore[no-untyped-def]
    """Extract tenant_id from path parameters for per-tenant rate limiting."""
    tenant_id = request.path_params.get("tenant_id")
    if tenant_id:
        return f"tenant:{tenant_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=_get_tenant_id, default_limits=["60/minute"])
