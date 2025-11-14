## API Contracts & Dialogue Prototypes

### 1. REST / RPC Endpoints
| Method & Path | Description | Request | Response |
| --- | --- | --- | --- |
| `POST /webhook/telegram` | Приём апдейтов | Telegram payload | `200 OK` |
| `POST /users` | Создать/обновить профиль. Вызывается ботом после ввода даты/времени. | `{telegram_id, name?, birth_date, birth_time?, location?}` | `{user_id, tz}` |
| `GET /users/{id}` | Получить профиль для команды `/profile`. | – | профиль |
| `POST /forecasts/short` | Сгенерировать короткий прогноз (с кешем по дате). | `{user_id}` | `{forecast_id, text, generated_at}` |
| `POST /forecasts/full` | Полный расклад, требует подписку. | `{user_id}` | `{forecast_id, sections: {finance, love, health, advice}}` |
| `GET /forecasts?user_id=&type=&date=` | Выдача из архива. | query | список |
| `POST /subscriptions/checkout` | Создание платежа (150 ₽/мес через Stars/Stripe). | `{user_id, plan}` | платежный токен/инвойс |
| `POST /payments/webhook` | Колбек провайдера → обновление статуса. | провайдер | `200` |
| `POST /emergency` | Экстренный вопрос. | `{user_id, question}` | `{answer, available_at_next}` |
| `POST /notifications/schedule` | Создать напоминания (не открыл прогноз, продление). | payload | расписание |
| `POST /admin/broadcast` | Публикация «Главного астрособытия». | `{text, channel, push}` | статус |

### 2. Internal Services Interfaces
#### Astrology Service
- `compute_natal(user_info)` → JSON (положение планет, дома, аспекты).
- `current_transits(timestamp, location)` → список транзитов (планета, аспект, орб, влияние).
- `highlight_transits(natal, transits)` → топ-3 аспекта с тэгами «финансы/любовь/здоровье/энергия».

#### LLM Orchestrator
- `render_short(context)` → текст ≤ 380 символов.
- `render_full(context_finance, context_love, context_health, advice_seed)` → Markdown/JSON.
- `render_emergency(question, astro_slice)` → 2 абзаца + дисклеймер.
- Поддерживает guardrails (OpenAI moderation, custom правила).

### 3. Data Models (Pydantic-style)
```python
class User(BaseModel):
    id: UUID
    telegram_id: int
    name: str | None
    birth_date: date
    birth_time: time | None
    location: str | None
    lat: float | None
    lon: float | None
    timezone: str
    language: str = "ru"
    created_at: datetime
    last_seen: datetime | None

class Forecast(BaseModel):
    id: UUID
    user_id: UUID
    kind: Literal["short", "full"]
    content: dict | str
    transit_snapshot: dict
    generated_at: datetime

class Subscription(BaseModel):
    id: UUID
    user_id: UUID
    plan: Literal["trial", "weekly", "monthly"]
    status: Literal["pending", "active", "expired", "canceled"]
    started_at: datetime
    expires_at: datetime
```

### 4. Conversation Flow (State Machine)
1. **Entry (`START`)**
   - Action: send intro → ask birth date.
   - Transition: `DATE_PROVIDED` if valid; `DATE_ERROR` otherwise.
2. **Birth Details**
   - Ask time/city.
   - If skipped → `DETAILS_CONFIRMED` with defaults.
3. **Short Forecast Delivery**
   - Fetch/generate forecast.
   - After sending → `OFFER_UPSELL`.
4. **Upsell**
   - Buttons: `Получить полный расклад`, `Остаться с коротким`.
   - If subscribe → `PAYMENT_FLOW`.
5. **Payment Flow**
   - Create invoice → wait for callback.
   - Success → `FULL_FORECAST`.
6. **Full Forecast**
   - Show sections, record in archive.
   - Offer: `Архив`, `Экстренный вопрос`, `Настройки`.
7. **Archive**
   - Pagination inline keyboards.
8. **Emergency Question**
   - Rate limit check; if denied → show timer.
   - Accept question → streaming response.
9. **Notifications**
   - If user inactive by noon → reminder message state.

Transitions реализованы через FSM aiogram (`StatesGroup`) + Redis storage.

### 5. Dialogue Prototypes (Расширенные)
```
/start
Бот: Привет! Введи дату рождения (дд.мм.гггг).
Юзер: 27.04.1995
Бот: А знаешь время и город? Напиши «чч:мм, город» или «Пропустить».
Юзер: 08:30, Санкт-Петербург
Бот: Сохраняю… секунду!
Бот: Сегодня Луна в Тельце усиливает твою уверенность. Действуй мягко, но настойчиво. Речь о переговорах — энергия в твою пользу.
Бот: Хочешь детальный расклад про финансы, любовь и здоровье + рекомендации? Дам 2 дня бесплатно.
Кнопки: [Получить полный расклад] [Позже]
```

```
После подписки
Бот: ✅ Подписка активна до 20 ноября.
Бот: 
Финансы — Юпитер расширяет твой денежный сектор: шанс на премию или щедрый заказчик. Договорись о деталях до вечера.
Любовь — Венера и Меркурий в гармонии: говори о чувствах, тебя поймут.
Здоровье — Слушай тело, дай отдых глазам.
Рекомендация дня — медитируй 7 минут на чувство благодарности.
Кнопки: [Архив] [Экстренный вопрос] [Настройки]
```

```
Команда /sos
Бот: Что тебя волнует? 1 вопрос → 1 ответ.
Юзер: Стоит ли соглашаться на ночную смену?
Бот: Сейчас Марс напрягает твою зону ресурсов, поэтому не расширяй нагрузку без нужды. Если это ради денег — договорись об ограниченном сроке, иначе рискуешь перегореть. Спроси себя, даст ли это свободное утро. Ответь «Ещё вопрос» завтра.
```

### 6. Error & Edge Cases
- Неверная дата → подсказка формата + ограничение (1900–2020).
- Нет времени/города → подставляем 12:00 и UTC+3 (Россия) с дисклеймером.
- LLM timeout → fallback шаблон (rule-based).
- Платёж не завершён → напоминание через 10 минут.
- Пользователь заблокировал бота → флаг `is_blocked`, отключение пушей.

### 7. Telemetry Events
- `user_registered`, `profile_completed`, `short_forecast_viewed`, `upsell_shown`, `subscription_started`, `full_forecast_viewed`, `emergency_question_asked`, `reminder_sent`, `reminder_opened`.

### 8. Next Steps
1. Реализовать Pydantic-схемы и ORM-модели.
2. Настроить FSM и webhook обработчики.
3. Интегрировать Swiss Ephemeris и протестировать расчёты.
4. Подготовить промпты и golden set для QA.
