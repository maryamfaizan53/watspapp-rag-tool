"""
Daily UsageSnapshot worker.
Runs as an asyncio background task started at app lifespan.
Every 24 hours (or at the next midnight UTC), computes daily stats per active tenant
and upserts into the usage_snapshots collection.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert

from app.db import AsyncSessionLocal
from app.db.models import Tenant, Message, UsageSnapshot

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def _compute_snapshot_for_tenant(db, tenant_id: UUID, target_date: date) -> None:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Query message stats for the day
    query = (
        select(
            func.count(Message.id).label("message_count"),
            func.count(func.distinct(Message.conversation_id)).label("active_users"), # Approximate active users by distinct conversations
            func.count(Message.id).filter(Message.content_type == "audio").label("voice_message_count"),
            func.avg(Message.latency_ms).label("avg_latency_ms")
        )
        .where(
            and_(
                Message.tenant_id == tenant_id,
                Message.timestamp >= start,
                Message.timestamp < end,
                Message.role == "user"
            )
        )
    )
    
    result = await db.execute(query)
    row = result.fetchone()

    if not row or row.message_count == 0:
        return  # no activity for this tenant on this date

    # Upsert into usage_snapshots
    stmt = insert(UsageSnapshot).values(
        tenant_id=tenant_id,
        date=target_date,
        message_count=row.message_count,
        active_users=row.active_users,
        voice_message_count=row.voice_message_count,
        avg_latency_ms=int(row.avg_latency_ms or 0)
    )
    
    # On conflict update
    stmt = stmt.on_conflict_do_update(
        constraint='uq_usage_tenant_date',
        set_={
            "message_count": stmt.excluded.message_count,
            "active_users": stmt.excluded.active_users,
            "voice_message_count": stmt.excluded.voice_message_count,
            "avg_latency_ms": stmt.excluded.avg_latency_ms,
        }
    )
    
    await db.execute(stmt)
    await db.commit()
    
    logger.debug(
        "UsageSnapshot upserted for tenant %s on %s: %d messages",
        tenant_id,
        target_date,
        row.message_count,
    )


async def _run_daily_snapshot() -> None:
    """Compute snapshots for yesterday across all active tenants."""
    try:
        async with AsyncSessionLocal() as db:
            yesterday = date.today() - timedelta(days=1)
            
            query = select(Tenant.id).where(Tenant.status == "active")
            result = await db.execute(query)
            tenant_ids = result.scalars().all()
            
            logger.info("Running daily UsageSnapshot for %d tenants (date=%s)", len(tenant_ids), yesterday)
            for tid in tenant_ids:
                try:
                    await _compute_snapshot_for_tenant(db, tid, yesterday)
                except Exception:
                    logger.exception("Snapshot failed for tenant %s", tid)
            
            logger.info("Daily UsageSnapshot complete")
    except Exception:
        logger.exception("UsageSnapshot worker run failed")


def _seconds_until_next_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


async def _worker_loop() -> None:
    logger.info("UsageSnapshot worker started")
    while True:
        wait = _seconds_until_next_midnight_utc()
        logger.info("UsageSnapshot worker sleeping %.0f seconds until next midnight UTC", wait)
        await asyncio.sleep(wait)
        await _run_daily_snapshot()


def start_worker() -> None:
    """Start the background worker task. Call from app lifespan startup."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
        logger.info("UsageSnapshot background worker task created")


def stop_worker() -> None:
    """Cancel the background worker task. Call from app lifespan shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        logger.info("UsageSnapshot background worker task cancelled")
