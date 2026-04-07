import hashlib
import io
import logging
import textwrap
from datetime import datetime, timezone
from typing import Generator

import pdfplumber
from bson import ObjectId

from app.db import faiss_store
from app.db.mongo import get_db
from app.models.document import DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.services.embeddings import embed_batch

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 3000   # ~750 tokens at 4 chars/token (fits 512-1024 token target)
CHUNK_OVERLAP_CHARS = 600  # 20% overlap


def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text_from_pdf(file_bytes: bytes) -> list[tuple[str, int]]:
    """Extract text from PDF. Returns list of (page_text, page_number)."""
    pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((text, i))
    return pages


def chunk_text(text: str, page_number: int | None = None) -> list[dict]:
    """
    Split text into overlapping chunks of ~CHUNK_SIZE_CHARS with CHUNK_OVERLAP_CHARS overlap.
    Returns list of {text, page_number} dicts.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"text": chunk, "page_number": page_number})
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP_CHARS
    return chunks


def chunk_document(file_bytes: bytes, mime_type: str) -> list[dict]:
    """Parse and chunk a document. Returns list of {text, page_number} dicts."""
    raw_chunks: list[dict] = []

    if mime_type == "application/pdf":
        pages = extract_text_from_pdf(file_bytes)
        for page_text, page_num in pages:
            raw_chunks.extend(chunk_text(page_text, page_number=page_num))
    else:
        # plain text
        text = file_bytes.decode("utf-8", errors="replace")
        raw_chunks.extend(chunk_text(text, page_number=None))

    return raw_chunks


async def process_document(tenant_id: str, document_id: str) -> None:
    """
    Full ingestion pipeline: pending → processing → ready (or failed).
    Called as a BackgroundTask after upload.
    """
    db = get_db()
    doc_oid = ObjectId(document_id)

    # Fetch document record
    doc = await db.documents.find_one({"_id": doc_oid})
    if not doc:
        logger.error("Document %s not found for ingestion", document_id)
        return

    # Update status → processing
    await db.documents.update_one(
        {"_id": doc_oid},
        {"$set": {"status": DocumentStatus.processing.value}},
    )

    try:
        # Retrieve file bytes from GridFS or temp storage
        # For Phase 1: file bytes stored temporarily in document record itself
        file_bytes = doc.get("_file_bytes")
        if not file_bytes:
            raise ValueError("File bytes not available for ingestion")

        mime_type = doc["mime_type"]
        chunks = chunk_document(file_bytes, mime_type)

        if not chunks:
            raise ValueError("Document produced zero chunks after parsing")

        # Embed all chunks
        texts = [c["text"] for c in chunks]
        vectors = embed_batch(texts)

        # Add to FAISS + create DocumentChunk records
        chunk_records = []
        for i, (chunk_meta, _) in enumerate(zip(chunks, texts)):
            chunk_records.append(
                DocumentChunk(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    chunk_index=i,
                    text=chunk_meta["text"],
                    faiss_vector_id=-1,  # will be set after FAISS add
                    page_number=chunk_meta.get("page_number"),
                )
            )

        # placeholder chunk_ids for FAISS mapping
        placeholder_ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        faiss_ids = faiss_store.add_vectors(tenant_id, vectors, placeholder_ids)

        # Insert DocumentChunk records with real faiss_vector_ids
        chunk_docs = []
        for record, faiss_id in zip(chunk_records, faiss_ids):
            record.faiss_vector_id = faiss_id
            doc_to_insert = record.to_doc()
            chunk_docs.append(doc_to_insert)

        result = await db.document_chunks.insert_many(chunk_docs)

        # Update FAISS id_map to use real MongoDB ObjectIds
        index, id_map = faiss_store.load_index(tenant_id)
        for faiss_id, inserted_id in zip(faiss_ids, result.inserted_ids):
            id_map[faiss_id] = str(inserted_id)
        faiss_store.save_index(tenant_id, index, id_map)

        # Mark document ready
        await db.documents.update_one(
            {"_id": doc_oid},
            {
                "$set": {
                    "status": DocumentStatus.ready.value,
                    "chunk_count": len(chunks),
                    "ready_at": datetime.now(timezone.utc),
                    "_file_bytes": None,  # free memory
                },
            },
        )
        logger.info(
            "Ingested document %s for tenant %s: %d chunks", document_id, tenant_id, len(chunks)
        )

    except Exception as exc:
        logger.exception("Ingestion failed for document %s: %s", document_id, exc)
        await db.documents.update_one(
            {"_id": doc_oid},
            {
                "$set": {
                    "status": DocumentStatus.failed.value,
                    "error_message": str(exc),
                    "_file_bytes": None,
                }
            },
        )
