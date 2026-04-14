from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin
from app.db import get_db
from app.db.models import Tenant, UsageSnapshot, AdminUser

router = APIRouter(prefix="/admin/tenants/{tenant_id}/metrics", tags=["Metrics"])


@router.get("")
async def get_metrics(
    tenant_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    # Verify tenant exists
    tenant = await db.get(Tenant, tid)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    query = select(UsageSnapshot).where(UsageSnapshot.tenant_id == tid)
    
    filters = []
    if from_date:
        filters.append(UsageSnapshot.date >= from_date)
    if to_date:
        filters.append(UsageSnapshot.date <= to_date)
    
    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(UsageSnapshot.date.desc()).limit(90)
    result = await db.execute(query)
    snapshots = result.scalars().all()

    total_messages = sum(s.message_count for s in snapshots)
    total_users = sum(s.active_users for s in snapshots)
    avg_latency = (
        int(sum(s.avg_latency_ms for s in snapshots) / len(snapshots)) if snapshots else 0
    )

    daily = []
    for s in snapshots:
        daily.append(
            {
                "date": s.date.isoformat(),
                "message_count": s.message_count,
                "active_users": s.active_users,
            }
        )

    return {
        "tenant_id": tenant_id,
        "message_count": total_messages,
        "active_users": total_users,
        "avg_latency_ms": avg_latency,
        "daily_breakdown": daily,
    }
