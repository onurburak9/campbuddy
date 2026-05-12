# CampBuddy Phase 2 — REST API + Web UI Design

**Date:** 2026-05-12
**Status:** Approved

## Overview

Phase 2 adds a FastAPI REST API and a React single-page application so users can manage their own scans and view results via browser. Admin management (creating users, setting scan limits) stays in the CLI. Everything runs in Docker; only the frontend container is exposed to the public internet.

## Architecture

### Containers

| Container | Public | Command |
|-----------|--------|---------|
| `frontend` | ✅ :80/:443 | Nginx — serves React build, proxies `/api/*` to `api:8000` |
| `api` | internal :8000 | `uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| `app` | internal | `python main.py` (unchanged) |
| `playwright` | internal :8001 | unchanged |

`api` and `app` use the **same Docker image**, different `command:` entries in `docker-compose.yml`. Both mount the same SQLite volume.

### Directory Structure (additions only)

```
core/services/          shared business logic (imported by api/ and cli.py)
  scans.py
  users.py
  history.py

api/                    thin FastAPI layer — HTTP, auth, serialization only
  main.py
  auth.py               session cookie helpers, bcrypt verification
  deps.py               FastAPI dependency: current_user
  routes/
    auth.py
    scans.py
    users.py

frontend/               React SPA
  Dockerfile            multi-stage: vite build → nginx image
  nginx.conf            serves static files, proxies /api/*
  src/
    pages/              Login, Dashboard, ScanDetail, CreateScan, EditScan, Profile
    components/
    api/                fetch wrappers for each route group
    contexts/           AuthContext
```

## Data Model Changes

Two new columns on `users`:

```python
hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
scan_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
```

`hashed_password` is nullable so existing YAML-seeded users are unaffected. `POST /auth/login` returns 401 if the user exists but has no password set (admin must run `update-user --password` first). Both columns are additive — `create_tables()` handles them on first run. No migration tool needed.

**CLI additions to `update-user`:**
- `--password <plaintext>` — bcrypt-hashes on write
- `--scan-limit N` — sets the per-user scan cap

## Authentication

- Email + password, bcrypt (`passlib[bcrypt]`)
- On successful login: sign a JWT (`python-jose`) containing `user_id`, set as HttpOnly cookie (`campbuddy_session`), 24h expiry
- All `/api/v1/*` routes except `POST /auth/login` require a valid cookie
- Cookie is HttpOnly — JS never reads it directly
- On re-login: old cookie is overwritten; no explicit invalidation store needed at this scale

## API Routes

Base path: `/api/v1/`

### Auth
```
POST /auth/login          { email, password } → 200 + sets cookie | 401
POST /auth/logout         → 200 + clears cookie
GET  /auth/me             → { id, email, scan_limit, scans_used }
```

### Scans
```
GET    /scans             → list caller's scans + last run outcome
POST   /scans             → create (raises 409 if at scan_limit)
GET    /scans/{id}        → scan detail
PATCH  /scans/{id}        → update editable fields
DELETE /scans/{id}        → delete scan + all history
POST   /scans/{id}/pause  → set status=paused
POST   /scans/{id}/resume → set status=active
```

### History
```
GET /scans/{id}/runs      → paginated ScanRun list
GET /scans/{id}/results   → paginated ScanResult list
```

### Profile
```
PATCH /users/me           → update email, telegram_chat_id,
                            recreationgov_email, recreationgov_password
```

**Ownership invariant:** all scan routes verify the scan belongs to the calling user in the service layer. Violation → 403. `scan_limit` is not writable via the API.

## Service Layer

All functions accept a SQLAlchemy `Session` and return ORM objects or raise domain exceptions (not HTTP exceptions — that's the API layer's job).

### `core/services/scans.py`
```python
def list_scans(db, user_id) -> list[Scan]
def get_scan(db, scan_id, user_id) -> Scan          # raises NotFound / Forbidden
def create_scan(db, user_id, data) -> Scan           # raises LimitExceeded
def update_scan(db, scan_id, user_id, data) -> Scan
def delete_scan(db, scan_id, user_id) -> None
def pause_scan(db, scan_id, user_id) -> Scan
def resume_scan(db, scan_id, user_id) -> Scan
```

### `core/services/users.py`
```python
def get_user_by_email(db, email) -> User
def update_profile(db, user_id, data, encryption_key) -> User
def scans_used(db, user_id) -> int
```

### `core/services/history.py`
```python
def list_runs(db, scan_id, user_id, page, page_size) -> list[ScanRun]
def list_results(db, scan_id, user_id, page, page_size) -> list[ScanResult]
```

The existing `core/runner.py` continues to read `Scan` rows directly — the service layer is additive, not a replacement.

## Frontend

**Stack:** Vite + React, plain `fetch()`, Tailwind CSS. No state management library.

**Pages:**

| Route | Page |
|-------|------|
| `/login` | Email + password form |
| `/` | Dashboard — scan list with status badges, pause/resume |
| `/scans/new` | Create scan form |
| `/scans/:id` | Scan detail — config, run history, results table |
| `/scans/:id/edit` | Edit scan (same form, pre-filled) |
| `/profile` | Email, Telegram, Recreation.gov credentials |

**Auth flow:** App loads → `GET /api/v1/auth/me`. If 401, redirect to `/login`. All routes except `/login` are protected. Logout calls `POST /api/v1/auth/logout` then redirects.

**Nginx:** serves `index.html` for all non-`/api` paths (client-side routing). Proxies `/api/*` to `api:8000` on the internal Docker network.

**Build:** `frontend/Dockerfile` is multi-stage — Node image runs `vite build`, output is copied into an `nginx:alpine` image. No Node.js in production.

## Testing

Mirrors the existing `tests/` structure. In-memory SQLite, no real network calls.

```
tests/
  services/
    test_scans.py     — CRUD, scan_limit enforcement, ownership
    test_users.py     — profile updates, credential encryption
    test_history.py   — pagination, ownership checks
  api/
    test_auth.py      — login/logout/me, bad credentials
    test_scans.py     — all routes, 401 without cookie, 403 wrong owner
    test_users.py     — PATCH /users/me
```

Coverage target: 90%+ on `core/services/` and `api/`.

## Docker Compose Changes

```yaml
services:
  app:
    build: .
    command: python main.py
    volumes:
      - ./data:/app/data
    env_file: .env

  api:
    build: .                          # same image as app
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    volumes:
      - ./data:/app/data
    env_file: .env
    depends_on: [app]

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on: [api]

  playwright:
    # unchanged
```

## New Dependencies

**Python (`requirements.txt`):**
- `fastapi`
- `uvicorn[standard]`
- `passlib[bcrypt]`
- `python-jose[cryptography]`
- `python-multipart`

**Frontend (`frontend/package.json`):**
- `react`, `react-dom`, `react-router-dom`
- `vite`, `@vitejs/plugin-react`
- `tailwindcss`

## Out of Scope (Phase 2)

- Admin web UI for user management (stays in CLI)
- Telegram bot (Phase 3)
- PostgreSQL migration (SQLite remains)
- Real-time scan status (polling on page load is sufficient)
- Email verification on account creation
