from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentChunkBase(BaseModel):
    document_id: UUID
    tenant_id: UUID
    chunk_index: int
    text: str
    faiss_vector_id: int  # index position in tenant's FAISS file
    page_number: Optional[int] = None  # source page (PDFs only)


class DocumentChunkCreate(DocumentChunkBase):
    pass


class DocumentChunkSchema(DocumentChunkBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
