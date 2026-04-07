from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    user = "user"
    bot = "bot"


class ContentType(str, Enum):
    text = "text"
    audio = "audio"


class Message(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    conversation_id: str
    tenant_id: str
    role: MessageRole
    content_type: ContentType = ContentType.text
    content: str  # raw text or audio file reference/URL
    transcription: Optional[str] = None  # populated for audio messages
    rag_context_ids: list[str] = Field(default_factory=list)  # DocumentChunk IDs used
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: Optional[int] = None  # end-to-end response time

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["conversation_id"] = ObjectId(self.conversation_id)
        data["tenant_id"] = ObjectId(self.tenant_id)
        data["rag_context_ids"] = [ObjectId(cid) for cid in self.rag_context_ids]
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
