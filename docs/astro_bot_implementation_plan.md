## AstroForecast Bot — Implementation Schematics

### 0. Guiding Principles
- **Single codebase**: FastAPI backend + aiogram bot live in one repo; services split by modules, not repos.
- **Stateless bot layer**: all state (FSM, rate limits, cache) lives in Redis/PostgreSQL so multiple workers can scale.
- **First release fully free**: all access checks reference `access_flags`, no payment logic in runtime path (kept behind feature flags for later).

---

### 1. Component Layers & Responsibilities
```
┌──────────────────────────────────────────────────────────────────────────┐
│ Telegram API                                                             │
└───────────────▲──────────────────────────────────────────────────────────┘
                │ updates/webhook
┌───────────────┴──────────────┐
│ Bot Gateway (aiogram + FastAPI webhook)                                 │
│ - FSM & input validation                                               │
│ - Command & callback routers (`/start`, `/archive`, `/sos`)             │
│ - Rich reply keyboards                                                  │
└───────────────┬──────────────┘
                │ REST/RPC calls
┌───────────────┴──────────────────────────────────────────────────────────┐
│ Core API (FastAPI)                                                      │
│ - Users/Profile CRUD                                                    │
│ - Forecast facade (delegates to services)                               │
│ - Access flags + telemetry                                              │
│ - Admin endpoints                                                       │
└─────┬───────────┬────────────┬────────────┬────────────┬────────────────┘
      │           │            │            │            │
┌─────▼───┐ ┌─────▼────┐ ┌─────▼────────┐ ┌─▼───────────┐ ┌─────▼────────┐
│Astrology│ │LLM Orches│ │Forecast Engine│ │Emergency Q&A│ │Notification  │
│Service  │ │trator    │ │(Celery)       │ │Service      │ │Scheduler     │
│pyswisseph│ │prompts   │ │daily jobs     │ │mini-chat    │ │APScheduler   │
└─────┬───┘ └─────┬────┘ └─────┬────────┘ └─┬───────────┘ └─────┬────────┘
      │           │            │              │                  │
      ▼           ▼            ▼              ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL (users, charts, forecasts, access_flags, events, sos, logs)   │
│ Redis (FSM state, rate limits, cache of forecasts, Celery broker)        │
└──────────────────────────────────────────────────────────────────────────┘
```

Key modules (Python packages):
- `astro_bot/` — bot entry & routers (already present).
- `app/api/` — FastAPI routers (`users`, `forecasts`, `access`, `archive`, `admin`).
- `app/services/astrology.py` — wrappers over Swiss Ephemeris, caching layer.
- `app/services/llm.py` — prompt builders, OpenAI client, guardrails.
- `app/services/forecasts.py` — orchestrates data fetch, caching, persistence.
- `app/services/emergency.py` — rate limit checks, streaming to bot.
- `app/scheduler/` — Celery tasks + APScheduler kickoff (daily forecast generation, reminders, broadcast).
- `app/db/` — SQLAlchemy models, migrations (Alembic).

---

### 2. Database Schema (PostgreSQL 15)

| Table | Columns | Notes |
| --- | --- | --- |
| `users` | `id UUID PK`, `telegram_id BIGINT UNIQUE`, `name TEXT`, `birth_date DATE`, `birth_time TIME NULL`, `location TEXT`, `lat DOUBLE`, `lon DOUBLE`, `timezone TEXT`, `language TEXT default 'ru'`, `notification_opt_in BOOL`, `created_at`, `updated_at`, `last_seen` | core profile |
| `natal_charts` | `user_id FK users`, `chart_json JSONB`, `computed_at TIMESTAMP`, `version SMALLINT` | heavy data, lazy computed |
| `forecasts` | `id UUID`, `user_id`, `kind ENUM('short','full')`, `content_short TEXT NULL`, `content_full JSONB NULL`, `transit_snapshot JSONB`, `speed_tag SMALLINT`, `depth_tag SMALLINT`, `caution_tag SMALLINT`, `generated_at TIMESTAMP`, `uniq_idx (user_id, kind, generated_at::date)` | stores all texts |
| `archive_feedback` | `id UUID`, `forecast_id FK forecasts`, `user_id`, `value ENUM('accurate','off')`, `submitted_at` | «сбылось / нет» |
| `access_flags` | `user_id PK`, `beta_full_enabled BOOL DEFAULT TRUE`, `beta_sos_enabled BOOL DEFAULT TRUE`, `notes TEXT`, `granted_at TIMESTAMP` | toggles while всё free |
| `emergency_questions` | `id UUID`, `user_id`, `question TEXT`, `answer TEXT`, `asked_at`, `answer_sent_at`, `next_allowed_at`, `status ENUM('pending','sent','error')` | mini-чат |
| `notifications` | `id UUID`, `user_id`, `type ENUM('daily_reminder','full_unlock','sos_invite','streak_cheer')`, `payload JSONB`, `scheduled_at`, `status ENUM('scheduled','sent','skipped','error')` | scheduler |
| `events_log` | `id UUID`, `user_id`, `event TEXT`, `payload JSONB`, `created_at TIMESTAMP`, `source TEXT` | analytics |

Indexes:
- `forecasts_user_kind_date_idx` on `(user_id, kind, date_trunc('day', generated_at))`.
- `emergency_questions_user_idx` on `(user_id, asked_at DESC)`.
- `events_log_event_idx` on `(event, created_at)`.

---

### 3. Redis Usage
- `redis://0/0`: aiogram FSM storage (key: `fsm:{telegram_id}`).
- `redis://0/1`: short forecast cache `forecast:{user_id}:{date}` (JSON).
- `redis://0/2`: rate limits `sos_limit:{user_id}` with TTL 24h.
- `redis://0/3`: Celery broker & result backend.

Key TTLs:
- Short forecast cache: expire at local midnight + 1h.
- Full forecast cache: same TTL but stored in Postgres as truth.

---

### 4. Core Sequence Diagrams

#### 4.1 Onboarding + Short Forecast
```
User -> BotGateway: /start
BotGateway -> CoreAPI /users: create_or_update_profile
CoreAPI -> AstrologyService: compute_natal_if_needed
CoreAPI -> ForecastService: fetch_short(user_id)
ForecastService -> Redis: check cache
alt cache hit
  ForecastService -> CoreAPI: cached forecast_id
else cache miss
  ForecastService -> AstrologyService: current_transits(now, user.tz)
  ForecastService -> LLM Orchestrator: render_short(context)
  ForecastService -> PostgreSQL: insert forecasts(kind='short')
  ForecastService -> Redis: cache text
end
CoreAPI -> BotGateway: forecast payload
BotGateway -> User: message + CTA buttons
CoreAPI -> EventsLog: record `short_forecast_viewed`
```

#### 4.2 Feature Unlock → Full Forecast
```
User -> BotGateway: presses "Раскрыть полный расклад"
BotGateway -> CoreAPI /access/intent_full: log intent, ensure `beta_full_enabled`
CoreAPI -> ForecastService: fetch_full(user_id)
ForecastService -> PostgreSQL: check existing full forecast for today
alt exists
  ForecastService -> BotGateway: hydrated text
else
  ForecastService -> AstrologyService: highlight_transits grouped by domains
  ForecastService -> LLM Orchestrator: render_full(finance, love, health, advice)
  ForecastService -> PostgreSQL: insert forecasts(kind='full')
end
BotGateway -> User: Markdown full report + quick replies
EventsLog: record `full_forecast_viewed`
```

#### 4.3 Emergency Question
```
User -> BotGateway: /sos
BotGateway -> Redis: check `sos_limit`
alt limit exists
  BotGateway -> User: "Доступно через X часов"
else
  BotGateway -> CoreAPI /emergency: create question
  CoreAPI -> AstrologyService: astro_slice(lite)
  CoreAPI -> LLM Orchestrator: render_emergency(question, astro_slice)
  CoreAPI -> PostgreSQL: save answer, `next_allowed_at = now + 24h`
  BotGateway -> User: send answer (2 messages)
  Redis: set `sos_limit` TTL 24h
end
EventsLog: `emergency_question_asked`
```

#### 4.4 Daily Broadcast & Reminder
```
Celery Beat 02:00 -> ForecastEngine.daily_event()
ForecastEngine -> AstrologyService: daily_transit_summary
ForecastEngine -> LLM Orchestrator: render_daily_event
ForecastEngine -> Telegram Channel: sendMessage
ForecastEngine -> Notifications: enqueue `daily_reminder` for inactive users
Notifications worker -> Telegram Bot API: push DM
EventsLog: `daily_event_published`, `reminder_sent`
```

---

### 5. API Surface (FastAPI Routers)

| Route | Method | Auth | Description |
| --- | --- | --- | --- |
| `/users` | `POST` | Bot token (service-to-service) | create/update profile, returns `user_id`, `timezone` |
| `/forecasts/short` | `POST` | Bot | returns latest short forecast text (generates if missing) |
| `/forecasts/full` | `POST` | Bot | returns today’s full forecast (force generate if allowed) |
| `/archive` | `GET` | Bot | list of dates + ids |
| `/archive/{forecast_id}` | `GET` | Bot | returns stored forecast |
| `/archive/{forecast_id}/feedback` | `POST` | Bot | store «сбылось/нет» |
| `/emergency` | `POST` | Bot | create and answer SOS question |
| `/access/intent` | `POST` | Bot | log CTA intents (`full`, `archive`, `sos`) |
| `/admin/stats` | `GET` | Admin JWT | aggregated metrics for dashboard |

All endpoints share middleware injecting `request_id`, `telegram_id` (from signed payload), `locale`.

---

### 6. Prompts & Templates

| Template | Input fields | Output contract |
| --- | --- | --- |
| `short_forecast.j2` | `sun_sign`, `moon_phase`, `top_transits`, `speed_tag`, `depth_tag`, `caution_tag`, `tone_hint`, `user_name?` | ≤380 chars, 2–3 sentences, contains emoji + CTA text placeholder. |
| `full_forecast.json` | For each domain: `planetary_context`, `trend`, `risk`, `action`. Advice seed. | JSON with 4 sections; post-processor converts to Markdown with emojis and bullet points. |
| `emergency.txt` | `question`, `astro_slice`, `tone="supportive"`, `constraints` | ≤120 words, includes disclaimer sentence, optional split markers `\n---\n` for multi-message. |
| `daily_event.txt` | `event_name`, `planets`, `impact`, `quick_action` | 250–300 chars, mention event + specific action. |

Implementation: use `jinja2` for deterministic scaffolding before sending to OpenAI (GPT‑4o‑mini). Guardrails via moderation endpoint; fallback templates stored in `app/templates/fallbacks/`.

---

### 7. Implementation Tasks per Layer

**Bot Gateway**
- [ ] Switch from polling to webhook (FastAPI route `/telegram/webhook`).
- [ ] Implement FSM states for onboarding (`Start`, `BirthDate`, `Details`, `Completed`) with aiogram `StatesGroup`.
- [ ] Add handlers for `/forecast`, `/full`, `/archive`, `/sos`, inline keyboards for CTA.
- [ ] Implement callback data factories for archive pagination and feedback.

**Core API**
- [ ] Scaffold FastAPI app with routers, dependency injection (DB session, Redis, config).
- [ ] Implement `UserService` (CRUD, timezone detection via `timezonefinder` library).
- [ ] Implement `ForecastService` with caching, LLM orchestration, persistence.
- [ ] Expose `/forecasts` endpoints + tests (pytest + httpx AsyncClient).

**Astrology Service**
- [ ] Bundle Swiss Ephemeris data (Docker volume).
- [ ] Implement `compute_natal(user)` caching results in `natal_charts`.
- [ ] Implement `current_transits(dt, lat, lon)` returning aspects with tags.
- [ ] Provide helper `transits_to_tags` to map to `speed/depth/caution`.

**LLM Orchestrator**
- [ ] Prompt builder classes (ShortPrompt, FullPrompt, EmergencyPrompt, DailyPrompt).
- [ ] Client wrapper for OpenAI with retry/backoff and token budgeting.
- [ ] Guardrails: length check, banned content detection, fallback to template.

**Emergency Service**
- [ ] API endpoint to accept question, check Redis TTL, persist to DB.
- [ ] Generate response via orchestrator, store status, send to bot (webhook call).
- [ ] Provide timer text (time delta) for next availability.

**Notifications & Scheduler**
- [ ] Celery worker configured with Redis, tasks for daily broadcast, reminders, streak messages.
- [ ] APScheduler (or Celery beat) triggers `daily_event`, `reminder_sweeper`, `streak_job`.
- [ ] Worker uses Core API services to fetch target users and queue sendMessage via bot token.

**Admin Dashboard**
- [ ] Secure route `/admin` with Telegram Login widget or shared secret.
- [ ] Aggregate metrics via SQL queries (DAU, full unlock rate, SOS usage, archive feedback).
- [ ] Provide golden report for manual export (CSV).

---

### 8. DevOps & Environments

| Aspect | Plan |
| --- | --- |
| **Containers** | `bot`, `api`, `worker`, `scheduler`, `db`, `redis`. Docker Compose for dev, Helm/Compose for prod. |
| **Config** | `.env` with sections: Telegram Bot token, OpenAI key, Redis URL, Postgres DSN, timezone defaults. Use Pydantic `BaseSettings`. |
| **Migrations** | Alembic autogenerate + revision per table change. |
| **CI/CD** | GitHub Actions: lint (ruff, mypy), tests, build images, push to registry, deploy to staging via SSH/Render. |
| **Monitoring** | `prometheus_fastapi_instrumentator`, Celery Flower for queue, Sentry SDK for bot & API. |
| **Secrets** | Doppler/Vault/1Password CLI; never commit `.env`. |

---

### 9. Testing Strategy (per layer)
- **Unit**: `pytest` for astrology calculations (fixture with known dates), forecast formatting, prompt builder outputs.
- **Service**: simulate LLM responses via VCR or faker to test `ForecastService`.
- **API**: httpx AsyncClient to test `/users`, `/forecasts`, `/emergency` flows.
- **Bot**: aiogram test tools to simulate updates (or golden transcripts).
- **Load**: Locust script hitting `/forecasts/short` for 1k users; Celery stress test for reminders.

---

### 10. Work Breakdown Structure (Practical Order)
1. **Foundation**
   - Setup FastAPI project structure, config, DB connection, Alembic.
   - Integrate aiogram router with webhook endpoint.
2. **Profiles & Onboarding**
   - Implement `/users` API, FSM, validation, timezone detection.
3. **Astro & LLM Core**
   - Build astrology service + caching.
   - Implement short forecast generation + storage.
4. **Full Experience**
   - CTA handling, full forecast generation, archive browsing, feedback.
5. **Emergency Layer**
   - SOS endpoint, rate limiting, messaging split.
6. **Retention Mechanics**
   - Notifications scheduler, daily broadcast, streak tracking.
7. **Admin & Analytics**
   - Events log, dashboard, export.
8. **Polish**
   - Logging, tracing, fallback templates, improved copy, automated tests.

Deliverables from this document: team can start coding each module with clear boundaries, DB schema, API contracts, and queue flows without re-opening product spec.
