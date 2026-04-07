from datetime import date, datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_admin
from app.db.mongo import get_db
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/admin/tenants/{tenant_id}/metrics", tags=["Metrics"])


@router.get("")
async def get_metrics(
    tenant_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()

    # Verify tenant exists
    tenant = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    query: dict = {"tenant_id": ObjectId(tenant_id)}
    if from_date or to_date:
        date_filter: dict = {}
        if from_date:
            date_filter["$gte"] = datetime.combine(from_date, datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
        if to_date:
            date_filter["$lte"] = datetime.combine(to_date, datetime.max.time()).replace(
                tzinfo=timezone.utc
            )
        query["date"] = date_filter

    cursor = db.usage_snapshots.find(query).sort("date", -1).limit(90)
    snapshots = await cursor.to_list(length=90)

    total_messages = sum(s["message_count"] for s in snapshots)
    total_users = sum(s["active_users"] for s in snapshots)
    avg_latency = (
        int(sum(s["avg_latency_ms"] for s in snapshots) / len(snapshots)) if snapshots else 0
    )

    daily = []
    for s in snapshots:
        d = s["date"]
        daily.append(
            {
                "date": d.date().isoformat() if hasattr(d, "date") else str(d)[:10],
                "message_count": s["message_count"],
                "active_users": s["active_users"],
            }
        )

    return {
        "tenant_id": tenant_id,
        "message_count": total_messages,
        "active_users": total_users,
        "avg_latency_ms": avg_latency,
        "daily_breakdown": daily,
    }
