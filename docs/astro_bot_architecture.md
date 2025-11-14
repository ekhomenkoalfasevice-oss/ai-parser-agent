## AstroForecast Bot – Architecture Blueprint

### 1. Vision & Scope
- **Goal**: персонализированный ежедневный астропрогноз с монетизацией через подписку (детальный расклад, архив, «Экстренный вопрос», ежедневная рассылка события дня).
- **Channels**: Telegram-бот (MVP), Telegram-канал, опционально web-виджет (embed) поверх того же API.
- **Нефункциональные цели**: ответ <5 c на короткий прогноз, 99% успешных рассылок, аудит логов и управление подписками.
- **Монетизация**: месячная подписка 150 ₽ (триал 2 дня), оплаты через Telegram Payments / Stripe / ЮKassa.

### 2. Высокоуровневая архитектура
```
Telegram Client ─┐
                 │ 1. webhook/update
Telegram Bot API ─► Bot Gateway (FastAPI) ─► Command Router ─┐
                                                            │
                                      ┌─► Astrology Service ─┤
                                      │                      │
                                      ├─► LLM Orchestrator ──┤
                                      │                      │
                                      ├─► Subscription/Payments Service
                                      │                      │
                                      └─► Notifications & Scheduler

Shared services: PostgreSQL, Redis cache, Object storage (архив текстов), Observability stack.
```

### 3. Основные сервисы и модули
| Модуль | Ответственность | Технологии |
| --- | --- | --- |
| Bot Gateway | Webhook + стейт команд, анти-спам, локализация | FastAPI, aiogram |
| Profile Service | Пользовательские данные (дата/место/время рождения, timezone, настройки) | PostgreSQL |
| Astrology Service | Расчёт транзитов, аспектов, хранение натальной карты | Swiss Ephemeris (pyswisseph), astroquery |
| LLM Orchestrator | Сбор контекста, шаблоны, контроль длины, кэширование ответов | LangChain / custom prompts, OpenAI GPT-4.1 |
| Subscription & Billing | Планы, платежные статусы, интеграция Telegram Stars/Stripe | python-telegram-bot Payments / external API |
| Forecast Engine | Планировщик генерации дневных прогнозов, сохранение в архив | Celery worker, Redis broker |
| Emergency Q&A | Rate limit, хранение истории, быстрая генерация mini-ответа | FastAPI endpoint + LLM |
| Notifications | Cron-like worker, пуши (не прочитал прогноз, окончание подписки) | APScheduler / Celery beat |
| Analytics/Admin | Метрики, manual push, экспорт | Metabase/Grafana |

### 4. Data Flow Scenarios
1. **Регистрация / базовый прогноз**
   1. Пользователь вводит дату/время/город → Bot Gateway.
   2. Profile Service валидирует, вычисляет timezone, сохраняет профиль.
   3. Astrology Service строит натал (при первом запросе) и текущие транзиты.
   4. Forecast Engine формирует короткий контекст → LLM Orchestrator → ответ.
   5. Bot отправляет 2–3 предложения + CTA подписки.

2. **Детальный расклад (подписчик)**
   1. Проверка ACL (active subscription) → Forecast Engine.
   2. Сбор данных: финансовый, любовный, здоровье контексты (предопределённые «шаблонные» правила + транзиты).
   3. LLM prompt с четырьмя секциями + рекомендация дня.
   4. Сохранение в `forecast_archive` с подписью пользователя.

3. **Экстренный вопрос**
   1. Проверка лимита (1/24h).  
   2. Сбор быстрого среза транзитов (3–5 ключевых аспектов) + текст вопроса.  
   3. LLM prompt «counselor» с safety-правилами.  
   4. Логирование и ответ.

4. **Рассылка «Главное событие дня»**
   1. Ночной джоб вычисляет ключевой транзит (алгоритм выбора: интенсивность аспекта).  
   2. LLM генерирует текст 250–300 символов.  
   3. Публикация в канал + опциональный push подписчикам.

### 5. Схема данных (PostgreSQL)
- `users`: `id`, `telegram_id`, `name`, `birth_date`, `birth_time`, `birth_city`, `lat`, `lon`, `tz`, `language`, `created_at`, `last_seen`.
- `natal_charts`: `user_id`, `chart_json`, `computed_at`.
- `subscriptions`: `id`, `user_id`, `plan`, `status`, `started_at`, `expires_at`, `payment_provider`, `provider_payload`.
- `forecasts`: `id`, `user_id`, `type` (short/full), `content`, `transit_snapshot`, `created_at`, `feedback` (enum: none/accurate/off).
- `emergency_questions`: `id`, `user_id`, `question`, `answer`, `status`, `asked_at`.
- `notifications`: `id`, `user_id`, `type`, `payload`, `scheduled_at`, `status`.

### 6. Conversation & Command Handling
- `/start`: приветствие → запрос даты рождения → опционально время/город → сохранение → короткий прогноз.
- `/profile`: показать текущие данные, кнопка изменить.
- `/forecast`: если уже был сегодня — показать сохранённый, иначе сгенерировать.
- `/full`: доступно при подписке, триал → триггер оплаты.
- `/archive`: inline keyboard с датами (7 последних → pagination).
- `/sos`: экстренный вопрос (rate-limit + вход в мини-чат).
- `/help`: подсказки, ссылка на канал.

### 7. Prompt Engineering (LLM)
- **Short Forecast Prompt**: вход — солнечный знак, ключевые транзиты, «энергетический тон». Выход: 2–3 предложения, ≤380 символов, позитивный call-to-action.
- **Full Forecast Prompt**: структура JSON → парсер перед отправкой юзеру форматирует Markdown блоки.
- **Emergency Prompt**: строгий safety (не медицинские диагнозы, не финсоветы без дисклеймера). Ответ ≤120 слов.
- Кэширование: если пользователь уже запросил короткий прогноз сегодня, повторно выдаётся сохранённая версия без LLM вызова.

### 8. Интеграции & внешние зависимости
- Swiss Ephemeris / NASA JPL: подготовить контейнер с эфемеридами.
- Telegram Payments (Stars) + резерв Stripe/ЮKassa для вне-TG платежей.
- Email/SMS (опционально) для напоминаний — через SendGrid/Msg91.

### 9. Безопасность и соответствие
- Очистка PII по запросу (`/delete_me`).
- Rate limiting на уровне Bot Gateway + Redis.
- Audit лог (кто и когда генерировал прогноз, ID LLM вызова).
- Secrets управлять через `.env` + Vault/Parameter Store.

### 10. Roadmap (итерации)
1. **MVP (2–3 недели)**: регистрация, базовый прогноз, оплата, детальный расклад, архив, рассылка без канала.  
2. **Iter 2**: Экстренный вопрос, оценка «сбылось», напоминания, аналитика.  
3. **Iter 3**: Веб-виджет, многоязычность, рекомендательная лента (советы/ритуалы).

### 11. Тестирование
- Юнит-тесты для расчёта транзитов и форматирования ответов.
- Контрольные промпты (golden set) для LLM regression.
- Интеграционные тесты webhook → прогноз.
- Нагрузочные для рассылок (100k пользователей, 5 минут).

### 12. Мониторинг
- Prometheus metrics: время ответа, ошибки LLM, очередь Celery.
- Sentry: исключения в бэкенде.
- ClickHouse/Redshift: события продукта (MAU, конверсии в подписку, удержание).

### 13. DevOps
- Docker + docker-compose для локальной разработки.
- CI/CD (GitHub Actions): lint, tests, deploy to staging, manual approval to prod.
- IaC (Terraform) для облачной инфраструктуры.

Документ служит стартовой точкой; следующие шаги — детализация API и моделирование диалогов (см. отдельные артефакты).
