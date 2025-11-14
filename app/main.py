"""FastAPI application wired with aiogram webhook, Postgres and Redis."""

from __future__ import annotations

import logging.config
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update
import redis.asyncio as redis

from astro_bot.bot import create_bot, create_dispatcher
from astro_bot.config import settings
from app.api.routes import api_router
from app.core.redis import create_redis_client
from app.core.database import engine
from app.db import Base

logger = logging.getLogger("astro_bot.api")

bot: Bot | None = None
dispatcher: Dispatcher | None = None
redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks for FastAPI app."""
    global bot, dispatcher, redis_client

    logging.config.dictConfig(settings.logging_config)
    logger.info("Starting AstroForecast API (log level: %s)", settings.log_level)

    # Ensure tables exist (simple bootstrap until Alembic is configured)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis_client = create_redis_client()
    storage = RedisStorage(redis=redis_client)

    bot = create_bot()
    dispatcher = create_dispatcher(storage=storage)

    webhook_url = settings.webhook_full_url
    if webhook_url:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret_token,
            drop_pending_updates=True,
        )
        logger.info("Telegram webhook set to %s", webhook_url)
    else:
        logger.warning(
            "WEBHOOK_BASE_URL is not configured. Telegram webhook was not set."
        )

    try:
        yield
    finally:
        if bot:
            await bot.delete_webhook(drop_pending_updates=False)
            await bot.session.close()
            logger.info("Telegram webhook removed")
        if dispatcher:
            await dispatcher.storage.close()
            await dispatcher.storage.wait_closed()
        if redis_client:
            await redis_client.close()
            await redis_client.connection_pool.disconnect()
            logger.info("Redis client closed")


app = FastAPI(
    title="AstroForecast API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)

@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(settings.normalised_webhook_path)
async def telegram_webhook(request: Request) -> JSONResponse:
    """Receive Telegram updates and pass them to aiogram dispatcher."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.webhook_secret_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    payload: Any = await request.json()
    update = Update.model_validate(payload)

    if not bot or not dispatcher:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not ready",
        )

    await dispatcher.feed_update(bot, update)
    return JSONResponse({"ok": True})
