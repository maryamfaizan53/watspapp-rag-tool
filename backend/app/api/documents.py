import hashlib
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.api.auth import get_current_admin
from app.db import faiss_store
from app.db.mongo import get_db
from app.models.admin_user import AdminUser
from app.models.document import Document, DocumentStatus
from app.services.ingestion import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/tenants/{tenant_id}/documents", tags=["Documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "text/plain"}
MAX_FILE_SIZE_BYTES = 52_428_800  # 50 MB


def _serialize_doc(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    doc["tenant_id"] = str(doc["tenant_id"])
    doc.pop("_file_bytes", None)
    return doc


@router.get("")
async def list_documents(
    tenant_id: str,
    status: str | None = None,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    query: dict = {"tenant_id": ObjectId(tenant_id)}
    if status:
        query["status"] = status
    cursor = db.documents.find(query, {"_file_bytes": 0}).sort("uploaded_at", -1)
    docs = await cursor.to_list(length=200)
    return {"items": [_serialize_doc(d) for d in docs], "total": len(docs)}


@router.post("", status_code=202)
async def upload_document(
    tenant_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()

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
    existing = await db.documents.find_one(
        {"tenant_id": ObjectId(tenant_id), "content_hash": content_hash}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document is already in the knowledge base.",
        )

    # Create Document record (store bytes temporarily for background ingestion)
    doc = Document(
        tenant_id=tenant_id,
        name=file.filename or "unnamed",
        content_hash=content_hash,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        status=DocumentStatus.pending,
    )
    doc_data = doc.to_doc()
    doc_data["_file_bytes"] = file_bytes  # temporary storage for background task
    result = await db.documents.insert_one(doc_data)
    document_id = str(result.inserted_id)

    background_tasks.add_task(process_document, tenant_id, document_id)

    return {
        "id": document_id,
        "name": doc.name,
        "status": doc.status.value,
        "file_size_bytes": doc.file_size_bytes,
        "mime_type": doc.mime_type,
        "uploaded_at": doc.uploaded_at.isoformat(),
    }


@router.get("/{document_id}")
async def get_document(
    tenant_id: str,
    document_id: str,
    _: AdminUser = Depends(get_current_admin),
) -> dict:
    db = get_db()
    doc = await db.documents.find_one(
        {"_id": ObjectId(document_id), "tenant_id": ObjectId(tenant_id)},
        {"_file_bytes": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_doc(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    tenant_id: str,
    document_id: str,
    _: AdminUser = Depends(get_current_admin),
) -> None:
    db = get_db()
    doc = await db.documents.find_one(
        {"_id": ObjectId(document_id), "tenant_id": ObjectId(tenant_id)}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete DocumentChunk records
    await db.document_chunks.delete_many({"document_id": ObjectId(document_id)})

    # Delete Document record
    await db.documents.delete_one({"_id": ObjectId(document_id)})

    # Rebuild FAISS index without deleted document's vectors
    # (Simple approach: evict cache; vectors remain but are orphaned — acceptable for Phase 1)
    faiss_store.evict_from_cache(tenant_id)

    logger.info("Deleted document %s from tenant %s", document_id, tenant_id)
