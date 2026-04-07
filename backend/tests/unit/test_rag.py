"""Unit tests for the RAG pipeline (app/services/rag.py)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

TENANT_ID = str(ObjectId())
CONV_ID = str(ObjectId())
CHUNK_ID = str(ObjectId())


@pytest.mark.asyncio
async def test_answer_query_empty_kb_returns_fallback():
    """When FAISS returns no results, the fallback 'no data' message is returned."""
    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[]),
    ):
        from app.services.rag import FALLBACK_NO_DATA, answer_query

        answer, chunk_ids = await answer_query(TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert answer == FALLBACK_NO_DATA
        assert chunk_ids == []


@pytest.mark.asyncio
async def test_answer_query_llm_unavailable_returns_fallback():
    """When the LLM is unavailable (safe_generate returns None), the degraded fallback is used."""
    mock_db = MagicMock()
    mock_db.document_chunks.find.return_value.to_list = AsyncMock(
        return_value=[{"_id": ObjectId(CHUNK_ID), "text": "OGDC P/E is 8.5"}]
    )
    mock_db.messages.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(CHUNK_ID, 0.1)]),
        patch("app.services.rag.get_db", return_value=mock_db),
        patch("app.services.rag.llm.safe_generate", new_callable=AsyncMock, return_value=None),
    ):
        from app.services.rag import FALLBACK_LLM_DOWN, answer_query

        answer, chunk_ids = await answer_query(TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert answer == FALLBACK_LLM_DOWN
        assert chunk_ids == []


@pytest.mark.asyncio
async def test_answer_query_returns_llm_response():
    """Happy path: FAISS finds chunks → LLM returns answer → returned to caller."""
    mock_db = MagicMock()
    mock_db.document_chunks.find.return_value.to_list = AsyncMock(
        return_value=[{"_id": ObjectId(CHUNK_ID), "text": "OGDC P/E ratio is 7.3"}]
    )
    mock_db.messages.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(CHUNK_ID, 0.05)]),
        patch("app.services.rag.get_db", return_value=mock_db),
        patch(
            "app.services.rag.llm.safe_generate",
            new_callable=AsyncMock,
            return_value="OGDC P/E ratio is 7.3",
        ),
    ):
        from app.services.rag import answer_query

        answer, chunk_ids = await answer_query(TENANT_ID, CONV_ID, "What is OGDC P/E?")
        assert "7.3" in answer
        assert chunk_ids == [CHUNK_ID]


@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_new_when_no_existing():
    """A new Conversation is created when none exists in the DB."""
    user_id = str(ObjectId())
    mock_db = MagicMock()
    mock_db.conversations.find_one = AsyncMock(return_value=None)
    mock_db.conversations.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=ObjectId())
    )

    with patch("app.services.rag.get_db", return_value=mock_db):
        from app.services.rag import get_or_create_conversation

        await get_or_create_conversation(TENANT_ID, user_id, "telegram")
        assert mock_db.conversations.insert_one.called


@pytest.mark.asyncio
async def test_get_or_create_conversation_reuses_active_session():
    """An active (non-expired) conversation is reused rather than creating a new one."""
    from datetime import datetime, timedelta, timezone

    # last_message_at = 5 minutes ago (within 30-min window)
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    tenant_oid = ObjectId()
    user_oid = ObjectId()
    existing_doc = {
        "_id": ObjectId(),
        "tenant_id": tenant_oid,
        "bot_user_id": user_oid,
        "platform": "telegram",
        "started_at": recent,
        "last_message_at": recent,
        "message_count": 3,
        "status": "active",
    }

    mock_db = MagicMock()
    mock_db.conversations.find_one = AsyncMock(return_value=existing_doc)

    with patch("app.services.rag.get_db", return_value=mock_db):
        from app.services.rag import get_or_create_conversation

        await get_or_create_conversation(
            str(tenant_oid),
            str(user_oid),
            "telegram",
        )
        # insert_one must NOT have been called — existing session reused
        mock_db.conversations.insert_one.assert_not_called()
