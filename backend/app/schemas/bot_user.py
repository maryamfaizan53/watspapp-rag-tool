from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class Platform(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


class BotUserBase(BaseModel):
    tenant_id: UUID
    platform: Platform
    platform_id: str  # Telegram chat_id or WhatsApp E.164 number


class BotUserCreate(BotUserBase):
    pass


class BotUserSchema(BotUserBase):
    id: UUID
    created_at: datetime
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)
