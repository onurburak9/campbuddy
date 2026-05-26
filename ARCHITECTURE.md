# CampBuddy Architecture

## System Overview

CampBuddy monitors campground availability, automates booking, and exposes a REST API for users to manage their scans via browser.

```
┌──────────────────────────────────────────────────────────────┐
│                            VPS                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  app container (scheduler)                          │    │
│  │  ┌────────────┐    ┌─────────────┐                  │    │
│  │  │ APScheduler│───▶│   Runner    │                  │    │
│  │  │  (jobs)    │    │  (per scan) │                  │    │
│  │  └────────────┘    └──────┬──────┘                  │    │
│  │                           │                         │    │
│  │              ┌────────────┼────────────┐            │    │
│  │              ▼            ▼            ▼            │    │
│  │        ┌──────────┐ ┌─────────┐ ┌──────────┐       │    │
│  │        │ camply   │ │ Booking │ │ Notifier │       │    │
│  │        │ (avail.) │ │ Client  │ │ (email + │       │    │
│  │        └──────────┘ └────┬────┘ │ telegram)│       │    │
│  │                          │      └──────────┘       │    │
│  │        ┌─────────────────┘                         │    │
│  │        ▼                                            │    │
│  │  ┌──────────┐    SQLite                             │    │
│  │  │Playwright│◀── campbuddy.db ──────────────────┐  │    │
│  │  │ sidecar  │    (shared volume)                │  │    │
│  │  └──────────┘                                   │  │    │
│  └─────────────────────────────────────────────────│──┘    │
│                                                    │        │
│  ┌─────────────────────────────────────────────────│──┐    │
│  │  api container  :8000 (localhost)               │  │    │
│  │  ┌──────────────────────────────────────────┐   │  │    │
│  │  │ FastAPI (uvicorn)                        │   │  │    │
│  │  │  /api/v1/auth  /api/v1/scans  /api/v1/users│  │  │    │
│  │  │  JWT cookie auth · scan CRUD · history   │   │  │    │
│  │  └──────────────────────┬───────────────────┘   │  │    │
│  │                         │  core/services/        │  │    │
│  │                         └───────────────────────►┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Components

### APScheduler (`core/scheduler.py`)
Runs one background job per active scan, firing at each scan's `polling_interval`. A 60-second sync job adds/removes jobs when scan statuses change in the DB.

### Runner (`core/runner.py`)
Executes a single scan end-to-end:
1. Calls availability checker
2. Writes `scan_run` record (always, regardless of outcome)
3. For each new site: saves result, calls booking sidecar, then routes by urgency —
   cart-add succeeded → immediate per-site notification; otherwise → buffered into
   a per-run digest sent once after the loop

### Availability Checker (`core/availability.py`)
Thin wrapper around camply's OO API. Converts a `Scan` DB record → `SearchRecreationDotGov` call → returns `list[AvailableCampsite]`. Provider class is looked up from `PROVIDER_MAP`.

### Booking Client (`core/booking.py`)
HTTP client (httpx) that POSTs to the Playwright sidecar's `/add-to-cart` endpoint. Returns `True`/`False`. Failures are non-fatal — user is always notified with the booking URL.

### Notifier (`core/notifier.py`)
Two dispatch paths: `notify(scan, payload, settings)` for urgent single-site sends (cart-add success) and `notify_digest(scan, payloads, settings)` for batched multi-site summaries (everything else). Both honour per-scan `notify_via_email` and `notify_via_telegram` flags. Email uses smtplib/SMTP with UTF-8 MIMEText; Telegram uses the Bot API via `requests` with defensive truncation at 4000 chars. Booking URL always included in plain text.

### Playwright Sidecar (`playwright_service/`)
Isolated FastAPI service in its own Docker container. Receives `POST /add-to-cart { booking_url, email, password, check_in, check_out }` (dates in `MM-DD-YYYY`), drives headless Chromium to log in and add the site to cart, returns `{ success, error }`. Runs separately so a browser crash cannot kill the scheduler.

Bot-detection hardening: `playwright-stealth`, Chrome 136 user agent + matching `sec-ch-ua` headers, human-like typing delays, and jitter between actions. Dates are pre-selected by injecting `r1s_search_session` into `localStorage` before navigating to the campsite page — see [`docs/superpowers/recreation-gov-checkout-flow.md`](docs/superpowers/recreation-gov-checkout-flow.md) for the full site map.

### Service Layer (`core/services/`)
Shared business logic imported by both the API routes and the CLI. Three modules:
- `scans.py` — scan CRUD, ownership check, soft-delete, pause/resume, per-user `scan_limit` enforcement
- `users.py` — profile reads/updates, Recreation.gov credential encryption, `scans_used` count
- `history.py` — paginated `ScanRun` and `ScanResult` queries (ownership-gated via `get_scan`)

Domain exceptions (`NotFound`, `Forbidden`, `LimitExceeded`) live in `core/services/exceptions.py` and are translated to HTTP status codes at the route layer.

### REST API (`api/`)
FastAPI application served by uvicorn on port 8000 (localhost-only). Session-cookie JWT auth (`HS256`, 24 h TTL, `httponly`/`samesite=lax`). Routes: `POST /api/v1/auth/login`, `POST /auth/logout`, `GET /auth/me`, full scan CRUD + `/{id}/pause` + `/{id}/resume`, `GET /{id}/runs`, `GET /{id}/results`, `PATCH /api/v1/users/me`. Login is timing-safe: a dummy hash is evaluated even for unknown emails to prevent user enumeration.

### Crypto (`core/crypto.py`)
Fernet (AES-128-CBC + HMAC) encrypt/decrypt for Recreation.gov passwords. Key lives in `ENCRYPTION_KEY` env var; validated at startup by `Settings`.

### Settings (`config/settings.py`)
pydantic v1 `BaseSettings` (built-in to pydantic v1 — pydantic-settings package is intentionally NOT used because camply requires pydantic v1). Validates `ENCRYPTION_KEY` is a real Fernet key. Cached via `@lru_cache`. `api_secret_key` defaults to `""` and is validated non-empty in the API lifespan; the scheduler ignores it.

## Data Flow

```
Scheduler fires scan_id=N
    → runner.run_scan(N)
        → availability.check_availability(scan)
            → camply.SearchRecreationDotGov(...).get_matching_campsites(continuous=False)
            → returns [AvailableCampsite, ...]
        → write ScanRun(outcome, sites_found)
        → for each site:
            → dedup check (campsite_id + booking_date already in scan_results?)
            → write ScanResult(cart_added=False, notified=False)
            → booking.attempt_cart_add(url, email, password, check_in, check_out)
                → POST playwright_service /add-to-cart {booking_url, email, password, check_in, check_out}
            → notifier.notify(scan, payload)
                → send_email() and/or send_telegram()
            → update ScanResult(cart_added, notified, timestamps)
        → commit
```

## Database Schema

```
users
  id, email (unique), telegram_chat_id, recreationgov_email
  recreationgov_password (Fernet-encrypted, String(256))
  hashed_password (bcrypt digest for Web UI login, nullable)
  scan_limit (int, default 5 — max active scans per user)
  created_at (timezone-aware), deleted_at (soft-delete, nullable)

scans
  id, user_id→users (indexed), name (optional label), provider
  status (enum: active|paused|completed)
  polling_interval
  rec_area_ids (JSON list[int]), campground_ids, campsite_ids
  search_windows (JSON list[dict]), nights
  days_of_week (JSON list[int]), weekends_only
  notify_via_email, notify_via_telegram, notify_on_new_only
  created_at (timezone-aware), deleted_at (soft-delete, nullable)

scan_runs                          ← always written, every execution
  id, scan_id→scans (indexed)
  started_at, finished_at (both timezone-aware)
  outcome (enum: success|no_results|error|null), sites_found, error_message

scan_results                       ← one row per available site per run
  id, scan_run_id→scan_runs (indexed), scan_id→scans
  campsite_id, facility_name, site_name, campsite_type
  booking_date, booking_end_date, booking_url
  first_seen_at, cart_added, cart_added_at, notified, notified_at
  composite index (scan_id, campsite_id, booking_date) for dedup queries
```

All cascades: deleting a User cascades to their Scans, ScanRuns, and ScanResults.

## Supported Providers

| Provider key | camply class | Notes |
|---|---|---|
| `RecreationDotGov` | `SearchRecreationDotGov` | Default. Uses unofficial availability API. |

To add a provider: see "Adding a New Campground Provider" in CLAUDE.md.

## Deployment

Three Docker containers, `docker-compose.yml`:
- `app` — scheduler + runner + notifier; runs `alembic upgrade head` then `python main.py` via `entrypoint.sh`
- `api` — FastAPI REST API; `uvicorn api.main:app` on `127.0.0.1:8000`; `depends_on: app` so migrations run first
- `playwright` — Playwright sidecar (FastAPI, port 8001 internal only)

SQLite database mounted at `./data/campbuddy.db`. Both `app` and `api` share this volume. Back up this file.

## Phased Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Core engine | ✅ Done | Scheduler, runner, notifier, Playwright sidecar |
| 2 — Web dashboard | 🔨 In progress | REST API (this PR) + React frontend (planned) |
| 3 — Telegram bot | Planned | Create/manage scans via Telegram commands |

## Architecture Decision Records

- [ADR 001](docs/adr/001-camply-as-engine.md) — Use camply as availability engine
- [ADR 002](docs/adr/002-playwright-sidecar.md) — Playwright in isolated Docker sidecar
- [ADR 003](docs/adr/003-sqlite-first.md) — SQLite for Phase 1
- [ADR 004](docs/adr/004-notify-on-cart-failure.md) — Notify even when cart add fails
- [ADR 005](docs/adr/005-pydantic-v1.md) — pydantic v1 (camply constraint)
- [ADR 006](docs/adr/006-split-urgent-and-digest-notifications.md) — Split urgent and digest notifications
