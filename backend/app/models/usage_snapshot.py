from datetime import date, datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class UsageSnapshot(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    tenant_id: str
    date: date  # UTC midnight day boundary
    message_count: int = 0
    active_users: int = 0
    voice_message_count: int = 0
    avg_latency_ms: int = 0

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["tenant_id"] = ObjectId(self.tenant_id)
        data["date"] = datetime.combine(self.date, datetime.min.time()).replace(tzinfo=timezone.utc)
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
