# AstroForecast Bot

Бекенд и Telegram-бот проекта «АстроПрогноз на Сегодня». Первая версия полностью бесплатная: бот подключён к FastAPI, Postgres и Redis, обновления принимаются через вебхук Telegram.

## Быстрый старт
1. Создайте виртуальное окружение и установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Создайте `.env` по примеру ниже:
   ```dotenv
   TELEGRAM_BOT_TOKEN=123:abc
   WEBHOOK_BASE_URL=https://example.com
   WEBHOOK_SECRET_TOKEN=super-secret
   DATABASE_URL=postgresql+asyncpg://astro:astro@localhost:5432/astro_bot
   REDIS_DSN=redis://localhost:6379/0
   ```
3. Запустите API + вебхук:
   ```bash
   uvicorn app.main:app --reload
   ```
   FastAPI поднимет `/health` и endpoint для вебхука (путь берётся из `WEBHOOK_PATH`, по умолчанию `/telegram/webhook`).

> Для локальной отладки без вебхука оставлен скрипт `python -m astro_bot.bot`, который запускает aiogram в режиме polling.

## Статус функционала
- `/start`, `/help` и заглушки команд `/forecast`, `/full`, `/archive`, `/sos`.
- FastAPI и aiogram работают в одном процессе, хранение состояний и кешей планируется в Redis (подключение уже настроено).
- База данных и сервисы генерации прогнозов будут добавлены на следующих шагах (см. `docs/`).

Архитектурное описание, промпты и план внедрения лежат в `docs/astro_bot_detailed_spec.md` и `docs/astro_bot_implementation_plan.md`.
