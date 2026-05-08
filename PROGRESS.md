# CampBuddy — Progress & Handoff

Status tracker for Phase 1 implementation. Refer to `ARCHITECTURE.md` for design and `docs/superpowers/plans/2026-05-06-campbuddy-phase1.md` for the full plan.

## Status

| # | Milestone | Status | PR |
|---|---|---|---|
| M1 | Foundation (models, crypto, settings, docs) | ✅ Merged | [#1](https://github.com/onurburak9/campbuddy/pull/1) |
| M2 | Availability — camply OO API wrapper | ✅ Merged | [#2](https://github.com/onurburak9/campbuddy/pull/2) |
| M3 | Notifications — email + Telegram | ✅ Merged | [#3](https://github.com/onurburak9/campbuddy/pull/3) |
| M4 | Booking sidecar — Playwright service + client | ✅ Merged | [#4](https://github.com/onurburak9/campbuddy/pull/4) |
| M5 | Runner + Scheduler — full scan cycle | ✅ Merged | [#5](https://github.com/onurburak9/campbuddy/pull/5) |
| M6 | CLI + Deployment — Docker Compose, scans.yaml | ✅ Merged | [#6](https://github.com/onurburak9/campbuddy/pull/6) |

**Phase 1 complete.** 47 tests passing, **96% overall coverage**. All module targets exceeded.

## What you can run locally today (after M1 + M2)

You can verify the foundation, exercise the database, run all unit tests, and hit the real Recreation.gov API through camply. You **cannot** yet run the scheduler, send notifications, or use the CLI — those are M3/M5/M6.

### One-time setup

```bash
git clone https://github.com/onurburak9/campbuddy
cd campbuddy

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Why a venv: camply 0.34.1 requires pydantic v1, which conflicts with most modern Python projects' pydantic v2. The venv keeps things isolated. See `docs/adr/005-pydantic-v1.md`.

### 1. Run the test suite

```bash
pytest tests/ -v
```

Expected: **24 passed**. Covers models (cascade deletes, rollback semantics, defaults), settings (env loading, Fernet key validation, lru_cache), crypto (encrypt/decrypt round-trip, wrong-key detection), and availability (provider lookup, multi-window, error guards).

### 2. Coverage report

```bash
pytest tests/ --cov=core --cov=db --cov=config --cov-report=term-missing
```

Expected: **100% on every shipped module** (`config/settings.py`, `core/crypto.py`, `core/availability.py`, `db/models.py`, `db/session.py`).

### 3. Hit the real Recreation.gov API

```bash
python poc_search.py
```

This is the live integration smoke test. It searches rec areas 1076 (Stanislaus NF) and 2991 (Eldorado NF) for July 3–6, 2026, 3 nights. Currently returns ~21 available campsites with their names, types, dates, and direct booking URLs.

You can edit `poc_search.py` to try different rec area IDs, dates, or nights — useful for finding rec area IDs to put in `scans.yaml` once M6 ships.

### 4. Exercise the database directly (optional)

```bash
python -c "
from db.session import make_engine, create_tables, make_session_factory, get_db
from db.models import User, Scan, ScanStatus
from core.crypto import encrypt_password
from cryptography.fernet import Fernet

key = Fernet.generate_key().decode()
engine = make_engine('sqlite:///./data/test.db')
create_tables(engine)
factory = make_session_factory(engine)

with get_db(factory) as db:
    user = User(
        email='you@example.com',
        recreationgov_email='you@example.com',
        recreationgov_password=encrypt_password('hunter2', key),
    )
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        rec_area_ids=[1076],
        search_windows=[{'start_date': '2026-07-03', 'end_date': '2026-07-06'}],
        nights=3,
    )
    db.add(scan)

print('OK — DB created at data/test.db')
"
rm data/test.db   # cleanup
```

This proves the schema, encryption, and session lifecycle work end-to-end. The actual `seed`/`list-scans`/`pause` CLI commands ship with M6.

## What's coming next (M3 → M6)

Each milestone builds on the previous and is independently mergeable.

- **M3 — Notifications** (`core/notifier.py`): SMTP email + Telegram bot dispatch with the booking URL in plain text. Adds a `test-notify` CLI stub for live channel verification.
- **M4 — Booking sidecar** (`playwright_service/`): isolated FastAPI + headless Chromium container that logs into Recreation.gov and adds a campsite to cart. The app talks to it via `core/booking.py` over HTTP.
- **M5 — Runner + Scheduler** (`core/runner.py`, `core/scheduler.py`): the heart of the system. APScheduler fires per-scan jobs that call availability → cart-add → notify, writing every run to `scan_runs` and every found site to `scan_results`. Includes the end-to-end integration test.
- **M6 — CLI + Deployment**: full `cli.py` (seed/list/pause/resume/delete/test-notify), `main.py` entry point, `Dockerfile`, full `docker-compose.yml`, `config/scans.yaml` with realistic examples.

After M6 you'll be able to: edit `scans.yaml`, `python cli.py seed`, `docker compose up -d`, and start receiving cancellation alerts.

## Decisions worth knowing

- **pydantic v1 only** (ADR 005) — camply pins it. All settings use `from pydantic import BaseSettings`, NOT `pydantic-settings`. The project venv keeps this isolated.
- **Timezone-aware datetimes everywhere** — `datetime.now(timezone.utc)`, never `datetime.utcnow()`. Otherwise APScheduler comparisons crash at runtime.
- **Cart-add failure is non-fatal** (ADR 004) — the user is always notified with the booking URL even if Playwright can't add to cart.
- **Playwright runs in its own container** (ADR 002) — Chromium crashes don't kill the scheduler.
- **SQLite for now** (ADR 003) — single-process, low-volume; migrate to Postgres later by changing `DATABASE_URL`.

## Open items / followups

- camply 0.34.1 logs verbosely via `rich`. May want to suppress this in M5 once the runner is wired up.
- `recreationgov_password` column is `String(256)` — Fernet ciphertext fits comfortably, but worth re-checking if password lengths grow.
- `days_of_week` uses Python's `weekday()` convention (0=Mon, 6=Sun) — documented in CLAUDE.md and the model column comment, but no validation at the boundary yet. Consider adding when M6 ships and YAML is the input source.
