"""
Integration tests: Telegram webhook (app/api/webhooks.py).

Runs against the real FastAPI app with the DB session overridden. Patches:
- app.api.webhooks.consume_message_quota  (mock DB can't do SELECT FOR UPDATE)
- app.services.rag._prefetch_stock_data   (text like "OGDC" would otherwise
  trigger real PSX network calls)
- LLM safe_generate / safe_generate_with_tools

Also covers the new security behaviour:
- the webhook secret is read from the X-Telegram-Bot-Api-Secret-Token HEADER
  (Telegram never sends it as a query param) and mismatches are rejected 403
- over-quota tenants get QUOTA_EXCEEDED_REPLY without touching the RAG pipeline
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.services.usage_service import QUOTA_EXCEEDED_REPLY

TENANT_ID = str(uuid.uuid4())
CHAT_ID = 5551234


def _make_tenant(secret_token: str | None = None):
    tenant = MagicMock()
    tenant.id = uuid.UUID(TENANT_ID)
    tenant.status = "active"
    channels = {"telegram": {"bot_token": "123456:plain-legacy-token"}}
    if secret_token:
        channels["telegram"]["webhook_secret_token"] = secret_token
    tenant.channels = channels
    tenant.usage = {}
    tenant.quota = {"messages_per_month": 1000}
    return tenant


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _wire_tenant(db, tenant):
    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)


@pytest.fixture()
def client(mock_db):
    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


def _tg_text_update(text: str) -> dict:
    return {
        "update_id": 10001,
        "message": {
            "message_id": 1,
            "from": {"id": CHAT_ID, "is_bot": False, "first_name": "Ali"},
            "chat": {"id": CHAT_ID, "type": "private"},
            "date": 1760000000,
            "text": text,
        },
    }


def _common_patches(answer="OGDC is trading at 132.50 PKR."):
    bot_user = MagicMock()
    bot_user.id = uuid.uuid4()
    conversation = MagicMock()
    conversation.id = uuid.uuid4()
    return (
        patch("app.api.webhooks.consume_message_quota", new_callable=AsyncMock, return_value=True),
        patch(
            "app.api.webhooks.bot_user_service.get_or_create_bot_user",
            new_callable=AsyncMock, return_value=bot_user,
        ),
        patch(
            "app.api.webhooks.rag.get_or_create_conversation",
            new_callable=AsyncMock, return_value=conversation,
        ),
        patch(
            "app.api.webhooks.rag.answer_query",
            new_callable=AsyncMock, return_value=(answer, []),
        ),
        patch("app.api.webhooks.rag.update_conversation", new_callable=AsyncMock),
    )


# ── Happy path ────────────────────────────────────────────────────────


def test_telegram_text_message_replies_via_webhook_response(client, mock_db):
    _wire_tenant(mock_db, _make_tenant())
    p1, p2, p3, p4, p5 = _common_patches()
    with p1, p2, p3, p4 as mock_answer, p5:
        resp = client.post(f"/webhooks/telegram/{TENANT_ID}", json=_tg_text_update("OGDC price?"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "sendMessage"
    assert body["chat_id"] == CHAT_ID
    assert "132.50" in body["text"]
    mock_answer.assert_awaited_once()


# ── Secret token (header, not query param) ────────────────────────────


def test_telegram_secret_token_checked_from_header(client, mock_db):
    _wire_tenant(mock_db, _make_tenant(secret_token="s3cret"))
    p1, p2, p3, p4, p5 = _common_patches()
    with p1, p2, p3, p4, p5:
        ok = client.post(
            f"/webhooks/telegram/{TENANT_ID}",
            json=_tg_text_update("hello"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
        )
    assert ok.status_code == 200


def test_telegram_secret_token_mismatch_rejected_403(client, mock_db):
    _wire_tenant(mock_db, _make_tenant(secret_token="s3cret"))
    resp = client.post(
        f"/webhooks/telegram/{TENANT_ID}",
        json=_tg_text_update("hello"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG"},
    )
    assert resp.status_code == 403


def test_telegram_secret_token_missing_header_rejected_403(client, mock_db):
    _wire_tenant(mock_db, _make_tenant(secret_token="s3cret"))
    resp = client.post(f"/webhooks/telegram/{TENANT_ID}", json=_tg_text_update("hello"))
    assert resp.status_code == 403


# ── Quota enforcement ─────────────────────────────────────────────────


def test_telegram_over_quota_replies_quota_message_without_rag(client, mock_db):
    _wire_tenant(mock_db, _make_tenant())
    with (
        patch("app.api.webhooks.consume_message_quota", new_callable=AsyncMock, return_value=False),
        patch("app.api.webhooks.rag.answer_query", new_callable=AsyncMock) as mock_answer,
    ):
        resp = client.post(f"/webhooks/telegram/{TENANT_ID}", json=_tg_text_update("OGDC price?"))

    assert resp.status_code == 200
    assert resp.json()["text"] == QUOTA_EXCEEDED_REPLY
    mock_answer.assert_not_awaited()  # over-quota must never burn LLM tokens


# ── Edge cases ────────────────────────────────────────────────────────


def test_telegram_inactive_tenant_returns_404(client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.post(f"/webhooks/telegram/{TENANT_ID}", json=_tg_text_update("hi"))
    assert resp.status_code == 404


def test_telegram_missing_bot_token_acks_silently(client, mock_db):
    tenant = _make_tenant()
    tenant.channels = {"telegram": {}}
    _wire_tenant(mock_db, tenant)
    resp = client.post(f"/webhooks/telegram/{TENANT_ID}", json=_tg_text_update("hi"))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
