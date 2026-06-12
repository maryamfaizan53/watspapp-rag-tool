"""
Integration tests: document upload endpoints + RAG query path.

These tests run against the real FastAPI app with the DB session and admin
auth overridden, so no database / Redis / network is required.

Notes vs. the old version of this file:
- FALLBACK_NO_DATA no longer exists (rag.py was rewritten); removed.
- rag.answer_query now pre-fetches live PSX data for detected symbols and
  uses safe_generate_with_tools on the no-live-data path, so we patch
  app.services.rag._prefetch_stock_data and llm.safe_generate_with_tools —
  otherwise a query like "What is OGDC EPS?" would hit real network calls.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.api.auth import get_current_admin

TENANT_ID = str(uuid.uuid4())


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def mock_db():
    """Async DB session mock whose execute() result is configurable per-test."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture()
def client(mock_db):
    """TestClient with DB + admin auth overridden and rate limiting disabled."""
    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_admin] = lambda: MagicMock(email="admin@test.local")

    # slowapi limiter would otherwise try to reach Redis storage on each request
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    with patch("app.api.documents.process_document", new_callable=AsyncMock):
        yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


def _no_duplicate(db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)


def _has_duplicate(db):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result)


# ── Upload endpoint ───────────────────────────────────────────────────


def test_upload_txt_returns_202(client, mock_db):
    _no_duplicate(mock_db)
    resp = client.post(
        f"/admin/tenants/{TENANT_ID}/documents",
        files={"file": ("psx-faq.txt", b"OGDC is an oil and gas company.", "text/plain")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["name"] == "psx-faq.txt"


def test_upload_duplicate_returns_409(client, mock_db):
    _has_duplicate(mock_db)
    resp = client.post(
        f"/admin/tenants/{TENANT_ID}/documents",
        files={"file": ("psx-faq.txt", b"OGDC is an oil and gas company.", "text/plain")},
    )
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()


def test_upload_unsupported_mime_returns_415(client, mock_db):
    _no_duplicate(mock_db)
    resp = client.post(
        f"/admin/tenants/{TENANT_ID}/documents",
        files={"file": ("virus.exe", b"\x00\x01", "application/x-msdownload")},
    )
    assert resp.status_code == 415


def test_upload_invalid_tenant_id_returns_400(client, mock_db):
    _no_duplicate(mock_db)
    resp = client.post(
        "/admin/tenants/not-a-uuid/documents",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


# ── RAG query path (service-level integration) ────────────────────────


@pytest.mark.asyncio
async def test_rag_query_with_context_uses_kb_and_live_data():
    """KB chunk within distance threshold + prefetched live data → live-data prompt path."""
    from app.services import rag

    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    chunk = MagicMock()
    chunk.id = uuid.uuid4()
    chunk.text = "OGDC reported EPS of 25.4 PKR for FY2025."

    db = AsyncMock()

    async def mock_execute(query):
        result = MagicMock()
        q = str(query)
        if "document_chunks" in q:
            result.scalar_one_or_none.return_value = chunk
        else:
            result.scalars.return_value.all.return_value = []
        return result

    db.execute.side_effect = mock_execute

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(str(chunk.id), 0.4)]),
        patch(
            "app.services.rag._prefetch_stock_data",
            new_callable=AsyncMock,
            return_value='{"symbol": "OGDC", "price": 132.5, "status": "ok"}',
        ),
        patch(
            "app.services.rag.llm.safe_generate",
            new_callable=AsyncMock,
            return_value="OGDC's EPS for FY2025 was 25.4 PKR.",
        ) as mock_gen,
    ):
        answer, chunk_ids = await rag.answer_query(db, tenant_id, conv_id, "What is OGDC EPS?")

    assert "25.4" in answer
    assert chunk_ids == [str(chunk.id)]
    prompt = mock_gen.call_args[0][0]
    assert "OGDC reported EPS" in prompt  # KB context injected
    assert '"status": "ok"' in prompt     # live data injected


@pytest.mark.asyncio
async def test_rag_query_llm_down_returns_fallback():
    """Both LLM providers down → graceful FALLBACK_LLM_DOWN, never an exception."""
    from app.services import rag
    from app.services.rag import FALLBACK_LLM_DOWN

    db = AsyncMock()

    async def mock_execute(query):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    db.execute.side_effect = mock_execute

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=""),
        # safe_generate_with_tools swallows provider errors internally and
        # returns None when both providers / breakers are down — emulate that.
        patch(
            "app.services.rag.llm.safe_generate_with_tools",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        answer, chunk_ids = await rag.answer_query(db, uuid.uuid4(), uuid.uuid4(), "hello")

    assert answer == FALLBACK_LLM_DOWN
    assert chunk_ids == []
