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
3. Dedupes new sites against existing `scan_results`, inserts rows, and updates the
   availability lifecycle (bumps `last_seen_at`/`is_available` for sites still present,
   flips previously-available sites that dropped out to unavailable)
4. Finalizes the `ScanRun` (`outcome`, `sites_found`, `finished_at`) *before* any
   cart-add, so a sidecar crash can't leave the run record orphaned
5. If there are new sites, sends the "available" notification (`notify_available`)
6. If the scan has `auto_book` enabled and the user has both Recreation.gov
   credentials, checks sidecar health, then batch-adds all new sites to cart in a
   single sidecar call (one login per run) and sends the cart-results notification
   (`notify_cart_results`)

### Availability Checker (`core/availability.py`)
Thin wrapper around camply's OO API. Converts a `Scan` DB record → `SearchRecreationDotGov` call → returns `list[AvailableCampsite]`. Provider class is looked up from `PROVIDER_MAP`.

### Booking Client (`core/booking.py`)
HTTP client (httpx) with three functions: `sidecar_healthy(settings)` — preflight `GET /health` check; `attempt_cart_add_batch(sites, email, password, settings)` — `POST /add-to-cart-batch` with the full list of new sites for a scan, logging in once and adding all of them in a single sidecar session, returning one result dict per site; and `attempt_cart_add` — the legacy single-site `POST /add-to-cart` call, still used by the `cli.py cart-add` debug command. Cart-add is opt-in per scan via the `auto_book` flag; failures are non-fatal — the user is always notified.

### Notifier (`core/notifier.py`)
Two-phase dispatch per scan run: `notify_available(scan, payloads, settings)` is sent as soon as new sites are found, before any cart-add attempt, and `notify_cart_results(scan, payloads, settings, sidecar_available=...)` is sent after the batch cart-add completes (only for scans with `auto_book` enabled), including a distinct "sidecar unavailable" variant when the preflight health check fails. Both honour per-scan `notify_via_email` and `notify_via_telegram` flags. Email uses smtplib/SMTP with UTF-8 MIMEText; Telegram uses the Bot API via `requests` with defensive truncation at 4000 chars. Booking URL always included in plain text.

### Playwright Sidecar (`playwright_service/`)
Isolated FastAPI service in its own Docker container. `POST /health` reports readiness for the runner's preflight check. `POST /add-to-cart-batch { email, password, sites: [{ booking_url, check_in, check_out }, ...] }` is the primary path used by `auto_book` scans — logs in once, then adds every site to cart in the same browser session, returning `{ results: [{ success, error }, ...] }` (one per site, dates in `MM-DD-YYYY`). `POST /add-to-cart { booking_url, email, password, check_in, check_out }` remains for single-site use (e.g. the `cli.py cart-add` debug command). Runs separately so a browser crash cannot kill the scheduler.

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
        → write ScanRun(started_at)
        → for each site:
            → dedup check (campsite_id + booking_date already in scan_results?)
            → write ScanResult(cart_added=False, notified=False, is_available=True)
        → update availability lifecycle for existing ScanResults (last_seen_at, is_available)
        → finalize ScanRun(outcome, sites_found, finished_at)   ← before any cart-add
        → if new sites found:
            → notifier.notify_available(scan, payloads, settings)
                → send_email_available() and/or send_telegram_available()
            → mark those ScanResults notified=True
        → if scan.auto_book and user has both rec.gov credentials:
            → booking.sidecar_healthy(settings)
                → not healthy → notifier.notify_cart_results(scan, payloads, settings, sidecar_available=False); stop
            → booking.attempt_cart_add_batch(sites, email, password, settings)
                → POST playwright_service /add-to-cart-batch {email, password, sites: [...]}  (one login, all sites)
            → update each ScanResult(cart_added, cart_added_at)
            → notifier.notify_cart_results(scan, payloads, settings)
                → send_email_available() and/or send_telegram_available() (cart-add outcome variant)
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
