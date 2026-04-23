# Automation Service

Python/FastAPI service that owns Postgres and runs the Instagram automation pipeline. It also hosts the Link-in-Bio product (pages, links, cards, lead capture, analytics).

## Two entry points

This service runs as **two processes** — the HTTP API and the RabbitMQ worker are independent:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000   # REST API
python -m app.worker                                     # RabbitMQ consumer
```

Both read the same `.env` and share the same Postgres via `app/db/session.py`.

## Package management

**uv**, not pip.

```bash
uv sync                 # install
uv add <package>        # add runtime dep
uv add --dev <package>  # add dev dep
uv run <cmd>            # run inside the env
```

## Tech stack

- Python 3.11+ (`.python-version`: 3.11.13)
- FastAPI 0.128, Uvicorn
- SQLAlchemy 2.0 async + asyncpg (psycopg async actually — `postgresql+psycopg_async://...`, see `app/config.py`)
- Alembic 1.18 for migrations
- aio-pika 9.5 (RabbitMQ)
- python-jose + bcrypt for JWT + password hashing
- cryptography / Fernet for encrypting Instagram access tokens
- httpx for outbound Graph API calls
- BeautifulSoup4 for OpenGraph scraping (bio-link previews)
- structlog for logging
- Pydantic 2 + pydantic-settings

## Project structure

```
app/
├── main.py                      # FastAPI app, CORS, router registration
├── worker.py                    # Worker entry (`python -m app.worker`) — consumes instagram.comments
├── config.py                    # pydantic-settings, env loading
├── db/
│   └── session.py               # AsyncEngine, async_session_maker
├── api/
│   ├── deps.py                  # DI: auth (cookie JWT), DB session
│   └── routes/                  # One file per domain, all mounted at /api/v1
│       ├── auth.py              # register, login, logout, refresh, me
│       ├── instagram.py         # OAuth connect + callback, account listing
│       ├── automations.py       # CRUD for automation rules
│       ├── bio_pages.py         # user's link-in-bio page
│       ├── bio_links.py         # URL links on a bio page
│       ├── bio_cards.py         # lead-capture form cards
│       ├── page_items.py        # ordered layout items on a bio page
│       ├── routing_rules.py     # lead routing (email/webhook/redirect)
│       ├── leads.py             # captured leads CRUD + export
│       ├── analytics.py         # aggregated analytics for dashboards
│       ├── public_bio.py        # unauthenticated rendering of /bio/:slug
│       ├── social_links.py      # social-profile links
│       └── utils.py             # misc utilities (og-scrape, etc.)
├── models/                      # SQLAlchemy ORM models (one file per table)
├── schemas/                     # Pydantic request/response schemas
└── services/                    # Business logic
    ├── auth.py                  # password hash, JWT issue/verify
    ├── instagram_client.py      # Graph API client (OAuth + DM send)
    ├── comment_processor.py     # Webhook-event → automation-match → DM
    ├── rabbitmq_consumer.py     # aio-pika consumer (used by worker.py)
    ├── automation_repository.py
    ├── bio_page_service.py
    ├── bio_link_service.py
    ├── bio_card_service.py
    ├── page_item_service.py
    ├── routing_service.py
    ├── lead_service.py
    ├── analytics_service.py
    ├── geo_ip_service.py        # GeoLite2 country lookups
    ├── og_metadata_service.py   # OpenGraph scraping for link previews
    └── social_link_service.py
```

## Domain model

**Auth / accounts**
- `user.py` — `User` (email, hashed_password)
- `instagram_account.py` — `InstagramAccount` (linked to a user, stores Fernet-encrypted access token)

**Automation (DM pipeline)**
- `automation.py` — `Automation`, plus `TriggerType` (`ALL_COMMENTS | KEYWORD`) and `MessageType` (`TEXT | CAROUSEL`). Same file also defines `DMSentLog`, `CommentReplyLog`, and `CommenterDetails`.

**Link-in-Bio**
- `bio_page.py`, `bio_link.py`, `bio_card.py`, `page_item.py`, `routing_rule.py`, `lead.py`, `social_link.py`

**Analytics**
- `analytics_event.py` — raw events (views/clicks with IP, UA, country)
- `analytics_aggregate.py` — pre-computed rollups

## Webhook → DM processing path

```
RabbitMQ (queue: instagram.comments)
  └─▶ app/worker.py  (Worker.run)
       └─▶ app/services/rabbitmq_consumer.py  (aio-pika consume loop)
            └─▶ Worker.process_comment(payload)
                 └─▶ app/services/comment_processor.py  (CommentProcessor.process)
                      ├─▶ load Automation + InstagramAccount from DB
                      ├─▶ match by TriggerType / keywords
                      ├─▶ app/services/instagram_client.py  (send DM via Graph API)
                      └─▶ write DMSentLog / CommentReplyLog
```

The worker currently only subscribes to `instagram.comments`. Other event types (`messages`, `mentions`, `story_insights`) are published by the webhook service but not yet consumed here.

## Database migrations

Alembic lives in `alembic/`. Migrations are numbered `NNN_short_name.py`:

| # | Migration | Notes |
|---|---|---|
| 001 | `001_initial.py` | Users, InstagramAccounts, Automations, DMSentLog |
| 002 | `002_add_comment_reply_fields_to_automation.py` | Auto-reply fields |
| 003 | `003_add_link_in_bio.py` | Full Link-in-Bio schema |
| 004 | `004_add_user_id_to_bio_pages.py` | Bio pages owned by user |
| 005 | `005_add_social_links.py` | Social-link model |
| 006 | `006_add_comment_reply_log.py` | Comment reply tracking |
| 007 | `007_add_commenter_details.py` | Commenter profile cache |
| 008 | `008_add_carousel_support.py` | CAROUSEL message type |

```bash
alembic upgrade head           # apply
alembic revision -m "name"     # new migration (rename to NNN_name.py)
alembic downgrade -1           # revert one
```

The Docker image runs `alembic upgrade head` on startup.

## Environment variables

All loaded by `app/config.py`. See `.env.example`.

**App / CORS**
- `APP_ENV` (`development` controls cookie `secure` flag)
- `APP_PORT` (default 8000)
- `FRONTEND_URL` — used as the only allowed CORS origin

**Database** (URL is built from parts in `config.py`)
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

**Auth**
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`

**Instagram OAuth / Graph API**
- `INSTAGRAM_CLIENT_ID`, `INSTAGRAM_CLIENT_SECRET`, `INSTAGRAM_REDIRECT_URI`, `INSTAGRAM_GRAPH_API_URL`

**Crypto**
- `ENCRYPTION_KEY` — base64 Fernet key for access-token encryption. Rotating invalidates stored tokens.

**Integration**
- `RABBITMQ_URL` — single AMQP URL, must match the webhook service's broker

**Other**
- `LOG_LEVEL`, `GEOIP_DATABASE_PATH` (GeoLite2 `.mmdb`), `ANALYTICS_RETENTION_DAYS`, `BIO_PAGE_ENABLED`

## CORS / cookies

`main.py` sets `allow_origins=[FRONTEND_URL]` and `allow_credentials=True`. It cannot use `"*"` — browsers refuse credentialed requests to wildcard origins. Frontend must call this API from exactly `FRONTEND_URL`.

## Commands

```bash
# Dev
docker-compose up -d                      # Postgres + API (with migrations)
uv run uvicorn app.main:app --reload      # API only (needs Postgres running)
python -m app.worker                      # Worker (needs RabbitMQ + Postgres)

# Migrations
alembic upgrade head
alembic downgrade -1

# Quality
uv run ruff format .
uv run ruff check .
uv run pytest
```

## Health check

`GET /health` → `{"status": "healthy", "service": "automation-service"}`. OpenAPI docs at `/docs`.
