import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin
from app.db import get_db, faiss_store
from app.db.models import Document, DocumentChunk, AdminUser
from app.services.ingestion import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/tenants/{tenant_id}/documents", tags=["Documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "text/plain"}
MAX_FILE_SIZE_BYTES = 52_428_800  # 50 MB


def _serialize_doc(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "tenant_id": str(doc.tenant_id),
        "name": doc.name,
        "content_hash": doc.content_hash,
        "file_size_bytes": doc.file_size_bytes,
        "mime_type": doc.mime_type,
        "status": doc.status,
        "error_message": doc.error_message,
        "chunk_count": doc.chunk_count,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "ready_at": doc.ready_at.isoformat() if doc.ready_at else None,
    }


@router.get("")
async def list_documents(
    tenant_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    query = select(Document).where(Document.tenant_id == tid)
    if status:
        query = query.where(Document.status == status)

    query = query.order_by(Document.uploaded_at.desc())
    result = await db.execute(query)
    docs = result.scalars().all()

    return {"items": [_serialize_doc(d) for d in docs], "total": len(docs)}


@router.post("", status_code=202)
async def upload_document(
    tenant_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID")

    # Validate MIME type
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{mime_type}'. Accepted: PDF, plain text.",
        )

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit.",
        )

    # Deduplication check
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    result = await db.execute(
        select(Document).where(
            and_(Document.tenant_id == tid, Document.content_hash == content_hash)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document is already in the knowledge base.",
        )

    # Create Document record
    doc = Document(
        tenant_id=tid,
        name=file.filename or "unnamed",
        content_hash=content_hash,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Store file bytes temporarily for background processing
    # In production, use cloud storage (S3, etc.)
    import tempfile
    import os

    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"doc_{doc.id}.bin")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    background_tasks.add_task(process_document, tenant_id, str(doc.id), temp_path)

    return {
        "id": str(doc.id),
        "name": doc.name,
        "status": doc.status,
        "file_size_bytes": doc.file_size_bytes,
        "mime_type": doc.mime_type,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


@router.get("/{document_id}")
async def get_document(
    tenant_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    try:
        tid = UUID(tenant_id)
        did = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = await db.execute(
        select(Document).where(
            and_(Document.id == did, Document.tenant_id == tid)
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return _serialize_doc(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    tenant_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> None:
    try:
        tid = UUID(tenant_id)
        did = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")

    # Get document
    result = await db.execute(
        select(Document).where(
            and_(Document.id == did, Document.tenant_id == tid)
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete associated chunks first, then document (respects FK constraint)
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(DocumentChunk).where(DocumentChunk.document_id == did))
    await db.execute(sql_delete(Document).where(Document.id == did))
    await db.commit()

    # Rebuild FAISS index cache
    faiss_store.evict_from_cache(tenant_id)

    logger.info("Deleted document %s from tenant %s", document_id, tenant_id)
