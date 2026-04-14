"""
Integration test: document upload → ingestion pipeline → RAG query returns content.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_admin
from app.db.models import AdminUser

TENANT_ID = uuid.uuid4()

FIXTURE_TEXT = (
    "OGDC Annual Report 2024. "
    "The company reported earnings per share (EPS) of PKR 45.23 for FY2024. "
    "Return on equity stood at 18.7 percent. "
    "P/E ratio as of December 2024 was 7.3."
)


def _fake_admin() -> AdminUser:
    return AdminUser(
        id=uuid.uuid4(),
        email="admin@test.com",
        hashed_password="x",
        role="super_admin",
        is_active=True,
    )


def _common_patches(mock_db):
    """Patches needed for every document endpoint test."""
    return [
        # Patch get_db WHERE IT IS USED (imported name in each consumer module)
        patch("app.api.documents.get_db", return_value=mock_db),
        # Patch lifespan hooks via their LOCAL names in main.py
        patch("app.main.connect_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.connect_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.start_worker"),
        patch("app.main.stop_worker"),
        # Redis dependency (used by slowapi middleware)
        patch("app.db.redis.get_redis", return_value=AsyncMock()),
    ]


@pytest.mark.asyncio
async def test_upload_document_accepted():
    """POST /admin/tenants/{id}/documents with a valid TXT file returns HTTP 202."""
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    patches = _common_patches(mock_db) + [
        patch("app.api.documents.process_document", new_callable=AsyncMock),
    ]

    entered = [p.__enter__() for p in patches]
    try:
        from app.main import create_app

        test_app = create_app()
        test_app.dependency_overrides[get_current_admin] = _fake_admin

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                f"/admin/tenants/{TENANT_ID}/documents",
                files={"file": ("report.txt", FIXTURE_TEXT.encode(), "text/plain")},
            )
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_duplicate_document_returns_409():
    """Uploading the same content hash twice returns HTTP 409."""
    import hashlib

    existing_hash = hashlib.sha256(FIXTURE_TEXT.encode()).hexdigest()

    mock_db = AsyncMock()
    
    existing_doc = MagicMock()
    existing_doc.content_hash = existing_hash
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_doc

    patches = _common_patches(mock_db)
    entered = [p.__enter__() for p in patches]
    try:
        from app.main import create_app

        test_app = create_app()
        test_app.dependency_overrides[get_current_admin] = _fake_admin

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                f"/admin/tenants/{TENANT_ID}/documents",
                files={"file": ("report.txt", FIXTURE_TEXT.encode(), "text/plain")},
            )
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_ingestion_pipeline_content_queryable_via_rag():
    """
    After ingestion, content from the fixture document is present in chunks
    and the RAG service returns a non-empty answer referencing that content.
    """
    from app.services.ingestion import chunk_document

    file_bytes = FIXTURE_TEXT.encode()
    chunks = chunk_document(file_bytes, "text/plain")

    all_text = " ".join(c["text"] for c in chunks)
    assert "EPS" in all_text or "earnings" in all_text.lower()
    assert "7.3" in all_text
    assert len(chunks) >= 1

    mock_db = AsyncMock()
    
    chunk = MagicMock()
    chunk.id = uuid.uuid4()
    chunk.text = chunks[0]["text"]
    
    async def mock_execute(query):
        result = MagicMock()
        if "document_chunks" in str(query):
            result.scalar_one_or_none.return_value = chunk
        elif "messages" in str(query):
            result.scalars.return_value.all.return_value = []
        return result
    
    mock_db.execute.side_effect = mock_execute

    query_vector = np.zeros(384, dtype="float32")

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=query_vector),
        patch("app.services.rag.faiss_store.search", return_value=[(f"{uuid.uuid4()}_0", 0.05)]),
        patch("app.services.rag.llm.safe_generate", new_callable=AsyncMock, return_value="OGDC EPS is PKR 45.23 for FY2024."),
    ):
        from app.services.rag import FALLBACK_NO_DATA, answer_query

        answer, _ = await answer_query(mock_db, uuid.uuid4(), uuid.uuid4(), "What is OGDC EPS?")

    assert answer != FALLBACK_NO_DATA
    assert "45.23" in answer or "EPS" in answer
