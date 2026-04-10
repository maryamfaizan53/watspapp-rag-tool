"""
Seed script: create the first AdminUser from environment variables.
Idempotent — skips if the email already exists.

Usage:
    python -m scripts.seed_admin
"""
import asyncio
import sys

from sqlalchemy import select
from app.api.auth import hash_password
from app.config import settings
from app.db.postgres import connect_db, close_db, AsyncSessionLocal
from app.db.models import AdminUser


async def main() -> None:
    await connect_db()

    async with AsyncSessionLocal() as db:
        email = settings.seed_admin_email.lower()

        result = await db.execute(select(AdminUser).where(AdminUser.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin user '{email}' already exists — skipping.")
            await close_db()
            return

        admin = AdminUser(
            email=email,
            hashed_password=hash_password(settings.seed_admin_password),
            role="super_admin",
        )
        db.add(admin)
        await db.commit()
        print(f"Created admin user '{email}' with id={admin.id}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
