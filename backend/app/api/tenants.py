import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_admin
from app.db import get_db, faiss_store
from app.db.models import Tenant, AdminUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/tenants", tags=["Tenants"])


# ── Schemas ──────────────────────────────────────────────────────────


class TenantQuota(BaseModel):
    messages_per_month: int = 5_000
    rate_limit_per_minute: int = 60


class TenantPlan(str):
    starter = "starter"
    growth = "growth"
    enterprise = "enterprise"


class TenantCreateRequest(BaseModel):
    name: str
    plan: str = TenantPlan.starter
    quota: Optional[TenantQuota] = None


class ChannelConfigRequest(BaseModel):
    telegram_bot_token: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_app_secret: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────


def _serialize(tenant: Tenant) -> dict:
    """Convert tenant model to API response, hiding secrets."""
    data = {
        "id": str(tenant.id),
        "name": tenant.name,
        "plan": tenant.plan,
        "status": tenant.status,
        "channels": tenant.channels.copy() if tenant.channels else {},
        "quota": tenant.quota if tenant.quota else {"messages_per_month": 5000, "rate_limit_per_minute": 60},
        "usage": tenant.usage if tenant.usage else {"message_count_month": 0, "active_users_month": 0},
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }

    # Hide raw channel secrets
    channels = data.get("channels", {})
    if "telegram" in channels:
        channels["telegram"]["configured"] = bool(channels["telegram"].get("bot_token"))
        channels["telegram"].pop("bot_token", None)
        channels["telegram"].pop("webhook_url", None)
    if "whatsapp" in channels:
        channels["whatsapp"]["configured"] = bool(channels["whatsapp"].get("access_token"))
        channels["whatsapp"].pop("access_token", None)
        channels["whatsapp"].pop("app_secret", None)

    return data


# ── Routes ───────────────────────────────────────────────────────────


@router.get("")
async def list_tenants(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    skip = (page - 1) * limit

    # Build query
    query = select(Tenant)
    if status:
        query = query.where(Tenant.status == status)

    # Get total count
    count_result = await db.execute(select(func.count()).select_from(Tenant).where(Tenant.status == status if status else True))
    total = count_result.scalar()

    # Get paginated items
    query = query.offset(skip).limit(limit).order_by(Tenant.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [_serialize(t) for t in items],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 1,
    }


@router.post("", status_code=201)
async def create_tenant(
    body: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    # Check existing
    result = await db.execute(select(Tenant).where(Tenant.name == body.name))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="A tenant with this name already exists.")

    quota = body.quota.dict() if body.quota else {"messages_per_month": 5000, "rate_limit_per_minute": 60}

    tenant = Tenant(
        name=body.name,
        plan=body.plan,
        quota=quota,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return _serialize(tenant)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return _serialize(tenant)


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    quota = body.quota.dict() if body.quota else {"messages_per_month": 5000, "rate_limit_per_minute": 60}

    tenant.name = body.name
    tenant.plan = body.plan
    tenant.quota = quota
    tenant.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(tenant)

    return _serialize(tenant)


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> None:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from sqlalchemy import delete as sql_delete
    from app.db.models import Document, DocumentChunk, BotUser, Conversation, Message, UsageSnapshot

    # Delete in FK-safe order (children before parents)
    await db.execute(sql_delete(DocumentChunk).where(DocumentChunk.tenant_id == tid))
    await db.execute(sql_delete(Document).where(Document.tenant_id == tid))
    await db.execute(sql_delete(Message).where(Message.tenant_id == tid))
    await db.execute(sql_delete(Conversation).where(Conversation.tenant_id == tid))
    await db.execute(sql_delete(BotUser).where(BotUser.tenant_id == tid))
    await db.execute(sql_delete(UsageSnapshot).where(UsageSnapshot.tenant_id == tid))
    await db.execute(sql_delete(Tenant).where(Tenant.id == tid))
    await db.commit()

    faiss_store.delete_tenant_index(tenant_id)
    logger.info("Deleted tenant %s and all related data", tenant_id)


@router.put("/{tenant_id}/channels", status_code=200)
async def configure_channels(
    tenant_id: str,
    body: ChannelConfigRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Deep copy to force SQLAlchemy to detect the JSON mutation
    import copy
    channels = copy.deepcopy(tenant.channels) if tenant.channels else {}

    if body.telegram_bot_token is not None:
        channels.setdefault("telegram", {})
        channels["telegram"]["bot_token"] = body.telegram_bot_token
        channels["telegram"]["configured"] = True

    if body.whatsapp_access_token is not None:
        channels.setdefault("whatsapp", {})
        channels["whatsapp"]["access_token"] = body.whatsapp_access_token
        channels["whatsapp"]["configured"] = True
    if body.whatsapp_phone_number_id is not None:
        channels.setdefault("whatsapp", {})
        channels["whatsapp"]["phone_number_id"] = body.whatsapp_phone_number_id
    if body.whatsapp_app_secret is not None:
        channels.setdefault("whatsapp", {})
        channels["whatsapp"]["app_secret"] = body.whatsapp_app_secret
    if body.whatsapp_verify_token is not None:
        channels.setdefault("whatsapp", {})
        channels["whatsapp"]["verify_token"] = body.whatsapp_verify_token

    tenant.channels = channels
    flag_modified(tenant, "channels")
    tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True}
