"""User service helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_by_telegram(
    session: AsyncSession, telegram_id: int
) -> User | None:
    """Return user if exists."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_or_update_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    username: Optional[str] = None,
    language: Optional[str] = None,
    birth_date=None,
    birth_time=None,
    birth_city: Optional[str] = None,
    timezone: Optional[str] = None,
) -> User:
    """Create or update user profile."""
    user = await get_user_by_telegram(session, telegram_id)
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)

    user.first_name = first_name or user.first_name
    user.last_name = last_name or user.last_name
    user.username = username or user.username
    if language:
        user.language = language

    user.birth_date = birth_date or user.birth_date
    user.birth_time = birth_time or user.birth_time
    user.birth_city = birth_city or user.birth_city
    if timezone:
        user.timezone = timezone

    user.last_seen_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)
    return user


async def touch_last_seen(session: AsyncSession, user: User) -> None:
    """Update last seen timestamp."""
    user.last_seen_at = datetime.utcnow()
    await session.commit()
