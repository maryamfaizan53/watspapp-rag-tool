import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import get_current_admin
from app.db import faiss_store
from app.db.mongo import get_db
from app.models.admin_user import AdminUser
from app.models.tenant import ChannelConfig, Tenant, TenantPlan, TenantQuota, TenantStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/tenants", tags=["Tenants"])

DEFAULT_QUOTAS = {
    TenantPlan.starter: TenantQuota(messages_per_month=5_000, rate_limit_per_minute=60),
    TenantPlan.growth: TenantQuota(messages_per_month=50_000, rate_limit_per_minute=120),
    TenantPlan.enterprise: TenantQuota(messages_per_month=500_000, rate_limit_per_minute=300),
}


class TenantCreateRequest(BaseModel):
    name: str
    plan: TenantPlan = TenantPlan.starter
    quota: TenantQuota | None = None


class ChannelConfigRequest(BaseModel):
    telegram_bot_token: str | None = None
    whatsapp_account_sid: str | None = None
    whatsapp_auth_token: str | None = None
    whatsapp_from_number: str | None = None


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if "tenant_id" in doc:
        doc["tenant_id"] = str(doc["tenant_id"])
    # Don't expose raw channel secrets
    channels = doc.get("channels", {})
    if "telegram" in channels:
        channels["telegram"]["configured"] = bool(channels["telegram"].get("bot_token"))
        channels["telegram"].pop("bot_token", None)
        channels["telegram"].pop("webhook_url", None)
    if "whatsapp" in channels:
        channels["whatsapp"]["configured"] = bool(channels["whatsapp"].get("account_sid"))
        channels["whatsapp"].pop("account_sid", None)
        channels["whatsapp"].pop("auth_token", None)
    return doc


@router.get("")
async def list_tenants(
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    skip = (page - 1) * limit
    total = await db.tenants.count_documents(query)
    cursor = db.tenants.find(query).skip(skip).limit(limit).sort("created_at", -1)
    items = await cursor.to_list(length=limit)
    return {
        "items": [_serialize(t) for t in items],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", status_code=201)
async def create_tenant(
    body: TenantCreateRequest,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    existing = await db.tenants.find_one({"name": body.name})
    if existing:
        raise HTTPException(status_code=409, detail="A tenant with this name already exists.")

    quota = body.quota or DEFAULT_QUOTAS[body.plan]
    tenant = Tenant(name=body.name, plan=body.plan, quota=quota)
    result = await db.tenants.insert_one(tenant.to_doc())
    doc = await db.tenants.find_one({"_id": result.inserted_id})
    return _serialize(doc)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _serialize(doc)


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: TenantCreateRequest,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    quota = body.quota or DEFAULT_QUOTAS[body.plan]
    await db.tenants.update_one(
        {"_id": ObjectId(tenant_id)},
        {
            "$set": {
                "name": body.name,
                "plan": body.plan.value,
                "quota": quota.model_dump(),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _serialize(doc)


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: str,
    _: AdminUser = Depends(get_current_admin),
) -> None:
    db = get_db()
    tid = ObjectId(tenant_id)

    # Cascade delete: chunks → documents → messages → conversations → bot_users → tenant
    await db.document_chunks.delete_many({"tenant_id": tid})
    await db.documents.delete_many({"tenant_id": tid})
    await db.messages.delete_many({"tenant_id": tid})
    await db.conversations.delete_many({"tenant_id": tid})
    await db.bot_users.delete_many({"tenant_id": tid})
    await db.usage_snapshots.delete_many({"tenant_id": tid})
    faiss_store.delete_tenant_index(tenant_id)

    result = await db.tenants.delete_one({"_id": tid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")


@router.put("/{tenant_id}/channels", status_code=200)
async def configure_channels(
    tenant_id: str,
    body: ChannelConfigRequest,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    update: dict = {"updated_at": datetime.now(timezone.utc)}

    if body.telegram_bot_token is not None:
        update["channels.telegram.bot_token"] = body.telegram_bot_token
        update["channels.telegram.configured"] = True

    if body.whatsapp_account_sid is not None:
        update["channels.whatsapp.account_sid"] = body.whatsapp_account_sid
        update["channels.whatsapp.configured"] = True
    if body.whatsapp_auth_token is not None:
        update["channels.whatsapp.auth_token"] = body.whatsapp_auth_token
    if body.whatsapp_from_number is not None:
        update["channels.whatsapp.from_number"] = body.whatsapp_from_number

    await db.tenants.update_one({"_id": ObjectId(tenant_id)}, {"$set": update})
    return {"ok": True}
