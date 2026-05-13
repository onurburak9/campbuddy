# CampBuddy

Self-hosted campsite availability monitor. Polls campground systems via camply, adds available sites to cart via Playwright, notifies users via email and Telegram.

## Quick Start

```bash
# 1. Set up virtual environment (camply requires pydantic v1 — keep deps isolated)
python3 -m venv .venv
source .venv/bin/activate          # or use .venv/bin/<command> directly

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Generate ENCRYPTION_KEY and edit .env:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 4. Seed scans and run
mkdir -p data
python cli.py seed config/scans.yaml
python main.py
```

## Why a venv

camply 0.34.1 pins pydantic v1, which is incompatible with most modern Python projects (which use v2). The `.venv` keeps CampBuddy's dependencies isolated. Always activate it before running tests, CLI commands, or main.py.

## Key Commands

All commands assume the venv is active OR you prefix with `.venv/bin/`.

```bash
# Testing
pytest tests/ -v                                                  # run all tests
pytest tests/ --cov=core --cov=db --cov-report=term-missing      # with coverage

# Scan management
python cli.py seed config/scans.yaml    # create users + scans from YAML
python cli.py list-scans                # show all scans and status
python cli.py pause <id>                # pause a scan
python cli.py resume <id>               # resume a paused scan
python cli.py delete-scan <id>          # delete scan + all history
python cli.py test-notify <scan_id>     # send a test notification

# Docker
docker compose build
docker compose up -d
docker compose logs -f app
docker compose down
```

## Directory Structure

```
core/           — availability, booking, crypto, notifier, runner, scheduler
db/             — SQLAlchemy models and session factory
config/         — settings (pydantic v1 BaseSettings) and scans.yaml
playwright_service/ — isolated Playwright FastAPI sidecar
tests/          — mirrors core/ and db/ structure
docs/adr/       — architecture decision records
docs/superpowers/ — design specs and implementation plans
cli.py          — CLI entry point (click)
main.py         — scheduler entry point
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENCRYPTION_KEY` | yes | Fernet key for encrypting Recreation.gov passwords |
| `SMTP_HOST` | no | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | no | SMTP port (default: 587) |
| `SMTP_USER` | yes | SMTP login |
| `SMTP_PASSWORD` | yes | SMTP password / app password |
| `SMTP_FROM` | yes | From address shown in emails |
| `TELEGRAM_BOT_TOKEN` | no | Bot token from @BotFather; leave empty to disable |
| `PLAYWRIGHT_SERVICE_URL` | no | Internal URL of Playwright sidecar (default: http://playwright:8001) |
| `DATABASE_URL` | no | SQLite path (default: sqlite:///./data/campbuddy.db) |

## Testing Conventions

- Use `pytest` + `pytest-mock` (already in requirements)
- Mock all external I/O: camply, httpx, smtplib, requests (Telegram)
- Use in-memory SQLite for all DB tests (`sqlite:///:memory:`)
- No test may make real network calls
- Tests live in `tests/` mirroring `core/` and `db/`
- Always run with the venv: `.venv/bin/pytest` or activate first

## Code Conventions

- No comments unless the WHY is non-obvious (a constraint, a workaround, a surprising invariant)
- No docstrings on obvious functions
- DB session always via `get_db()` context manager — never share a Session across threads
- Each file has one responsibility — if it grows past ~150 lines, consider splitting
- Timezone-aware datetimes everywhere (`datetime.now(timezone.utc)`, never `datetime.utcnow()`)

## Adding a New Campground Provider

1. Find the camply search class (e.g. `SearchReserveCalifornia`) in `camply.search`
2. Add it to `PROVIDER_MAP` in `core/availability.py`
3. Add a test in `tests/test_availability.py` asserting the new provider name routes correctly
4. Update the provider table in `ARCHITECTURE.md`

## Schema Changes (Alembic)

Every change to `db/models.py` must be accompanied by a migration file in the same commit/PR. The CI `migrations` workflow enforces this by running `alembic check`, which fails if the models have drifted from the applied migrations.

### Adding a column or table

```bash
# 1. Edit db/models.py
# 2. Generate the migration
alembic revision --autogenerate -m "add <description>"
# 3. Review the generated file in migrations/versions/
# 4. Commit both files together
```

### Verifying locally

```bash
# Apply all migrations to a blank database
mkdir -p data
DATABASE_URL="sqlite:///./data/campbuddy.db" alembic upgrade head

# Confirm no drift between models and migrations
DATABASE_URL="sqlite:///./data/campbuddy.db" alembic check
```

### What CI checks

- `alembic upgrade head` — migrations apply cleanly to a blank database
- `alembic check` — no schema drift (catches `db/models.py` changes without a matching migration)

A PR that modifies `db/models.py` without a new migration file will fail the `alembic check` step.

## Architecture

See `ARCHITECTURE.md` for component diagram, data flow, and ADR links.
