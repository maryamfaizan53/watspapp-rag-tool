from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import get_db
from app.models.bot_user import BotUser, Platform


async def get_or_create_bot_user(
    tenant_id: str,
    platform: Platform,
    platform_id: str,
) -> BotUser:
    """Upsert a BotUser and update last_seen_at. Returns the BotUser."""
    db = get_db()
    now = datetime.now(timezone.utc)

    result = await db.bot_users.find_one_and_update(
        {
            "tenant_id": ObjectId(tenant_id),
            "platform": platform.value,
            "platform_id": platform_id,
        },
        {"$set": {"last_seen_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True,
    )

    result["_id"] = str(result["_id"])
    result["tenant_id"] = str(result["tenant_id"])
    return BotUser(**result)
