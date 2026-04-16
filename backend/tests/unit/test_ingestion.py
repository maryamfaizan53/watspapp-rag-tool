"""Unit tests for the document ingestion service (app/services/ingestion.py)."""
import uuid
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS, chunk_text, compute_sha256


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_chunk_text_single_chunk_for_short_text():
    text = "Short document."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0]["text"] == text


def test_chunk_text_produces_overlap():
    """A text longer than CHUNK_SIZE_CHARS should produce overlapping chunks."""
    text = "A" * (CHUNK_SIZE_CHARS + CHUNK_OVERLAP_CHARS + 100)
    chunks = chunk_text(text, page_number=1)
    assert len(chunks) >= 2
    # Second chunk should start before end of first chunk (overlap)
    first_end = CHUNK_SIZE_CHARS
    second_start = CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS
    assert second_start < first_end


def test_chunk_text_preserves_page_number():
    text = "Some content"
    chunks = chunk_text(text, page_number=5)
    assert all(c["page_number"] == 5 for c in chunks)


def test_compute_sha256_deterministic():
    data = b"test document bytes"
    assert compute_sha256(data) == compute_sha256(data)


def test_compute_sha256_differs_for_different_content():
    assert compute_sha256(b"doc1") != compute_sha256(b"doc2")


# ── Status transitions ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_document_marks_failed_on_missing_file():
    """If file is absent, ingestion sets status=failed."""
    doc_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.mime_type = "application/pdf"
    
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_doc
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch("app.services.ingestion.AsyncSessionLocal", new=mock_session_factory):
        from app.services.ingestion import process_document

        # Pass a non-existent file path
        await process_document(str(tenant_id), str(doc_id), "non_existent_file.bin")

    assert mock_doc.status == "failed"
    assert "No such file or directory" in mock_doc.error_message


@pytest.mark.asyncio
async def test_process_document_happy_path_marks_ready():
    """A valid plain-text document goes through pending→processing→ready."""
    doc_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.mime_type = "text/plain"
    
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_doc
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    import numpy as np
    dummy_vectors = np.zeros((1, 384), dtype="float32")
    
    temp_file = "test_ingest.txt"
    with open(temp_file, "wb") as f:
        f.write(b"Hello PSX. " * 100)

    try:
        with (
            patch("app.services.ingestion.embed_batch", return_value=dummy_vectors),
            patch("app.services.ingestion.faiss_store.add_vectors", return_value=[0]),
            patch("app.services.ingestion.AsyncSessionLocal", new=mock_session_factory),
        ):
            from app.services.ingestion import process_document

            await process_document(str(tenant_id), str(doc_id), temp_file)

        assert mock_doc.status == "ready"
        assert mock_doc.chunk_count > 0
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
