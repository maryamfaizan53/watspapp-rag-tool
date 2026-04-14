from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MessageRole(str, Enum):
    user = "user"
    bot = "bot"


class ContentType(str, Enum):
    text = "text"
    audio = "audio"


class MessageBase(BaseModel):
    conversation_id: UUID
    tenant_id: UUID
    role: MessageRole
    content_type: ContentType = ContentType.text
    content: str  # raw text or audio file reference/URL
    transcription: Optional[str] = None  # populated for audio messages
    rag_context_ids: List[str] = Field(default_factory=list)  # DocumentChunk IDs used
    timestamp: datetime
    latency_ms: Optional[int] = None  # end-to-end response time


class MessageCreate(BaseModel):
    conversation_id: UUID
    tenant_id: UUID
    role: MessageRole
    content_type: ContentType = ContentType.text
    content: str
    transcription: Optional[str] = None
    rag_context_ids: List[str] = Field(default_factory=list)
    latency_ms: Optional[int] = None


class MessageSchema(MessageBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
