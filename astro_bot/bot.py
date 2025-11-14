"""Bot factories and optional local runner."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from .config import settings
from .handlers import router as base_router


def create_bot() -> Bot:
    """Instantiate aiogram Bot with shared settings."""
    return Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)


def create_dispatcher(storage: Optional[BaseStorage] = None) -> Dispatcher:
    """Instantiate Dispatcher and register base routers."""
    dp = Dispatcher(storage=storage or MemoryStorage())
    dp.include_router(base_router)
    return dp


async def main() -> None:
    """Convenience entrypoint for local polling runs."""
    bot = create_bot()
    dp = create_dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
