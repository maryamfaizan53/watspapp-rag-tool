"""
Quota enforcement for tenant message usage.

- Row-level lock (SELECT ... FOR UPDATE) prevents lost updates when multiple
  webhooks for the same tenant arrive concurrently.
- Usage carries a "month" stamp; counters reset automatically when the
  calendar month rolls over (UTC).
- consume_message_quota() is called BEFORE the RAG pipeline so over-quota
  tenants never burn LLM tokens.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Tenant

logger = logging.getLogger(__name__)

DEFAULT_MESSAGES_PER_MONTH = 5_000

QUOTA_EXCEEDED_REPLY = (
    "This service has reached its monthly message limit. "
    "Please contact your service provider to upgrade the plan."
)


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def consume_message_quota(db: AsyncSession, tenant_id: str | UUID) -> bool:
    """
    Atomically: reset counters on month rollover, check the plan limit,
    and increment usage by one. Returns False when the tenant is over quota
    (nothing is incremented in that case).
    """
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    result = await db.execute(
        select(Tenant).where(Tenant.id == tid).with_for_update()
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return False

    usage = dict(tenant.usage or {})
    month = _current_month()

    if usage.get("month") != month:
        usage = {"month": month, "message_count_month": 0, "active_users_month": 0}

    limit = (tenant.quota or {}).get("messages_per_month", DEFAULT_MESSAGES_PER_MONTH)
    used = int(usage.get("message_count_month", 0))

    if used >= limit:
        await db.commit()  # release the row lock
        logger.warning("Tenant %s over monthly quota (%d/%d)", tid, used, limit)
        return False

    usage["message_count_month"] = used + 1
    tenant.usage = usage
    flag_modified(tenant, "usage")
    await db.commit()
    return True
