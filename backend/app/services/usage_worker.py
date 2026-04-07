"""
Daily UsageSnapshot worker.
Runs as an asyncio background task started at app lifespan.
Every 24 hours (or at the next midnight UTC), computes daily stats per active tenant
and upserts into the usage_snapshots collection.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from bson import ObjectId

from app.db.mongo import get_db

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def _compute_snapshot_for_tenant(db, tenant_id: ObjectId, target_date: date) -> None:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    pipeline = [
        {
            "$match": {
                "tenant_id": tenant_id,
                "timestamp": {"$gte": start, "$lt": end},
                "role": "user",
            }
        },
        {
            "$group": {
                "_id": None,
                "message_count": {"$sum": 1},
                "voice_message_count": {
                    "$sum": {"$cond": [{"$eq": ["$content_type", "voice"]}, 1, 0]}
                },
                "avg_latency_ms": {"$avg": "$latency_ms"},
                "bot_user_ids": {"$addToSet": "$bot_user_id"},
            }
        },
    ]

    cursor = db.messages.aggregate(pipeline)
    rows = await cursor.to_list(length=1)

    if not rows:
        return  # no activity for this tenant on this date

    row = rows[0]
    snapshot = {
        "tenant_id": tenant_id,
        "date": start,
        "message_count": row["message_count"],
        "active_users": len(row["bot_user_ids"]),
        "voice_message_count": row["voice_message_count"],
        "avg_latency_ms": round(row["avg_latency_ms"] or 0, 2),
    }

    await db.usage_snapshots.update_one(
        {"tenant_id": tenant_id, "date": start},
        {"$set": snapshot},
        upsert=True,
    )
    logger.debug(
        "UsageSnapshot upserted for tenant %s on %s: %d messages",
        tenant_id,
        target_date,
        snapshot["message_count"],
    )


async def _run_daily_snapshot() -> None:
    """Compute snapshots for yesterday across all active tenants."""
    try:
        db = get_db()
        yesterday = date.today() - timedelta(days=1)
        cursor = db.tenants.find({"status": "active"}, {"_id": 1})
        tenants = await cursor.to_list(length=None)
        logger.info("Running daily UsageSnapshot for %d tenants (date=%s)", len(tenants), yesterday)
        for tenant in tenants:
            try:
                await _compute_snapshot_for_tenant(db, tenant["_id"], yesterday)
            except Exception:
                logger.exception("Snapshot failed for tenant %s", tenant["_id"])
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
