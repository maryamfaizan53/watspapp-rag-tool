from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field

SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes


class ConversationStatus(str, Enum):
    active = "active"
    expired = "expired"


class Conversation(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    tenant_id: str
    bot_user_id: str
    platform: str  # telegram | whatsapp
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    status: ConversationStatus = ConversationStatus.active

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def is_expired(self) -> bool:
        """Returns True if inactivity exceeds 30 minutes."""
        now = datetime.now(timezone.utc)
        last = self.last_message_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).total_seconds() > SESSION_TIMEOUT_SECONDS

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["tenant_id"] = ObjectId(self.tenant_id)
        data["bot_user_id"] = ObjectId(self.bot_user_id)
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
