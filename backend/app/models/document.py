from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    tenant_id: str
    name: str
    content_hash: str  # SHA-256 of file content (deduplication key)
    file_size_bytes: int
    mime_type: str  # application/pdf | text/plain
    status: DocumentStatus = DocumentStatus.pending
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ready_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["tenant_id"] = ObjectId(self.tenant_id)
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
