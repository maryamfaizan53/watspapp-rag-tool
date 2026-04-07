from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    document_id: str
    tenant_id: str
    chunk_index: int
    text: str
    faiss_vector_id: int  # index position in tenant's FAISS file
    page_number: Optional[int] = None  # source page (PDFs only)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        data["document_id"] = ObjectId(self.document_id)
        data["tenant_id"] = ObjectId(self.tenant_id)
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data
