from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class DocumentBase(BaseModel):
    tenant_id: UUID
    name: str
    content_hash: str  # SHA-256 of file content (deduplication key)
    file_size_bytes: int
    mime_type: str  # application/pdf | text/plain
    status: DocumentStatus = DocumentStatus.pending
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
    uploaded_at: datetime
    ready_at: Optional[datetime] = None


class DocumentCreate(BaseModel):
    tenant_id: UUID
    name: str
    content_hash: str
    file_size_bytes: int
    mime_type: str


class DocumentSchema(DocumentBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
