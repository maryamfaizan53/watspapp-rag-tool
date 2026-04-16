from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageSnapshotBase(BaseModel):
    tenant_id: UUID
    date: date  # UTC midnight day boundary
    message_count: int = 0
    active_users: int = 0
    voice_message_count: int = 0
    avg_latency_ms: int = 0


class UsageSnapshotCreate(UsageSnapshotBase):
    pass


class UsageSnapshotSchema(UsageSnapshotBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
