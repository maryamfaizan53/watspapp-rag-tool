from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotUser
from app.schemas.bot_user import Platform


async def get_or_create_bot_user(
    db: AsyncSession,
    tenant_id: str | UUID,
    platform: Platform,
    platform_id: str,
) -> BotUser:
    """Upsert a BotUser and update last_seen_at. Returns the BotUser."""
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    now = datetime.now(timezone.utc)

    # 1. Try to find existing
    query = select(BotUser).where(
        BotUser.tenant_id == tid,
        BotUser.platform == platform.value,
        BotUser.platform_id == platform_id,
    )
    result = await db.execute(query)
    bot_user = result.scalar_one_or_none()

    if bot_user:
        # Update last_seen_at
        bot_user.last_seen_at = now
    else:
        # Create new
        bot_user = BotUser(
            tenant_id=tid,
            platform=platform.value,
            platform_id=platform_id,
            created_at=now,
            last_seen_at=now,
        )
        db.add(bot_user)

    await db.commit()
    await db.refresh(bot_user)
    return bot_user
