"""Telegram handlers for AstroForecast bot."""

from __future__ import annotations

import logging
from datetime import datetime, time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from astro_bot.config import settings
from astro_bot.states import Onboarding
from app.core.database import async_session_maker
from app.services import (
    create_or_update_user,
    get_or_create_short_forecast,
    get_user_by_telegram,
)

router = Router(name="astro_bot")
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Привет! Я «АстроПрогноз на Сегодня». Введи дату рождения (дд.мм.гггг), чтобы получить первый "
    "короткий прогноз. Все функции — детали, архив и «Экстренный вопрос» — сейчас доступны бесплатно."
)

HELP_TEXT = (
    "Команды:\n"
    "/start — приветствие и ввод даты\n"
    "/forecast — короткий прогноз на сегодня\n"
    "/full — полный расклад (в разработке)\n"
    "/archive — архив (скоро)\n"
    "/sos — экстренный вопрос (скоро)\n"
    "/help — справка"
)

DETAILS_PROMPT = (
    "Супер! Теперь введи время и город рождения в формате «чч:мм, Город». "
    "Если не знаешь — напиши «Пропустить»."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_maker() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if user and user.birth_date:
            await message.answer(
                "Ты уже в системе. Секунду, обновляю короткий прогноз…"
            )
            forecast = await get_or_create_short_forecast(session, user)
            await message.answer(forecast.content)
            return

    await message.answer(WELCOME_TEXT)
    await state.set_state(Onboarding.waiting_birth_date)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("forecast"))
async def cmd_forecast(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        user = await get_user_by_telegram(session, message.from_user.id)
        if not user or not user.birth_date:
            await message.answer(
                "Давай сначала настроим профиль. Введи дату рождения (дд.мм.гггг)."
            )
            await state.set_state(Onboarding.waiting_birth_date)
            return
        forecast = await get_or_create_short_forecast(session, user)
        await message.answer(forecast.content)


@router.message(Onboarding.waiting_birth_date)
async def handle_birth_date(message: Message, state: FSMContext) -> None:
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        await message.answer("Неверный формат. Напиши дату как 12.07.1993")
        return

    await state.update_data(birth_date=parsed.isoformat())
    await message.answer(DETAILS_PROMPT)
    await state.set_state(Onboarding.waiting_details)


def _parse_details(text: str) -> tuple[time | None, str | None]:
    normalized = text.strip()
    if not normalized or normalized.lower() in {"пропустить", "skip"}:
        return None, None

    birth_time: time | None = None
    birth_city: str | None = None

    if "," in normalized:
        time_part, city_part = normalized.split(",", 1)
        time_part = time_part.strip()
        city_part = city_part.strip()
        if time_part:
            try:
                birth_time = datetime.strptime(time_part, "%H:%M").time()
            except ValueError:
                pass
        birth_city = city_part.title() if city_part else None
    else:
        # Either only time or only city; try time first.
        try:
            birth_time = datetime.strptime(normalized, "%H:%M").time()
        except ValueError:
            birth_city = normalized.title()

    return birth_time, birth_city


@router.message(Onboarding.waiting_details)
async def handle_details(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    birth_date_str = data.get("birth_date")
    if not birth_date_str:
        await message.answer("Что-то пошло не так. Напиши /start, чтобы начать заново.")
        await state.clear()
        return

    birth_time, birth_city = _parse_details(message.text or "")
    try:
        birth_date = datetime.fromisoformat(birth_date_str).date()
    except ValueError:
        await message.answer("Не удалось прочитать дату. Напиши /start ещё раз.")
        await state.clear()
        return

    async with async_session_maker() as session:
        user = await create_or_update_user(
            session,
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language=message.from_user.language_code or "ru",
            birth_date=birth_date,
            birth_time=birth_time,
            birth_city=birth_city,
            timezone=settings.default_timezone,
        )
        await state.clear()
        await message.answer("Профиль сохранён! Считаю твой короткий прогноз…")
        forecast = await get_or_create_short_forecast(session, user)
        await message.answer(forecast.content)


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
