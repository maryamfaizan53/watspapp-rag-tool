from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client.get_default_database()
    await _create_indexes()


async def close_db() -> None:
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db


async def _create_indexes() -> None:
    db = get_db()

    # tenants
    await db.tenants.create_index("name", unique=True)
    await db.tenants.create_index("status")
    await db.tenants.create_index(
        "channels.telegram.bot_token", unique=True, sparse=True
    )
    await db.tenants.create_index(
        "channels.whatsapp.from_number", unique=True, sparse=True
    )

    # admin_users
    await db.admin_users.create_index("email", unique=True)

    # bot_users — unique identity per platform per tenant
    await db.bot_users.create_index(
        [("tenant_id", 1), ("platform", 1), ("platform_id", 1)], unique=True
    )

    # conversations — find active session + TTL expiry
    await db.conversations.create_index(
        [("tenant_id", 1), ("bot_user_id", 1), ("last_message_at", -1)]
    )
    await db.conversations.create_index(
        "last_message_at", expireAfterSeconds=1800  # 30-min inactivity TTL
    )

    # messages — paginated retrieval + tenant analytics
    await db.messages.create_index([("conversation_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("tenant_id", 1), ("timestamp", -1)])

    # documents — list by tenant+status + deduplication
    await db.documents.create_index([("tenant_id", 1), ("status", 1)])
    await db.documents.create_index(
        [("tenant_id", 1), ("content_hash", 1)], unique=True
    )

    # document_chunks — ordered retrieval + bulk delete by tenant
    await db.document_chunks.create_index([("document_id", 1), ("chunk_index", 1)])
    await db.document_chunks.create_index("tenant_id")

    # usage_snapshots — one per tenant per day
    await db.usage_snapshots.create_index(
        [("tenant_id", 1), ("date", -1)], unique=True
    )
