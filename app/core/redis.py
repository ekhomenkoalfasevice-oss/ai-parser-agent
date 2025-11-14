"""Redis client helpers."""

from __future__ import annotations

import redis.asyncio as redis

from astro_bot.config import settings


def create_redis_client() -> redis.Redis:
    """Create lazy Redis client (connection established on first command)."""
    return redis.from_url(
        settings.redis_dsn,
        encoding="utf-8",
        decode_responses=True,
    )
