"""Unit tests for the RAG pipeline (app/services/rag.py)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TENANT_ID = uuid.uuid4()
CONV_ID = uuid.uuid4()
CHUNK_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()


def _chunk_db(chunk):
    mock_db = AsyncMock()

    async def mock_execute(query):
        result = MagicMock()
        if "document_chunks" in str(query):
            result.scalar_one_or_none.return_value = chunk
        elif "messages" in str(query):
            result.scalars.return_value.all.return_value = []
        return result

    mock_db.execute.side_effect = mock_execute
    return mock_db


@pytest.mark.asyncio
async def test_answer_query_empty_kb_uses_tools_path():
    """Empty FAISS → no context → tools path is used (web_search etc. can still answer)."""
    mock_db = _chunk_db(None)
    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=""),
        patch(
            "app.services.rag.llm.safe_generate_with_tools",
            new_callable=AsyncMock,
            return_value="To open a CDC account, choose a licensed broker...",
        ) as mock_tools,
    ):
        from app.services.rag import answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "How do I open an account?")
        assert "account" in answer
        assert chunk_ids == []
        # The prompt must explicitly say no relevant documents were found
        prompt_sent = mock_tools.call_args[0][0]
        assert "NO RELEVANT DOCUMENTS FOUND" in prompt_sent


@pytest.mark.asyncio
async def test_answer_query_filters_irrelevant_chunks_by_distance():
    """Chunks beyond rag_max_distance must be discarded (anti-hallucination)."""
    chunk = MagicMock()
    chunk.id = CHUNK_ID
    chunk.text = "OGDC P/E is 8.5"
    mock_db = _chunk_db(chunk)

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        # Distance 5.0 is far beyond any sane threshold
        patch("app.services.rag.faiss_store.search", return_value=[(f"{DOC_ID}_0", 5.0)]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=""),
        patch(
            "app.services.rag.llm.safe_generate_with_tools",
            new_callable=AsyncMock,
            return_value="I don't have that information in the knowledge base.",
        ) as mock_tools,
    ):
        from app.services.rag import answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "What colour is the sky?")
        assert chunk_ids == []  # irrelevant chunk was NOT used as context
        prompt_sent = mock_tools.call_args[0][0]
        assert "OGDC P/E is 8.5" not in prompt_sent


@pytest.mark.asyncio
async def test_answer_query_llm_unavailable_returns_fallback():
    """When the LLM is unavailable (returns None), the degraded fallback is used."""
    chunk = MagicMock()
    chunk.id = CHUNK_ID
    chunk.text = "Some KB content"
    mock_db = _chunk_db(chunk)

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(f"{DOC_ID}_0", 0.1)]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=""),
        patch("app.services.rag.llm.safe_generate_with_tools", new_callable=AsyncMock, return_value=None),
    ):
        from app.services.rag import FALLBACK_LLM_DOWN, answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "Tell me about the report")
        assert answer == FALLBACK_LLM_DOWN
        assert chunk_ids == []


@pytest.mark.asyncio
async def test_answer_query_returns_llm_response():
    """Happy path: relevant FAISS chunk → LLM answer → returned with chunk ids."""
    chunk = MagicMock()
    chunk.id = CHUNK_ID
    chunk.text = "OGDC P/E ratio is 7.3"
    mock_db = _chunk_db(chunk)

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[(f"{DOC_ID}_0", 0.05)]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=""),
        patch(
            "app.services.rag.llm.safe_generate_with_tools",
            new_callable=AsyncMock,
            return_value="OGDC P/E ratio is 7.3",
        ),
    ):
        from app.services.rag import answer_query

        answer, chunk_ids = await answer_query(mock_db, TENANT_ID, CONV_ID, "What is the P/E ratio?")
        assert "7.3" in answer
        assert chunk_ids == [str(CHUNK_ID)]


@pytest.mark.asyncio
async def test_answer_query_live_data_path_when_symbol_detected():
    """Known PSX symbol in query → pre-fetched live data path with safe_generate."""
    mock_db = _chunk_db(None)
    live_json = '{\n  "symbol": "OGDC",\n  "current_price_pkr": 311.42,\n  "source": "PSX Live"\n}'

    with (
        patch("app.services.rag.embeddings.embed_text", return_value=MagicMock()),
        patch("app.services.rag.faiss_store.search", return_value=[]),
        patch("app.services.rag._prefetch_stock_data", new_callable=AsyncMock, return_value=live_json),
        patch(
            "app.services.rag.llm.safe_generate",
            new_callable=AsyncMock,
            return_value="OGDC is trading at PKR 311.42.",
        ),
    ):
        from app.services.rag import answer_query

        answer, _ = await answer_query(mock_db, TENANT_ID, CONV_ID, "ogdc price?")
        assert "311.42" in answer


@pytest.mark.asyncio
async def test_format_price_direct_reports_unavailable():
    """Python-side formatter must say 'unavailable' for failed symbols, never a number."""
    from app.services.rag import _format_price_direct

    live = (
        '{"symbol": "OGDC", "current_price_pkr": 311.42, "source": "PSX Live"}'
        "\n---\n"
        '{"symbol": "LUCK", "status": "unavailable", "error": "..."}'
    )
    out = _format_price_direct(live)
    assert out is not None
    assert "311.42" in out
    assert "LUCK" in out and "unavailable" in out


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

    await get_or_create_conversation(mock_db, TENANT_ID, uuid.uuid4(), "telegram")
    mock_db.add.assert_not_called()
