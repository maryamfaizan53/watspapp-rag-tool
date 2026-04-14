from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes


class ConversationStatus(str, Enum):
    active = "active"
    expired = "expired"


class ConversationBase(BaseModel):
    tenant_id: UUID
    bot_user_id: UUID
    platform: str  # telegram | whatsapp
    started_at: datetime
    last_message_at: datetime
    message_count: int = 0
    status: ConversationStatus = ConversationStatus.active


class ConversationCreate(BaseModel):
    tenant_id: UUID
    bot_user_id: UUID
    platform: str


class ConversationSchema(ConversationBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

    def is_expired(self) -> bool:
        """Returns True if inactivity exceeds 30 minutes."""
        now = datetime.now(timezone.utc)
        last = self.last_message_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).total_seconds() > SESSION_TIMEOUT_SECONDS
