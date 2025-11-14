"""Entry point for running the AstroForecast bot."""

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from .config import settings
from .handlers import router as base_router


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(base_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
