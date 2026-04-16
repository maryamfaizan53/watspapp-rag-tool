from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


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
    messages_per_month: int = 5_000
    rate_limit_per_minute: int = 60


class TenantUsage(BaseModel):
    message_count_month: int = 0
    active_users_month: int = 0


class TenantBase(BaseModel):
    name: str
    plan: TenantPlan = TenantPlan.starter
    status: TenantStatus = TenantStatus.active
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    quota: TenantQuota = Field(default_factory=TenantQuota)
    usage: TenantUsage = Field(default_factory=TenantUsage)


class TenantCreate(TenantBase):
    pass


class TenantUpdate(TenantBase):
    name: Optional[str] = None
    plan: Optional[TenantPlan] = None
    status: Optional[TenantStatus] = None


class TenantSchema(TenantBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
