from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class Platform(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


class BotUser(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    tenant_id: str
    platform: Platform
    platform_id: str  # Telegram chat_id or WhatsApp E.164 number
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["tenant_id"] = ObjectId(self.tenant_id)
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
