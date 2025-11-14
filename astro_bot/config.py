"""Configuration helpers for AstroForecast bot."""

from functools import cached_property
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseSettings, Field, PositiveInt


_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    payment_provider_token: str | None = Field(
        default=None, alias="PAYMENT_PROVIDER_TOKEN"
    )
    subscription_price_rub: PositiveInt = Field(
        default=150, alias="SUBSCRIPTION_PRICE_RUB"
    )
    subscription_currency: Literal["RUB"] = Field(default="RUB")
    subscription_title: str = Field(
        default="Подписка «АстроПрогноз на Сегодня»"
    )
    subscription_description: str = Field(
        default=(
            "Детальные прогнозы на финансы, любовь и здоровье, архив и функция "
            "«Экстренный вопрос» на 30 дней."
        )
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @cached_property
    def subscription_price_kopeks(self) -> int:
        return self.subscription_price_rub * 100


settings = Settings()  # type: ignore[arg-type]
