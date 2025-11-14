"""Telegram handlers for AstroForecast bot."""

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from .config import settings


router = Router(name="astro_bot")

WELCOME_TEXT = (
    "Привет! Я «АстроПрогноз на Сегодня» и готов делиться персональными подсказками "
    "по натальной карте. Введи дату рождения, чтобы получить краткий прогноз, а для "
    "полного доступа оформи подписку."
)

PRICE_TEXT = (
    f"Стоимость подписки: {settings.subscription_price_rub} ₽ в месяц. "
    "Команда /subscribe оформит оплату в пару кликов через Telegram Payments."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(f"{WELCOME_TEXT}\n\n{PRICE_TEXT}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Основные команды:\n"
        "/start — повторить приветствие\n"
        "/subscribe — оплата подписки\n"
        "/sos — экстренный вопрос (будет реализовано после подписки)\n"
        "/forecast — получить прогноз (в разработке)"
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    if not settings.payment_provider_token or settings.payment_provider_token == "REPLACE_ME":
        await message.answer(
            "Платёжный провайдер пока не настроен. "
            "Добавьте корректный токен в переменную окружения "
            "`PAYMENT_PROVIDER_TOKEN`, чтобы принимать оплату."
        )
        return

    prices = [
        LabeledPrice(
            label="Месячная подписка",
            amount=settings.subscription_price_kopeks,
        )
    ]

    await message.answer_invoice(
        title=settings.subscription_title,
        description=settings.subscription_description,
        payload="subscription_monthly",
        provider_token=settings.payment_provider_token,
        currency=settings.subscription_currency,
        prices=prices,
        need_name=True,
        send_email_to_provider=False,
        send_phone_number_to_provider=False,
        is_flexible=False,
    )


@router.pre_checkout_query()
async def process_pre_checkout(
    query: PreCheckoutQuery,
    bot: Bot,
) -> None:
    if query.invoice_payload != "subscription_monthly":
        await bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message="Неизвестный тип подписки. Попробуйте снова из /subscribe.",
        )
        return

    await bot.answer_pre_checkout_query(query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    await message.answer(
        "Спасибо! Оплата прошла успешно. "
        "В течение нескольких минут активируем доступ к полным прогнозам."
    )
