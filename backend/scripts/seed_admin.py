"""
Seed script: create the first AdminUser from environment variables.
Idempotent — skips if the email already exists.

Usage:
    python -m scripts.seed_admin
"""
import asyncio
import sys

from app.api.auth import hash_password
from app.config import settings
from app.db.mongo import close_db, connect_db, get_db
from app.models.admin_user import AdminRole, AdminUser


async def main() -> None:
    await connect_db()
    db = get_db()

    email = settings.seed_admin_email.lower()
    existing = await db.admin_users.find_one({"email": email})
    if existing:
        print(f"Admin user '{email}' already exists — skipping.")
        await close_db()
        return

    admin = AdminUser(
        email=email,
        hashed_password=hash_password(settings.seed_admin_password),
        role=AdminRole.super_admin,
    )
    result = await db.admin_users.insert_one(admin.to_doc())
    print(f"Created admin user '{email}' with id={result.inserted_id}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
