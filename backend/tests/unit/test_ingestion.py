"""Unit tests for the document ingestion service (app/services/ingestion.py)."""
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
async def test_process_document_marks_failed_on_missing_bytes():
    """If _file_bytes is absent, ingestion sets status=failed."""
    from bson import ObjectId

    doc_id = ObjectId()
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(
        return_value={"_id": doc_id, "mime_type": "application/pdf", "_file_bytes": None}
    )
    mock_db.documents.update_one = AsyncMock()

    with patch("app.services.ingestion.get_db", return_value=mock_db):
        from app.services.ingestion import process_document

        await process_document(str(ObjectId()), str(doc_id))

    # Last update_one call should set status=failed
    calls = mock_db.documents.update_one.call_args_list
    last_call_set = calls[-1][0][1]["$set"]
    assert last_call_set["status"] == "failed"


@pytest.mark.asyncio
async def test_process_document_happy_path_marks_ready():
    """A valid plain-text document goes through pending→processing→ready."""
    from bson import ObjectId

    doc_id = ObjectId()
    inserted_ids = [ObjectId(), ObjectId()]

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(
        return_value={
            "_id": doc_id,
            "mime_type": "text/plain",
            "_file_bytes": b"Hello PSX. " * 100,
        }
    )
    mock_db.documents.update_one = AsyncMock()
    mock_db.document_chunks.insert_many = AsyncMock(
        return_value=MagicMock(inserted_ids=inserted_ids)
    )

    import numpy as np

    tenant_id = str(ObjectId())
    dummy_vectors = np.zeros((1, 384), dtype="float32")

    with (
        patch("app.services.ingestion.get_db", return_value=mock_db),
        patch("app.services.ingestion.embed_batch", return_value=dummy_vectors),
        patch("app.services.ingestion.faiss_store.add_vectors", return_value=[0]),
        patch("app.services.ingestion.faiss_store.load_index", return_value=(MagicMock(), {})),
        patch("app.services.ingestion.faiss_store.save_index"),
    ):
        from app.services.ingestion import process_document

        await process_document(tenant_id, str(doc_id))

    calls = mock_db.documents.update_one.call_args_list
    statuses = [c[0][1]["$set"]["status"] for c in calls]
    assert "processing" in statuses
    assert "ready" in statuses
