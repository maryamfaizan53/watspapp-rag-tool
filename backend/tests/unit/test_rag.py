"""Unit tests for the RAG pipeline (app/services/rag.py)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TENANT_ID = uuid.uuid4()
CONV_ID = uuid.uuid4()
CHUNK_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_answer_query_empty_kb_returns_fallback():
    """When FAISS returns no results, the fallback 'no data' message is returned."""
    mock_db = AsyncMock()
    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[]),
    ):
        from app.services.rag import FALLBACK_NO_DATA, answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert answer == FALLBACK_NO_DATA
        assert chunk_ids == []


@pytest.mark.asyncio
async def test_answer_query_llm_unavailable_returns_fallback():
    """When the LLM is unavailable (safe_generate returns None), the degraded fallback is used."""
    mock_db = AsyncMock()
    
    # Mock DocumentChunk
    chunk = MagicMock()
    chunk.id = CHUNK_ID
    chunk.text = "OGDC P/E is 8.5"
    
    async def mock_execute(query):
        result = MagicMock()
        if "document_chunks" in str(query):
            result.scalar_one_or_none.return_value = chunk
        elif "messages" in str(query):
            result.scalars.return_value.all.return_value = []
        return result
    
    mock_db.execute.side_effect = mock_execute

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(f"{DOC_ID}_0", 0.1)]),
        patch("app.services.rag.llm.safe_generate", new_callable=AsyncMock, return_value=None),
    ):
        from app.services.rag import FALLBACK_LLM_DOWN, answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert answer == FALLBACK_LLM_DOWN
        assert chunk_ids == []


@pytest.mark.asyncio
async def test_answer_query_returns_llm_response():
    """Happy path: FAISS finds chunks → LLM returns answer → returned to caller."""
    mock_db = AsyncMock()
    
    # Mock DocumentChunk
    chunk = MagicMock()
    chunk.id = CHUNK_ID
    chunk.text = "OGDC P/E ratio is 7.3"
    
    async def mock_execute(query):
        result = MagicMock()
        if "document_chunks" in str(query):
            result.scalar_one_or_none.return_value = chunk
        elif "messages" in str(query):
            result.scalars.return_value.all.return_value = []
        return result
    
    mock_db.execute.side_effect = mock_execute

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(f"{DOC_ID}_0", 0.05)]),
        patch(
            "app.services.rag.llm.safe_generate",
            new_callable=AsyncMock,
            return_value="OGDC P/E ratio is 7.3",
        ),
    ):
        from app.services.rag import answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert "7.3" in answer
        assert chunk_ids == [str(CHUNK_ID)]


@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_new_when_no_existing():
    """A new Conversation is created when none exists in the DB."""
    user_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from app.services.rag import get_or_create_conversation

    await get_or_create_conversation(mock_db, TENANT_ID, user_id, "telegram")
    assert mock_db.add.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_get_or_create_conversation_reuses_active_session():
    """An active (non-expired) conversation is reused rather than creating a new one."""
    from datetime import datetime, timedelta, timezone

    # last_message_at = 5 minutes ago (within 30-min window)
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    existing_conv = MagicMock()
    existing_conv.id = CONV_ID
    existing_conv.last_message_at = recent
    existing_conv.message_count = 3
    existing_conv.status = "active"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_conv
    mock_db.execute.return_value = mock_result

    from app.services.rag import get_or_create_conversation

    await get_or_create_conversation(
        mock_db,
        TENANT_ID,
        uuid.uuid4(),
        "telegram",
    )
    # db.add must NOT have been called — existing session reused
    mock_db.add.assert_not_called()
