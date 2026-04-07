from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class TenantPlan(str, Enum):
    starter = "starter"
    growth = "growth"
    enterprise = "enterprise"


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class TelegramChannelConfig(BaseModel):
    bot_token: Optional[str] = None  # stored encrypted
    webhook_url: Optional[str] = None
    configured: bool = False


class WhatsAppChannelConfig(BaseModel):
    account_sid: Optional[str] = None  # stored encrypted
    auth_token: Optional[str] = None   # stored encrypted
    from_number: Optional[str] = None
    configured: bool = False


class ChannelConfig(BaseModel):
    telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)
    whatsapp: WhatsAppChannelConfig = Field(default_factory=WhatsAppChannelConfig)


class TenantQuota(BaseModel):
    messages_per_month: int = 10_000
    rate_limit_per_minute: int = 60


class TenantUsage(BaseModel):
    message_count_month: int = 0
    active_users_month: int = 0


class Tenant(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    plan: TenantPlan = TenantPlan.starter
    status: TenantStatus = TenantStatus.active
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    quota: TenantQuota = Field(default_factory=TenantQuota)
    usage: TenantUsage = Field(default_factory=TenantUsage)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
