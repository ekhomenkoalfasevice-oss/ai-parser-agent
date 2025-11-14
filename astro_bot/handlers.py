"""Telegram handlers for AstroForecast bot."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


router = Router(name="astro_bot")

WELCOME_TEXT = (
    "Привет! Я «АстроПрогноз на Сегодня». Введи дату рождения, чтобы получить первый "
    "короткий прогноз. Все функции — детали, архив и «Экстренный вопрос» — сейчас доступны бесплатно."
)

HELP_TEXT = (
    "Команды:\n"
    "/start — приветствие и ввод даты\n"
    "/forecast — короткий прогноз на сегодня (скоро)\n"
    "/full — полный расклад (скоро)\n"
    "/archive — архив прогнозов (скоро)\n"
    "/sos — экстренный вопрос (скоро)\n"
    "/help — справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("forecast"))
async def cmd_forecast_stub(message: Message) -> None:
    await message.answer(
        "Скоро здесь появится твой короткий прогноз. Мы как раз настраиваем движок вычислений 💫"
    )


@router.message(Command("full"))
async def cmd_full_stub(message: Message) -> None:
    await message.answer(
        "Полный расклад в разработке. После короткого прогноза появится кнопка «Раскрыть полностью»."
    )


@router.message(Command("archive"))
async def cmd_archive_stub(message: Message) -> None:
    await message.answer(
        "Архив прогнозов появится после запуска детальных раскладов. Следи за обновлениями!"
    )


@router.message(Command("sos"))
async def cmd_sos_stub(message: Message) -> None:
    await message.answer(
        "Функция «Экстренный вопрос» появится здесь — один вопрос в день с быстрым советом. Скоро!"
    )
