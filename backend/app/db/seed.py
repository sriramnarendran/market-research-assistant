"""Idempotent dev seed: demo users + dev bypass user.

Usage:
    uv run python -m app.db.seed
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_session_factory

DEMO_USER_EMAIL = "demo-user@example.com"
DEMO_USER_PASSWORD = "demo-user-pass"
DEMO_ADMIN_EMAIL = "demo-admin@example.com"
DEMO_ADMIN_PASSWORD = "demo-admin-pass"
DEV_EMAIL = "dev@local"
DEV_PASSWORD = "dev-pass"


async def _upsert_user(
    session,
    *,
    user_id: uuid.UUID | None,
    email: str,
    password: str,
    role: str,
) -> None:
    existing = await session.execute(select(User).where(User.email == email))
    user = existing.scalar_one_or_none()
    pw_hash = hash_password(password)
    if user is None:
        kwargs: dict = {
            "email": email,
            "password_hash": pw_hash,
            "role": role,
        }
        if user_id is not None:
            kwargs["id"] = user_id
        session.add(User(**kwargs))
        print(f"[seed] created {email} ({role})")
    else:
        user.password_hash = pw_hash
        user.role = role
        print(f"[seed] updated {email} ({role})")


async def seed() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _upsert_user(
            session,
            user_id=settings.DEV_USER_ID,
            email=DEV_EMAIL,
            password=DEV_PASSWORD,
            role="user",
        )
        await _upsert_user(
            session,
            user_id=None,
            email=DEMO_USER_EMAIL,
            password=DEMO_USER_PASSWORD,
            role="user",
        )
        await _upsert_user(
            session,
            user_id=None,
            email=DEMO_ADMIN_EMAIL,
            password=DEMO_ADMIN_PASSWORD,
            role="admin",
        )
        await session.commit()

    print("\n[seed] Demo credentials:")
    print(f"  User:  {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")
    print(f"  Admin: {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
    print(f"  Dev (AUTH_DEV_BYPASS): {DEV_EMAIL} / {DEV_PASSWORD} (id={settings.DEV_USER_ID})")


if __name__ == "__main__":
    asyncio.run(seed())
