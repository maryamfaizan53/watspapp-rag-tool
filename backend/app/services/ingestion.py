import hashlib
import io
import logging
from datetime import datetime, timezone
from uuid import UUID

import pdfplumber

from app.db import faiss_store, AsyncSessionLocal
from app.db.models import Document, DocumentChunk
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


async def process_document(tenant_id: str, document_id: str, file_path: str) -> None:
    """
    Full ingestion pipeline: pending → processing → ready (or failed).
    Called as a BackgroundTask after upload.
    """
    tid = UUID(tenant_id)
    did = UUID(document_id)

    async with AsyncSessionLocal() as db:
        # Fetch document record
        doc = await db.get(Document, did)
        if not doc:
            logger.error("Document %s not found for ingestion", document_id)
            return

        # Update status → processing
        doc.status = "processing"
        await db.commit()

        try:
            # Read file bytes from temp storage
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            mime_type = doc.mime_type
            chunks = chunk_document(file_bytes, mime_type)

            if not chunks:
                raise ValueError("Document produced zero chunks after parsing")

            # Embed all chunks
            texts = [c["text"] for c in chunks]
            vectors = embed_batch(texts)

            # Add to FAISS and collect assigned faiss_vector_ids
            # Placeholder IDs for FAISS internal mapping
            placeholder_ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            faiss_ids = faiss_store.add_vectors(tenant_id, vectors, placeholder_ids)

            # Create DocumentChunk records
            for i, (chunk_meta, faiss_id) in enumerate(zip(chunks, faiss_ids)):
                chunk = DocumentChunk(
                    document_id=did,
                    tenant_id=tid,
                    chunk_index=i,
                    text=chunk_meta["text"],
                    faiss_vector_id=faiss_id,
                    page_number=chunk_meta.get("page_number"),
                )
                db.add(chunk)
            
            await db.commit()

            # Optional: update FAISS id_map with real DB IDs? 
            # In PostgreSQL we use UUIDs, let's keep it consistent.
            # Re-fetch chunks to get their real IDs (though FAISS store used placeholders)
            # For simplicity, we'll keep the placeholders in FAISS if we search by them, 
            # but usually we search and get faiss_vector_id, then fetch from DB.

            # Mark document ready
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            doc.ready_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "Ingested document %s for tenant %s: %d chunks", document_id, tenant_id, len(chunks)
            )

        except Exception as exc:
            logger.exception("Ingestion failed for document %s: %s", document_id, exc)
            # Rollback and mark failed
            await db.rollback()
            doc = await db.get(Document, did) # re-fetch after rollback
            if doc:
                doc.status = "failed"
                doc.error_message = str(exc)
                await db.commit()
        finally:
            # Cleanup temp file
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
