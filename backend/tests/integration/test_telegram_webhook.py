"""
Integration test: POST /webhooks/telegram/{tenant_id} → RAG pipeline → Telegram reply.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

TENANT_ID = str(ObjectId())
BOT_USER_OID = ObjectId()
CONV_OID = ObjectId()


def _make_mock_db():
    db = MagicMock()
    db.tenants.find_one = AsyncMock(
        return_value={
            "_id": TENANT_ID,
            "name": "Test Tenant",
            "status": "active",
            "channels": {"telegram": {"bot_token": "test-bot-token", "configured": True}},
            "quota": {"rate_limit_per_minute": 60},
        }
    )
    db.bot_users.find_one_and_update = AsyncMock(
        return_value={
            "_id": BOT_USER_OID,
            "tenant_id": ObjectId(TENANT_ID),
            "platform": "telegram",
            "platform_id": "12345",
        }
    )
    db.conversations.find_one = AsyncMock(return_value=None)
    db.conversations.insert_one = AsyncMock(return_value=MagicMock(inserted_id=CONV_OID))
    db.messages.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    db.messages.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[]
    )
    db.conversations.update_one = AsyncMock()
    db.tenants.update_one = AsyncMock()
    db.document_chunks.find.return_value.to_list = AsyncMock(
        return_value=[{"_id": ObjectId(), "text": "OGDC P/E is 7.3"}]
    )
    return db


TELEGRAM_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "chat": {"id": 12345, "type": "private"},
        "text": "What is OGDC P/E ratio?",
        "from": {"id": 12345, "is_bot": False, "first_name": "Investor"},
    },
}


def _make_patches(mock_db):
    import numpy as np

    chunk_id = str(ObjectId())
    return [
        patch("app.db.mongo.get_db", return_value=mock_db),
        patch("app.api.webhooks.get_db", return_value=mock_db),
        patch("app.services.rag.get_db", return_value=mock_db),
        patch("app.services.bot_user_service.get_db", return_value=mock_db),
        patch("app.db.redis.get_redis", return_value=AsyncMock()),
        patch("app.services.embeddings.embed_text", return_value=np.zeros(384, dtype="float32")),
        patch("app.db.faiss_store.search", return_value=[(chunk_id, 0.05)]),
        patch(
            "app.services.llm.safe_generate",
            new_callable=AsyncMock,
            return_value="OGDC P/E ratio is approximately 7.3.",
        ),
        patch("app.providers.telegram.send_text_reply", new_callable=AsyncMock),
        patch("app.main.connect_db", new_callable=AsyncMock),
        patch("app.main.connect_redis", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.start_worker"),
        patch("app.main.stop_worker"),
    ]


@pytest.mark.asyncio
async def test_telegram_webhook_returns_ok_and_sends_reply():
    """
    POST /webhooks/telegram/{tenant_id} returns 200 {"ok": true}
    and the background handler sends a Telegram reply.
    """
    mock_db = _make_mock_db()
    patches = _make_patches(mock_db)

    # Enter all patches
    mocks = [p.__enter__() for p in patches]
    try:
        mock_send = mocks[8]  # app.providers.telegram.send_text_reply

        from app.main import create_app

        test_app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                f"/webhooks/telegram/{TENANT_ID}",
                json=TELEGRAM_UPDATE,
            )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        # Background tasks run during request in test client
        mock_send.assert_called_once()
        _bot_token, _chat_id, reply_text = mock_send.call_args[0]
        assert "7.3" in reply_text
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_telegram_webhook_404_for_unknown_tenant():
    """Webhook for an unknown tenant returns 404."""
    mock_db = MagicMock()
    mock_db.tenants.find_one = AsyncMock(return_value=None)

    with (
        patch("app.api.webhooks.get_db", return_value=mock_db),
        patch("app.main.connect_db", new_callable=AsyncMock),
        patch("app.main.connect_redis", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.db.redis.get_redis", return_value=AsyncMock()),
        patch("app.main.start_worker"),
        patch("app.main.stop_worker"),
    ):
        from app.main import create_app

        test_app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                f"/webhooks/telegram/{ObjectId()}",
                json=TELEGRAM_UPDATE,
            )

    assert response.status_code == 404
