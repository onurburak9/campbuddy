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
HTTP client (httpx). The runner uses two functions: `sidecar_healthy(settings)` — preflight `GET /health` check; and `attempt_cart_add_batch(sites, email, password, settings)` — `POST /add-to-cart-batch` with the full list of new sites for a scan, logging in once and adding all of them in a single sidecar session, returning one result dict per site. The HTTP timeout is derived from the batch size via `batch_timeout_seconds(n)` (60s login overhead + 30s per site); a fixed budget used to expire mid-batch and report every site as failed. A legacy single-site `attempt_cart_add` helper also exists but is no longer used in production (the batch path replaced it). Cart-add is opt-in per scan via the `auto_book` flag; failures are non-fatal — the user is always notified.

Outcome tracking: every attempt writes a logfmt event (`core/events.py`) to stdout, which ships to Loki, and the failure reason is persisted on `ScanResult.cart_error` so the API and UI can show *why* a site wasn't carted. `cart_added=False` on its own is ambiguous — it could mean failed, skipped over the cap, or never attempted. Reason codes are a small closed set so they work as Grafana labels; see [Debugging with Grafana](docs/agents/debugging-with-grafana.md#cart-add-outcomes) for queries and the alert rule.

The runner only carts the first `CART_ADD_MAX_SITES` (default 5) new sites per run. Each add places a real 15-minute hold on a live campsite and the sidecar works through them sequentially, so an unbounded batch would both take many minutes and hold a large share of a campground. Sites beyond the cap are still found, stored, and notified — just not carted.

### Notifier (`core/notifier.py`)
Two-phase dispatch per scan run: `notify_available(scan, payloads, settings)` is sent as soon as new sites are found, before any cart-add attempt, and `notify_cart_results(scan, payloads, settings, sidecar_available=...)` is sent after the batch cart-add completes (only for scans with `auto_book` enabled), including a distinct "sidecar unavailable" variant when the preflight health check fails. Both honour per-scan `notify_via_email` and `notify_via_telegram` flags. Email uses smtplib/SMTP with UTF-8 MIMEText; Telegram uses the Bot API via `requests` with defensive truncation at 4000 chars. Booking URL always included in plain text.

### Playwright Sidecar (`playwright_service/`)
Isolated FastAPI service in its own Docker container. `POST /health` reports readiness for the runner's preflight check. `POST /add-to-cart-batch { email, password, sites: [{ booking_url, check_in, check_out }, ...] }` is the primary path used by `auto_book` scans — logs in once, then adds every site to cart in the same browser session, returning `{ results: [{ success, error }, ...] }` (one per site, dates in `MM-DD-YYYY`). `POST /add-to-cart { booking_url, email, password, check_in, check_out }` remains for single-site use (e.g. the `cli.py test-cart` debug command, which calls it directly via `requests`). Runs separately so a browser crash cannot kill the scheduler.

Bot-detection hardening: the browser runs **headed** against an Xvfb display because Recreation.gov silently drops logins from headless Chromium — the form spins for ~30s and no auth request is ever sent. `playwright_service/entrypoint.sh` starts Xvfb once on `:99` and the image sets `DISPLAY=:99`, so the server *and* any `docker compose exec` share one display. A `STEALTH_JS` init script patches the usual fingerprint vectors, and typing/jitter delays mimic a human. The user agent is deliberately **not** overridden; spoofing it while `navigator.userAgentData` reported the real build triggered an "outdated browser" interstitial. Set `PLAYWRIGHT_HEADLESS=true` to force headless for local debugging.

Browser lifecycle: **one long-lived browser, a fresh context per request.** Closing a headed Chromium in this container never returns — it leaves zombie processes and wedges the container badly enough that `docker kill` fails. `context.close()` is instant, so isolation between requests (and between users' credentials) comes from contexts. `get_shared_browser()` relaunches if the browser dies. Playwright's sync objects are thread-bound and FastAPI runs sync endpoints on a threadpool, so all browser work is funnelled through a single dedicated thread via `run_in_browser_thread()`. On shutdown a FastAPI lifespan hook calls `playwright.stop()`, which reaps every chrome process — see [Verifying a clean restart](#verifying-a-clean-restart).

### Verifying a clean restart

A headed Chromium that is not released on shutdown leaves zombie processes and makes the container unstoppable: `docker stop` reports *"tried to kill container, but did not receive an exit event"*, the container cannot even be `exec`'d into, and only a daemon/VM restart clears it. Because `docker compose up -d` must stop and replace the sidecar whenever its image changes, that failure mode would break the normal deploy.

The lifespan hook prevents it. Measured with a live headed browser in the server process: `down` 1.0s, `up -d --force-recreate` 1.1s, `stop` 0.5s, with `Application shutdown complete` in the log.

Re-run this after any change to the browser lifecycle, or on a new host. It needs no credentials and places no cart holds — the dummy login fails, but a headed browser is launched first, which is the part that matters:

```bash
docker compose -p cb-verify build playwright
docker compose -p cb-verify up -d playwright
until docker compose -p cb-verify exec -T playwright curl -sf http://localhost:8001/health; do sleep 2; done

# ~50s: login fails, but the server now owns a live headed Chromium
docker compose -p cb-verify exec -T playwright curl -s -m 120 -X POST \
  http://localhost:8001/add-to-cart -H 'Content-Type: application/json' \
  -d '{"booking_url":"https://www.recreation.gov/camping/campsites/42210","email":"nobody@example.invalid","password":"nope","check_in":"10-12-2026","check_out":"10-14-2026"}'

docker compose -p cb-verify exec -T playwright ps -eo stat,comm | grep -c chrome  # expect > 0
time docker compose -p cb-verify down                                             # expect ~1s
```

If `down` instead hangs for ~24s and reports "did not receive an exit event", the hook is not completing. Check the sidecar log: it should reach `Application shutdown complete`, not stop at `Waiting for application shutdown`. Recovery is a daemon restart (`colima restart -p <profile>`, or `systemctl restart docker` on Linux); the first mitigation to try is `--timeout-graceful-shutdown` on uvicorn so it stops waiting on the hook.

Login is treated as unreliable by design: even headed, Recreation.gov's reCAPTCHA occasionally rejects a session, so cart-add failure is non-fatal and the user is always notified with the booking URL.

A successful add is detected by the redirect to `/camping/reservations/orderdetails`, **not** by the navbar cart badge — that badge is cumulative, so it would report success for a site that failed once any earlier site had been added.

`playwright_service/selector_check.py` probes the live login and campsite pages for every selector `browser.py` depends on, without credentials: `docker compose exec playwright python -m playwright_service.selector_check`. Run it when cart-add starts failing.

Dates are pre-selected by injecting `r1s_search_session` into `localStorage` before navigating to the campsite page — see [`docs/superpowers/recreation-gov-checkout-flow.md`](docs/superpowers/recreation-gov-checkout-flow.md) for the full site map.

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
