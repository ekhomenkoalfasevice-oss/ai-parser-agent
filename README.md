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
3. Поднимите Postgres и Redis (например, через Docker):
   ```bash
   docker run -d --name astro-postgres -e POSTGRES_DB=astro_bot -e POSTGRES_USER=astro -e POSTGRES_PASSWORD=astro -p 5432:5432 postgres:16
   docker run -d --name astro-redis -p 6379:6379 redis:7
   ```
4. Запустите API + вебхук:
   ```bash
   uvicorn app.main:app --reload
   ```
   FastAPI поднимет `/health` и endpoint для вебхука (путь берётся из `WEBHOOK_PATH`, по умолчанию `/telegram/webhook`).

> Для локальной отладки без вебхука оставлен скрипт `python -m astro_bot.bot`, который запускает aiogram в режиме polling.

## Статус функционала
- `/start` запускает онбординг: бот спрашивает дату, время и город рождения, сохраняет профиль в Postgres и сразу выдаёт короткий прогноз (простой генератор на основе знака).
- `/forecast` повторно отдаёт короткий прогноз за текущий день (кэш в БД).
- `/full`, `/archive`, `/sos` пока заглушены — появятся после реализации детальных раскладов и архива.
- FastAPI и aiogram работают в одном процессе, Telegram обновления принимаются через вебхук, а состояния FSM и кеши подключены к Redis.

Архитектурное описание, промпты и план внедрения лежат в `docs/astro_bot_detailed_spec.md` и `docs/astro_bot_implementation_plan.md`.
