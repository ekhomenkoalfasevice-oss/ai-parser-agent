"""Configuration helpers for AstroForecast bot & API."""

from functools import cached_property
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseSettings, Field


_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings(BaseSettings):
    # Telegram / bot
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    webhook_base_url: AnyHttpUrl | None = Field(
        default=None,
        alias="WEBHOOK_BASE_URL",
        description="External https URL where Telegram will post updates",
    )
    webhook_path: str = Field(
        default="/telegram/webhook",
        alias="WEBHOOK_PATH",
    )
    webhook_secret_token: str = Field(
        default="local-secret-token",
        alias="WEBHOOK_SECRET_TOKEN",
    )

    # Infrastructure
    database_url: str = Field(
        default="postgresql+asyncpg://astro:astro@localhost:5432/astro_bot",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    redis_dsn: str = Field(default="redis://localhost:6379/0", alias="REDIS_DSN")
    default_timezone: str = Field(
        default="Europe/Moscow", alias="DEFAULT_TIMEZONE"
    )

    # Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @cached_property
    def normalised_webhook_path(self) -> str:
        """Ensure webhook path starts with a slash."""
        path = self.webhook_path or "/telegram/webhook"
        if not path.startswith("/"):
            path = f"/{path}"
        return path.rstrip("/") or "/telegram/webhook"

    @cached_property
    def webhook_full_url(self) -> str | None:
        """Full https URL for Telegram webhook, if base URL provided."""
        if not self.webhook_base_url:
            return None
        base = str(self.webhook_base_url).rstrip("/")
        return f"{base}{self.normalised_webhook_path}"

    @cached_property
    def logging_config(self) -> dict[str, Any]:
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "level": self.log_level.upper(),
                "handlers": ["console"],
            },
        }


settings = Settings()  # type: ignore[arg-type]