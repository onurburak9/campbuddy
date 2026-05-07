# CampBuddy Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core campsite monitoring engine — camply-powered availability scanning, Playwright add-to-cart automation, email + Telegram notifications, full run history in SQLite, CLI-managed via YAML config, deployed via Docker Compose on a VPS.

**Architecture:** APScheduler fires periodic jobs per scan config. Each job calls camply's OO API for availability, attempts Playwright add-to-cart via an isolated sidecar container, and dispatches notifications. All results written to SQLite regardless of outcome. A living documentation network (CLAUDE.md, ARCHITECTURE.md, ADRs) is maintained alongside the code.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, APScheduler 3.x, camply 0.34+, Playwright sidecar (FastAPI), httpx, cryptography (Fernet), pydantic-settings, click, pytest, pytest-cov, pytest-mock, respx

---

## Milestone Overview

| # | Branch | PR Title | Deliverable | Passes when |
|---|--------|----------|-------------|-------------|
| M1 | `feat/m1-foundation` | Foundation: models, crypto, settings, docs | Project scaffold, DB schema, Fernet crypto, full doc network | `pytest tests/` green; ARCHITECTURE.md + CLAUDE.md exist |
| M2 | `feat/m2-availability` | Availability: camply OO wrapper | camply wrapper tested and live-verified | `pytest tests/` green; POC search returns real data |
| M3 | `feat/m3-notifications` | Notifications: email + Telegram | Email + Telegram dispatch, CLI test command | `pytest tests/` green; test notification delivered |
| M4 | `feat/m4-booking-sidecar` | Booking: Playwright sidecar + client | Playwright service runs, booking client tested | Service health check passes; `pytest tests/` green |
| M5 | `feat/m5-runner-scheduler` | Core: scan runner + scheduler | Full scan cycle runs end-to-end | Integration test passes; coverage ≥80% on runner |
| M6 | `feat/m6-cli-deploy` | Deploy: CLI, Docker Compose, README | Seeded scans fire on VPS via Docker Compose | `docker compose up` runs; scans execute and notify |

---

## Document Network

These files are created in M1 and updated in every subsequent PR.

```
campbuddy/
├── CLAUDE.md               # AI agent context: commands, conventions, structure
├── AGENTS.md               # symlink → CLAUDE.md
├── ARCHITECTURE.md         # system overview, data flow, component map, ADR links
├── README.md               # human-facing: setup, config, deployment
└── docs/
    ├── adr/
    │   ├── 001-camply-as-engine.md
    │   ├── 002-playwright-sidecar.md
    │   ├── 003-sqlite-first.md
    │   └── 004-notify-on-cart-failure.md
    └── superpowers/
        ├── specs/2026-05-06-campbuddy-design.md
        └── plans/2026-05-06-campbuddy-phase1.md   ← this file
```

**Update rule:** Every PR that adds a component must update ARCHITECTURE.md to reflect it. CLAUDE.md is updated when commands, conventions, or extension points change.

---

## Full File Map

```
campbuddy/
├── config/
│   ├── settings.py
│   └── scans.yaml
├── core/
│   ├── __init__.py
│   ├── availability.py
│   ├── booking.py
│   ├── crypto.py
│   ├── notifier.py
│   ├── runner.py
│   └── scheduler.py
├── db/
│   ├── __init__.py
│   ├── models.py
│   └── session.py
├── playwright_service/
│   ├── __init__.py
│   ├── browser.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_crypto.py
│   ├── test_settings.py
│   ├── test_availability.py
│   ├── test_notifier.py
│   ├── test_booking.py
│   ├── test_runner.py
│   ├── test_scheduler.py
│   └── test_integration.py
├── cli.py
├── main.py
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
├── CLAUDE.md
├── AGENTS.md               ← symlink to CLAUDE.md
├── ARCHITECTURE.md
└── README.md
```

---

## Coverage Targets

| Module | Target | Notes |
|--------|--------|-------|
| `core/runner.py` | ≥85% | Most critical path |
| `core/availability.py` | ≥85% | Camply integration |
| `core/notifier.py` | ≥80% | Both channels |
| `core/booking.py` | ≥80% | All HTTP outcomes |
| `core/crypto.py` | 100% | Small, fully testable |
| `db/models.py` | ≥75% | CRUD coverage |
| `db/session.py` | ≥75% | |
| `core/scheduler.py` | ≥70% | |
| `playwright_service/browser.py` | excluded | Live browser only |
| `cli.py` | ≥60% | Smoke tested |

Run: `pytest tests/ --cov=. --cov-report=term-missing --ignore=playwright_service/browser.py`

---

---

# M1: Foundation

**Branch:** `feat/m1-foundation`
**PR title:** `feat: project foundation — models, crypto, settings, doc network`

### Deliverables
- Project installs and `pytest tests/` passes (all green)
- SQLite schema creates cleanly with `python -c "from db.session import *; ..."`
- Fernet encrypt/decrypt roundtrip verified
- `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `README.md` all exist with real content
- Four ADRs committed to `docs/adr/`

### PR Merge Checklist
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `pytest tests/ -v` — all tests pass
- [ ] `pytest tests/ --cov=core --cov=db --cov-report=term-missing` — crypto 100%, models ≥75%
- [ ] `CLAUDE.md` has project commands and conventions
- [ ] `ARCHITECTURE.md` describes all six components even if not yet built
- [ ] All four ADRs exist in `docs/adr/`

---

### Task 1.1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `playwright_service/requirements.txt`
- Create: `.env.example`
- Create: all `__init__.py` files

- [ ] **Step 1: Create `requirements.txt`**

```
camply==0.34.1
sqlalchemy==2.0.30
apscheduler==3.10.4
httpx==0.27.0
cryptography==42.0.5
pydantic-settings==2.2.1
pyyaml==6.0.1
click==8.1.7
requests==2.31.0
pytest==8.2.0
pytest-mock==3.14.0
pytest-cov==5.0.0
respx==0.21.1
```

- [ ] **Step 2: Create `playwright_service/requirements.txt`**

```
playwright==1.44.0
fastapi==0.111.0
uvicorn==0.29.0
```

- [ ] **Step 3: Create `.env.example`**

```
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key-here

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=CampBuddy <you@gmail.com>

# Leave empty to disable Telegram
TELEGRAM_BOT_TOKEN=

PLAYWRIGHT_SERVICE_URL=http://playwright:8001
DATABASE_URL=sqlite:///./data/campbuddy.db
```

- [ ] **Step 4: Create `__init__.py` files**

```bash
touch tests/__init__.py core/__init__.py db/__init__.py config/__init__.py playwright_service/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt playwright_service/requirements.txt .env.example tests/__init__.py core/__init__.py db/__init__.py config/__init__.py playwright_service/__init__.py
git commit -m "feat(m1): project scaffold and dependencies"
```

---

### Task 1.2: Settings Module

**Files:**
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_settings.py`:

```python
import pytest
from config.settings import Settings


def test_loads_required_fields(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.smtp_user == "test@example.com"
    assert s.database_url == "sqlite:///./data/campbuddy.db"
    assert s.playwright_service_url == "http://playwright:8001"


def test_telegram_defaults_empty(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == ""
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_settings.py -v
```

Expected: `ModuleNotFoundError: No module named 'config.settings'`

- [ ] **Step 3: Implement `config/settings.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    encryption_key: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str
    telegram_bot_token: str = ""
    playwright_service_url: str = "http://playwright:8001"
    database_url: str = "sqlite:///./data/campbuddy.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_settings.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add config/settings.py config/__init__.py tests/test_settings.py
git commit -m "feat(m1): settings module"
```

---

### Task 1.3: Database Models and Session

**Files:**
- Create: `db/models.py`
- Create: `db/session.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Base, User, Scan, ScanRun, ScanResult


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_user_created_with_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.created_at is not None
    assert user.telegram_chat_id is None


def test_scan_created_with_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.commit()
    assert scan.id is not None
    assert scan.status == "active"
    assert scan.nights == 1
    assert scan.provider == "RecreationDotGov"


def test_scan_run_always_writable(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.flush()
    for outcome in ["success", "no_results", "error"]:
        run = ScanRun(
            scan_id=scan.id,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            outcome=outcome,
            sites_found=0,
        )
        db.add(run)
    db.commit()
    runs = db.query(ScanRun).filter(ScanRun.scan_id == scan.id).all()
    assert len(runs) == 3


def test_scan_result_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.flush()
    run = ScanRun(
        scan_id=scan.id,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        outcome="success",
        sites_found=1,
    )
    db.add(run)
    db.flush()
    result = ScanResult(
        scan_run_id=run.id,
        scan_id=scan.id,
        campsite_id="10357088",
        facility_name="Union West",
        site_name="1",
        campsite_type="STANDARD NONELECTRIC",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://www.recreation.gov/camping/campsites/10357088",
        first_seen_at=datetime.utcnow(),
    )
    db.add(result)
    db.commit()
    assert result.id is not None
    assert result.cart_added is False
    assert result.notified is False
    assert result.cart_added_at is None


def test_session_factory_get_db():
    from sqlalchemy import create_engine
    from db.session import make_engine, create_tables, make_session_factory, get_db
    engine = make_engine("sqlite:///:memory:")
    create_tables(engine)
    factory = make_session_factory(engine)
    with get_db(factory) as db:
        user = User(email="session_test@example.com")
        db.add(user)
    with get_db(factory) as db:
        found = db.query(User).filter(User.email == "session_test@example.com").first()
        assert found is not None
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'db.models'`

- [ ] **Step 3: Implement `db/models.py`**

```python
from datetime import datetime, date
from typing import Optional
from sqlalchemy import JSON, DateTime, Boolean, Integer, String, ForeignKey, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="RecreationDotGov")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    polling_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    rec_area_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    campground_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    campsite_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    search_windows: Mapped[list] = mapped_column(JSON, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    days_of_week: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    weekends_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_via_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_via_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_on_new_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="scans")
    runs: Mapped[list["ScanRun"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scans.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sites_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="runs")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="run")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scans.id"), nullable=False)
    campsite_id: Mapped[str] = mapped_column(String, nullable=False)
    facility_name: Mapped[str] = mapped_column(String, nullable=False)
    site_name: Mapped[str] = mapped_column(String, nullable=False)
    campsite_type: Mapped[str] = mapped_column(String, nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_url: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cart_added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cart_added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    run: Mapped["ScanRun"] = relationship(back_populates="results")
    scan: Mapped["Scan"] = relationship(back_populates="results")
```

- [ ] **Step 4: Implement `db/session.py`**

```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from db.models import Base


def make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db(session_factory):
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 5: Run — expect pass**

```bash
pytest tests/test_models.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add db/models.py db/session.py db/__init__.py tests/test_models.py
git commit -m "feat(m1): SQLAlchemy models and session factory"
```

---

### Task 1.4: Crypto Helpers

**Files:**
- Create: `core/crypto.py`
- Create: `tests/test_crypto.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_crypto.py`:

```python
import pytest
from cryptography.fernet import Fernet
from core.crypto import encrypt_password, decrypt_password


def test_roundtrip():
    key = Fernet.generate_key().decode()
    assert decrypt_password(encrypt_password("s3cr3t!", key), key) == "s3cr3t!"


def test_ciphertext_differs_each_call():
    key = Fernet.generate_key().decode()
    assert encrypt_password("same", key) != encrypt_password("same", key)


def test_wrong_key_raises():
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    with pytest.raises(Exception):
        decrypt_password(encrypt_password("secret", key1), key2)


def test_encrypted_is_string():
    key = Fernet.generate_key().decode()
    result = encrypt_password("password", key)
    assert isinstance(result, str)
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_crypto.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.crypto'`

- [ ] **Step 3: Implement `core/crypto.py`**

```python
from cryptography.fernet import Fernet


def encrypt_password(plaintext: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(plaintext.encode()).decode()


def decrypt_password(encrypted: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(encrypted.encode()).decode()
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_crypto.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Check coverage**

```bash
pytest tests/test_crypto.py --cov=core/crypto --cov-report=term-missing
```

Expected: 100% coverage on `core/crypto.py`.

- [ ] **Step 6: Commit**

```bash
git add core/crypto.py core/__init__.py tests/test_crypto.py
git commit -m "feat(m1): Fernet encrypt/decrypt helpers"
```

---

### Task 1.5: CLAUDE.md + AGENTS.md

**Files:**
- Create: `CLAUDE.md`
- Create: `AGENTS.md` (symlink)

- [ ] **Step 1: Create `CLAUDE.md`**

```markdown
# CampBuddy

Self-hosted campsite availability monitor. Polls campground systems via camply, adds available sites to cart via Playwright, notifies users via email and Telegram.

## Quick Start

```bash
cp .env.example .env
# Fill in ENCRYPTION_KEY, SMTP_*, optionally TELEGRAM_BOT_TOKEN
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # generate key

pip install -r requirements.txt
mkdir -p data
python cli.py seed config/scans.yaml   # seed DB from YAML config
python main.py                          # start scheduler
```

## Key Commands

```bash
# Testing
pytest tests/ -v                                                  # run all tests
pytest tests/ --cov=. --cov-report=term-missing \
  --ignore=playwright_service/browser.py                         # with coverage

# Scan management
python cli.py seed config/scans.yaml    # create users + scans from YAML
python cli.py list-scans                # show all scans and status
python cli.py pause <id>                # pause a scan
python cli.py resume <id>               # resume a paused scan
python cli.py delete-scan <id>          # delete scan + all history
python cli.py test-notify <scan_id>     # send a test notification for a scan

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
config/         — pydantic-settings (settings.py) and scans.yaml
playwright_service/ — isolated Playwright FastAPI sidecar
tests/          — mirrors core/ and db/ structure
cli.py          — CLI entry point (click)
main.py         — scheduler entry point
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENCRYPTION_KEY` | yes | Fernet key for encrypting Recreation.gov passwords |
| `SMTP_HOST` | yes | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | yes | SMTP port (default: 587) |
| `SMTP_USER` | yes | SMTP login |
| `SMTP_PASSWORD` | yes | SMTP password / app password |
| `SMTP_FROM` | yes | From address shown in emails |
| `TELEGRAM_BOT_TOKEN` | no | Bot token from @BotFather; leave empty to disable |
| `PLAYWRIGHT_SERVICE_URL` | yes | Internal URL of Playwright sidecar (default: http://playwright:8001) |
| `DATABASE_URL` | yes | SQLite path (default: sqlite:///./data/campbuddy.db) |

## Testing Conventions

- Use `pytest` + `pytest-mock`
- Mock all external I/O: camply, httpx, smtplib, requests (Telegram)
- Use in-memory SQLite for all DB tests (`sqlite:///:memory:`)
- No test may make real network calls
- Tests live in `tests/` mirroring `core/` and `db/`

## Code Conventions

- No comments unless the WHY is non-obvious (a constraint, a workaround, a surprising invariant)
- No docstrings on obvious functions
- DB session always via `get_db()` context manager — never share a Session across threads
- Each file has one responsibility — if it grows past ~150 lines, consider splitting

## Adding a New Campground Provider

1. Find the camply search class (e.g. `SearchReserveCalifornia`) in `camply.search`
2. Add it to `PROVIDER_MAP` in `core/availability.py`
3. Add a test in `tests/test_availability.py` asserting the new provider name routes correctly
4. Update the provider table in `ARCHITECTURE.md`

## Architecture

See `ARCHITECTURE.md` for component diagram, data flow, and ADR links.
```

- [ ] **Step 2: Create `AGENTS.md` as a symlink**

```bash
ln -s CLAUDE.md AGENTS.md
```

- [ ] **Step 3: Verify symlink works**

```bash
diff CLAUDE.md AGENTS.md
```

Expected: no output (files are identical via symlink).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "docs(m1): CLAUDE.md and AGENTS.md symlink"
```

---

### Task 1.6: ARCHITECTURE.md

**Files:**
- Create: `ARCHITECTURE.md`

- [ ] **Step 1: Create `ARCHITECTURE.md`**

```markdown
# CampBuddy Architecture

## System Overview

CampBuddy is a single-process Python service that monitors campground availability and automates the booking flow on behalf of users.

```
┌─────────────────────────────────────────────────────────┐
│                        VPS                              │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  app container                                   │  │
│  │                                                  │  │
│  │  ┌────────────┐    ┌─────────────┐               │  │
│  │  │ APScheduler│───▶│   Runner    │               │  │
│  │  │  (jobs)    │    │  (per scan) │               │  │
│  │  └────────────┘    └──────┬──────┘               │  │
│  │                           │                      │  │
│  │              ┌────────────┼────────────┐         │  │
│  │              ▼            ▼            ▼         │  │
│  │        ┌──────────┐ ┌─────────┐ ┌──────────┐    │  │
│  │        │ camply   │ │ Booking │ │ Notifier │    │  │
│  │        │ (avail.) │ │ Client  │ │ (email + │    │  │
│  │        └──────────┘ └────┬────┘ │ telegram)│    │  │
│  │                          │      └──────────┘    │  │
│  │        ┌─────────────────┘                      │  │
│  │        ▼                                         │  │
│  │  ┌──────────┐    SQLite                          │  │
│  │  │Playwright│    campbuddy.db                    │  │
│  │  │ sidecar  │    (mounted volume)                │  │
│  │  └──────────┘                                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Components

### APScheduler (`core/scheduler.py`)
Runs one background job per active scan, firing at each scan's `polling_interval`. Also runs a 60-second sync job that adds/removes jobs when scan statuses change.

### Runner (`core/runner.py`)
Executes a single scan end-to-end:
1. Calls availability checker
2. Writes `scan_run` record (always, regardless of outcome)
3. For each new site: saves result, calls booking sidecar, sends notifications

### Availability Checker (`core/availability.py`)
Thin wrapper around camply's OO API. Converts scan DB record → `SearchRecreationDotGov` call → returns `list[AvailableCampsite]`. Provider is looked up from `PROVIDER_MAP`.

### Booking Client (`core/booking.py`)
HTTP client (httpx) that POSTs to the Playwright sidecar's `/add-to-cart` endpoint. Returns `True`/`False`. Failures are non-fatal — user is always notified with booking URL.

### Notifier (`core/notifier.py`)
Dispatches email (smtplib/SMTP) and Telegram (Bot API via requests) based on per-scan preferences. Booking URL is always included in plain text.

### Playwright Sidecar (`playwright_service/`)
Isolated FastAPI service in its own Docker container. Receives `POST /add-to-cart { booking_url, email, password }`, drives headless Chromium to log in and add the site to cart, returns `{ success, error }`. Runs separately so a browser crash cannot kill the scheduler.

### Crypto (`core/crypto.py`)
Fernet (AES-128-CBC + HMAC) encrypt/decrypt for Recreation.gov passwords. Key lives in `ENCRYPTION_KEY` env var.

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
            → booking.attempt_cart_add(url, email, password)
                → POST playwright_service /add-to-cart
            → notifier.notify(scan, payload)
                → send_email() and/or send_telegram()
            → update ScanResult(cart_added, notified, timestamps)
        → commit
```

## Database Schema

```
users
  id, email, telegram_chat_id, recreationgov_email, recreationgov_password (Fernet), created_at

scans
  id, user_id→users, provider, status, polling_interval
  rec_area_ids (JSON), campground_ids (JSON), campsite_ids (JSON)
  search_windows (JSON), nights, days_of_week (JSON), weekends_only
  notify_via_email, notify_via_telegram, notify_on_new_only
  created_at

scan_runs                          ← always written, every execution
  id, scan_id→scans, started_at, finished_at
  outcome (success|no_results|error), sites_found, error_message

scan_results                       ← one row per available site per run
  id, scan_run_id→scan_runs, scan_id→scans
  campsite_id, facility_name, site_name, campsite_type
  booking_date, booking_end_date, booking_url
  first_seen_at, cart_added, cart_added_at, notified, notified_at
```

## Supported Providers

| Provider key | camply class | Notes |
|---|---|---|
| `RecreationDotGov` | `SearchRecreationDotGov` | Default. Uses unofficial availability API. |

To add a provider: see "Adding a New Campground Provider" in CLAUDE.md.

## Deployment

Two Docker containers, `docker-compose.yml`:
- `app` — Python service (scheduler + runner + notifier)
- `playwright` — Playwright sidecar (FastAPI, port 8001 internal only)

SQLite database mounted at `./data/campbuddy.db`. Back up this file.

## Phased Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 — Core engine | 🔨 In progress | This plan |
| 2 — Web dashboard | Planned | FastAPI + HTMX, manage scans via browser |
| 3 — Telegram bot | Planned | Create/manage scans via Telegram commands |

## Architecture Decision Records

- [ADR 001](docs/adr/001-camply-as-engine.md) — Use camply as availability engine
- [ADR 002](docs/adr/002-playwright-sidecar.md) — Playwright in isolated Docker sidecar
- [ADR 003](docs/adr/003-sqlite-first.md) — SQLite for Phase 1
- [ADR 004](docs/adr/004-notify-on-cart-failure.md) — Notify even when cart add fails
```

- [ ] **Step 2: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs(m1): ARCHITECTURE.md — system overview, components, data flow"
```

---

### Task 1.7: Architecture Decision Records

**Files:**
- Create: `docs/adr/001-camply-as-engine.md`
- Create: `docs/adr/002-playwright-sidecar.md`
- Create: `docs/adr/003-sqlite-first.md`
- Create: `docs/adr/004-notify-on-cart-failure.md`

- [ ] **Step 1: Create `docs/adr/001-camply-as-engine.md`**

```markdown
# ADR 001: Use camply as the availability engine

**Date:** 2026-05-06  
**Status:** Accepted

## Context
We need to check campsite availability across 20+ providers (Recreation.gov, ReserveCalifornia, GoingToCamp, state parks). Building provider-specific scrapers from scratch would take weeks and require ongoing maintenance as provider UIs change.

## Decision
Use [camply](https://github.com/juftin/camply) as a Python library via its OO API (`SearchRecreationDotGov(...).get_matching_campsites(continuous=False)`). We call it in single-check mode from our own scheduler rather than using its built-in continuous loop.

## Consequences
- 20+ providers work immediately with no additional code
- We are coupled to camply's versioning and API stability
- camply's internal logging/display output (rich) appears in our logs — acceptable
- We cannot use camply's built-in notifications (they conflict with our per-user dispatch logic)
- Adding a new provider is a one-line change in `PROVIDER_MAP`
```

- [ ] **Step 2: Create `docs/adr/002-playwright-sidecar.md`**

```markdown
# ADR 002: Playwright in isolated Docker sidecar

**Date:** 2026-05-06  
**Status:** Accepted

## Context
Booking automation requires driving a headless browser (Playwright/Chromium). Chromium is memory-heavy (~300MB), crashes unpredictably, and has a different update cadence from the Python app.

## Decision
Run Playwright as a separate Docker container exposing an internal HTTP API (`POST /add-to-cart`). The app container calls it via httpx. The sidecar never exposes ports outside the Docker network.

## Consequences
- A Chromium crash cannot kill the APScheduler process or corrupt the DB
- Playwright and its browser can be updated independently
- Adds Docker Compose complexity (two services instead of one)
- The app must handle sidecar unavailability gracefully (non-fatal — falls back to notify-only)
```

- [ ] **Step 3: Create `docs/adr/003-sqlite-first.md`**

```markdown
# ADR 003: SQLite for Phase 1

**Date:** 2026-05-06  
**Status:** Accepted

## Context
We need persistent storage for users, scans, run history, and results. The service is single-process with no concurrent writers. User count is small (< 20 initially).

## Decision
Use SQLite with SQLAlchemy ORM. Database file mounted as a Docker volume at `./data/campbuddy.db`.

## Consequences
- Zero configuration, no separate DB container
- SQLAlchemy ORM means migration to PostgreSQL (Phase 2+) requires only changing `DATABASE_URL`
- `check_same_thread=False` needed for APScheduler's thread pool — safe because SQLAlchemy sessions are per-thread
- Must back up `campbuddy.db` file manually or via cron on the VPS
```

- [ ] **Step 4: Create `docs/adr/004-notify-on-cart-failure.md`**

```markdown
# ADR 004: Notify even when cart add fails

**Date:** 2026-05-06  
**Status:** Accepted

## Context
Playwright add-to-cart can fail for many reasons: bot detection, Recreation.gov UI changes, session timeout, login issues. Campsite windows close in minutes. If we only notify on successful cart add, a Playwright failure means the user never learns about availability.

## Decision
Always send a notification when a campsite is found, regardless of cart add outcome. The message indicates cart status and always includes the direct booking URL so the user can act manually.

## Consequences
- User is always informed, even when automation fails
- Playwright reliability is not critical-path — degraded gracefully
- Slightly noisier messages when cart add fails (mitigated by clear status line)
```

- [ ] **Step 5: Commit**

```bash
mkdir -p docs/adr
git add docs/adr/
git commit -m "docs(m1): architecture decision records (ADR 001–004)"
```

---

### Task 1.8: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# CampBuddy

Self-hosted campsite availability monitor. Watches for cancellations across Recreation.gov, ReserveCalifornia, and 20+ other providers, adds available sites to cart, and notifies you via email or Telegram.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for deployment)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (recommended for SMTP)
- Optional: a Telegram bot token from [@BotFather](https://t.me/botfather)

## Setup (local)

```bash
git clone <repo>
cd campbuddy
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in ENCRYPTION_KEY, SMTP_*, optionally TELEGRAM_BOT_TOKEN
# Generate ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

mkdir -p data
python cli.py seed config/scans.yaml
python main.py
```

## Configuration

Edit `config/scans.yaml` to define users and scans:

```yaml
users:
  - email: you@example.com
    telegram_chat_id: "123456789"
    recreationgov_email: you@example.com
    recreationgov_password: your-plaintext-password   # encrypted at seed time

scans:
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 300          # check every 5 minutes
    rec_area_ids: [1076, 2991]
    search_windows:
      - start_date: "2026-07-03"
        end_date: "2026-07-06"
    nights: 3
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true       # suppress repeat alerts for same site+date
```

Re-seed after changes: `python cli.py seed config/scans.yaml`

## Deployment (VPS via Docker Compose)

```bash
# On your VPS
git clone <repo> && cd campbuddy
cp .env.example .env && vim .env
mkdir -p data
python cli.py seed config/scans.yaml
docker compose up -d
docker compose logs -f
```

## Managing Scans

```bash
python cli.py list-scans          # show all scans
python cli.py pause <id>          # pause without deleting
python cli.py resume <id>         # re-activate
python cli.py delete-scan <id>    # remove scan + all history
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design, data flow, and component descriptions.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(m1): README with setup and deployment guide"
```

---

### M1 PR

- [ ] **Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Run coverage check**

```bash
pytest tests/ --cov=core --cov=db --cov-report=term-missing
```

Expected: `core/crypto.py` at 100%, `db/models.py` ≥75%.

- [ ] **Create PR**

```bash
git push origin feat/m1-foundation
gh pr create \
  --title "feat: project foundation — models, crypto, settings, doc network" \
  --base main \
  --body "## M1: Foundation

### What's in this PR
- Project scaffold: requirements, __init__ files, .env.example
- pydantic-settings config module
- SQLAlchemy 2.0 ORM models: User, Scan, ScanRun, ScanResult
- Fernet crypto helpers (encrypt/decrypt Recreation.gov passwords)
- CLAUDE.md + AGENTS.md (symlink) — AI agent context and key commands
- ARCHITECTURE.md — full system overview, component map, data flow
- README.md — setup, configuration, deployment guide
- ADRs 001–004 in docs/adr/

### Test coverage
- core/crypto.py: 100%
- db/models.py + session.py: ≥75%

### Verify
\`\`\`bash
pip install -r requirements.txt
pytest tests/ -v
\`\`\`"
```

---

---

# M2: Availability Engine

**Branch:** `feat/m2-availability`
**PR title:** `feat: availability wrapper — camply OO API integration`

### Deliverables
- `core/availability.py` wraps camply for any configured provider
- 4 unit tests pass (mocked camply)
- Live smoke test: real Recreation.gov data returned from POC command
- ARCHITECTURE.md provider table updated

### PR Merge Checklist
- [ ] `pytest tests/test_availability.py -v` — 4 passed
- [ ] `pytest tests/ --cov=core/availability --cov-report=term-missing` — ≥85%
- [ ] Live smoke: `python poc_search.py` returns ≥1 result
- [ ] ARCHITECTURE.md provider table reflects `RecreationDotGov`

---

### Task 2.1: Availability Wrapper

**Files:**
- Create: `core/availability.py`
- Create: `tests/test_availability.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_availability.py`:

```python
import pytest
from datetime import date
from unittest.mock import MagicMock
from core.availability import check_availability


def make_scan(**overrides):
    scan = MagicMock()
    scan.provider = "RecreationDotGov"
    scan.rec_area_ids = [1076]
    scan.campground_ids = None
    scan.campsite_ids = None
    scan.search_windows = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]
    scan.nights = 3
    scan.weekends_only = False
    scan.days_of_week = None
    for k, v in overrides.items():
        setattr(scan, k, v)
    return scan


def test_returns_matching_sites(mocker):
    mock_site = MagicMock()
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [mock_site]
    mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    result = check_availability(make_scan())

    assert result == [mock_site]
    mock_search.get_matching_campsites.assert_called_once_with(continuous=False)


def test_returns_empty_on_no_availability(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    assert check_availability(make_scan()) == []


def test_multiple_search_windows_passed(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    scan = make_scan(search_windows=[
        {"start_date": "2026-07-03", "end_date": "2026-07-06"},
        {"start_date": "2026-07-10", "end_date": "2026-07-13"},
    ])
    check_availability(scan)

    windows = mock_cls.call_args.kwargs["search_window"]
    assert len(windows) == 2


def test_unsupported_provider_raises(mocker):
    with pytest.raises(ValueError, match="Unsupported provider"):
        check_availability(make_scan(provider="UnknownProvider"))
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_availability.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.availability'`

- [ ] **Step 3: Implement `core/availability.py`**

```python
import logging
from datetime import date
from camply.containers import SearchWindow
from camply.search import SearchRecreationDotGov

logger = logging.getLogger(__name__)

PROVIDER_MAP = {
    "RecreationDotGov": SearchRecreationDotGov,
}


def check_availability(scan) -> list:
    cls = PROVIDER_MAP.get(scan.provider)
    if cls is None:
        raise ValueError(f"Unsupported provider: {scan.provider}")

    windows = [
        SearchWindow(
            start_date=date.fromisoformat(w["start_date"]),
            end_date=date.fromisoformat(w["end_date"]),
        )
        for w in scan.search_windows
    ]

    kwargs = dict(search_window=windows, nights=scan.nights, weekends_only=scan.weekends_only)
    if scan.rec_area_ids:
        kwargs["recreation_area"] = scan.rec_area_ids
    if scan.campground_ids:
        kwargs["campgrounds"] = scan.campground_ids
    if scan.campsite_ids:
        kwargs["campsites"] = scan.campsite_ids
    if scan.days_of_week:
        kwargs["days_of_the_week"] = scan.days_of_week

    sites = cls(**kwargs).get_matching_campsites(continuous=False)
    logger.info("Scan %s: %d site(s) found", getattr(scan, "id", "?"), len(sites))
    return sites
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_availability.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Coverage check**

```bash
pytest tests/test_availability.py --cov=core/availability --cov-report=term-missing
```

Expected: ≥85%.

- [ ] **Step 6: Live smoke test**

```bash
python poc_search.py
```

Expected: `Found N available campsite(s)` with real data. (Confirms camply integration works end-to-end.)

- [ ] **Step 7: Commit**

```bash
git add core/availability.py tests/test_availability.py
git commit -m "feat(m2): camply availability wrapper with provider map"
```

---

### M2 PR

- [ ] **Create PR**

```bash
git push origin feat/m2-availability
gh pr create \
  --title "feat: availability wrapper — camply OO API integration" \
  --base main \
  --body "## M2: Availability Engine

### What's in this PR
- core/availability.py: thin wrapper around camply OO API
- Converts Scan DB record → SearchWindow list → camply call → list[AvailableCampsite]
- PROVIDER_MAP for extensibility (add new providers in one line)
- 4 unit tests, all camply calls mocked

### Coverage
core/availability.py ≥85%

### Live verification
\`python poc_search.py\` returns real Recreation.gov data."
```

---

---

# M3: Notifications

**Branch:** `feat/m3-notifications`
**PR title:** `feat: email + Telegram notifications`

### Deliverables
- `core/notifier.py` sends email and Telegram with booking URL in message body
- 5 unit tests (both channels, both cart states, dispatch logic)
- CLI command `test-notify` for live delivery check
- Coverage ≥80%

### PR Merge Checklist
- [ ] `pytest tests/test_notifier.py -v` — 5 passed
- [ ] `pytest tests/ --cov=core/notifier --cov-report=term-missing` — ≥80%
- [ ] `python cli.py test-notify <scan_id>` sends real email or Telegram message

---

### Task 3.1: Notifier

**Files:**
- Create: `core/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_notifier.py`:

```python
import pytest
from datetime import date
from unittest.mock import MagicMock
from core.notifier import NotificationPayload, send_email, send_telegram, notify


def make_settings(**overrides):
    s = MagicMock()
    s.smtp_host = "smtp.example.com"
    s.smtp_port = 587
    s.smtp_user = "from@example.com"
    s.smtp_password = "pass"
    s.smtp_from = "CampBuddy <from@example.com>"
    s.telegram_bot_token = "bot123:token"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def make_payload(cart_added=True):
    return NotificationPayload(
        facility_name="Union West",
        site_name="1",
        campsite_type="STANDARD NONELECTRIC",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://www.recreation.gov/camping/campsites/10357088",
        cart_added=cart_added,
        nights=3,
    )


def test_email_contains_booking_url_and_cart_status(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_email("to@example.com", make_payload(cart_added=True), make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert "https://www.recreation.gov/camping/campsites/10357088" in raw
    assert "Added to cart" in raw


def test_email_fallback_message_when_cart_failed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_email("to@example.com", make_payload(cart_added=False), make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert "book manually" in raw.lower()
    assert "https://www.recreation.gov/camping/campsites/10357088" in raw


def test_telegram_contains_booking_url(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    send_telegram("123456", make_payload(), make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert "https://www.recreation.gov/camping/campsites/10357088" in text
    assert "Union West" in text


def test_notify_dispatches_both_channels(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_tg = mocker.patch("core.notifier.send_telegram")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = "123456"
    notify(scan, make_payload(), make_settings())
    mock_email.assert_called_once()
    mock_tg.assert_called_once()


def test_notify_skips_telegram_when_no_chat_id(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_tg = mocker.patch("core.notifier.send_telegram")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = None
    notify(scan, make_payload(), make_settings())
    mock_email.assert_called_once()
    mock_tg.assert_not_called()
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_notifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.notifier'`

- [ ] **Step 3: Implement `core/notifier.py`**

```python
import smtplib
import logging
import requests
from dataclasses import dataclass
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    facility_name: str
    site_name: str
    campsite_type: str
    booking_date: date
    booking_end_date: date
    booking_url: str
    cart_added: bool
    nights: int


def _format_dates(p: NotificationPayload) -> str:
    return f"{p.booking_date.strftime('%b %-d')} – {p.booking_end_date.strftime('%b %-d')}"


def send_email(to: str, payload: NotificationPayload, settings) -> None:
    dates = _format_dates(payload)
    cart_line = (
        "Added to cart — complete payment within ~15 min"
        if payload.cart_added
        else "Could not add to cart automatically — book manually now"
    )
    body = (
        f"Site:   {payload.facility_name} — Site {payload.site_name} ({payload.campsite_type})\n"
        f"Dates:  {dates} ({payload.nights} nights)\n"
        f"Status: {cart_line}\n\n"
        f"Book here: {payload.booking_url}\n"
    )
    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = f"Campsite available — {payload.facility_name} [{dates}]"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Email sent to %s", to)


def send_telegram(chat_id: str, payload: NotificationPayload, settings) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not set, skipping")
        return
    dates = _format_dates(payload)
    cart_line = (
        "✅ Added to cart — complete payment within ~15 min"
        if payload.cart_added
        else "⚠️ Could not add to cart automatically — book manually now"
    )
    text = (
        f"🏕 Campsite available!\n"
        f"{payload.facility_name} — Site {payload.site_name}\n"
        f"{dates} ({payload.nights} nights) · {payload.campsite_type}\n\n"
        f"{cart_line}\n"
        f"🔗 {payload.booking_url}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    if not resp.ok:
        logger.error("Telegram failed: %s", resp.text)


def notify(scan, payload: NotificationPayload, settings) -> None:
    if scan.notify_via_email and scan.user.email:
        try:
            send_email(scan.user.email, payload, settings)
        except Exception as e:
            logger.error("Email error: %s", e)

    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram(scan.user.telegram_chat_id, payload, settings)
        except Exception as e:
            logger.error("Telegram error: %s", e)
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_notifier.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Coverage check**

```bash
pytest tests/test_notifier.py --cov=core/notifier --cov-report=term-missing
```

Expected: ≥80%.

- [ ] **Step 6: Add `test-notify` CLI command to `cli.py`**

Add this command to `cli.py` alongside the other `@cli.command()` definitions (cli.py will be fully implemented in M6 — add this stub now so notification can be tested live):

```python
@cli.command()
@click.argument("scan_id", type=int)
def test_notify(scan_id: int):
    """Send a test notification for a scan (simulates a found site)."""
    from datetime import date
    from core.notifier import notify, NotificationPayload
    factory, settings = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        payload = NotificationPayload(
            facility_name="TEST — Upper Pines Campground",
            site_name="42",
            campsite_type="STANDARD NONELECTRIC",
            booking_date=date(2026, 7, 4),
            booking_end_date=date(2026, 7, 7),
            booking_url="https://www.recreation.gov/camping/campsites/99999",
            cart_added=False,
            nights=3,
        )
        notify(scan, payload, settings)
    click.echo("Test notification sent.")
```

Note: `cli.py` needs the `Scan` import and `get_factory()` helper — these are defined in full in M6 Task 6.1. If implementing M3 in isolation, create a minimal `cli.py` stub with just the `test_notify` command and the imports it needs.

- [ ] **Step 7: Live notification test**

```bash
python cli.py seed config/scans.yaml
python cli.py test-notify 1
```

Expected: email or Telegram message received at configured address.

- [ ] **Step 8: Commit**

```bash
git add core/notifier.py tests/test_notifier.py cli.py
git commit -m "feat(m3): email and Telegram notifier with test-notify CLI command"
```

---

### M3 PR

- [ ] **Create PR**

```bash
git push origin feat/m3-notifications
gh pr create \
  --title "feat: email + Telegram notifications" \
  --base main \
  --body "## M3: Notifications

### What's in this PR
- core/notifier.py: email (smtplib) + Telegram (Bot API) dispatch
- NotificationPayload dataclass (facility, site, dates, booking_url, cart_added)
- Booking URL always in plain text regardless of cart status
- Per-scan channel dispatch (notify_via_email, notify_via_telegram)
- cli test-notify command for live delivery verification
- 5 unit tests, all external I/O mocked

### Coverage
core/notifier.py ≥80%

### Live verification
\`python cli.py test-notify 1\` — real message delivered."
```

---

---

# M4: Booking Sidecar

**Branch:** `feat/m4-booking-sidecar`
**PR title:** `feat: Playwright sidecar service and booking client`

### Deliverables
- Playwright FastAPI sidecar service runs and health check passes
- `core/booking.py` HTTP client handles all outcomes (success, failure, connection error)
- 4 booking client tests + 2 FastAPI app tests (browser mocked)
- `docker compose up playwright` and `curl /health` returns `{"status":"ok"}`
- ARCHITECTURE.md updated with Playwright flow

### PR Merge Checklist
- [ ] `pytest tests/test_booking.py -v` — 4 passed
- [ ] `pytest tests/ --cov=core/booking --cov-report=term-missing` — ≥80%
- [ ] `docker compose up playwright -d && curl http://localhost:8001/health` — `{"status":"ok"}`
- [ ] `docker compose down`

---

### Task 4.1: Playwright Sidecar

**Files:**
- Create: `playwright_service/browser.py`
- Create: `playwright_service/main.py`
- Create: `playwright_service/Dockerfile`

- [ ] **Step 1: Implement `playwright_service/browser.py`**

```python
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.recreation.gov/login"
EMAIL_SELECTOR = "input[name='email'], input[type='email']"
PASSWORD_SELECTOR = "input[name='password'], input[type='password']"
SUBMIT_SELECTOR = "button[type='submit']"
CART_SELECTOR = "button[data-component='book-campsite'], button:has-text('Add to Cart'), button:has-text('Book Now')"


def add_to_cart(booking_url: str, email: str, password: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            page.fill(EMAIL_SELECTOR, email)
            page.fill(PASSWORD_SELECTOR, password)
            page.click(SUBMIT_SELECTOR)
            page.wait_for_url(lambda url: "login" not in url, timeout=15_000)

            page.goto(booking_url, wait_until="networkidle", timeout=30_000)
            page.wait_for_selector(CART_SELECTOR, timeout=10_000)
            page.click(CART_SELECTOR)
            page.wait_for_timeout(3_000)

            if "cart" in page.url or "checkout" in page.url:
                return {"success": True}
            return {"success": False, "error": "Cart page not reached after click"}

        except PlaywrightTimeout as e:
            logger.error("Playwright timeout: %s", e)
            return {"success": False, "error": f"Timeout: {e}"}
        except Exception as e:
            logger.error("Playwright error: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            browser.close()
```

- [ ] **Step 2: Implement `playwright_service/main.py`**

```python
import logging
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from playwright_service.browser import add_to_cart

logging.basicConfig(level=logging.INFO)
app = FastAPI()


class CartRequest(BaseModel):
    booking_url: str
    email: str
    password: str


class CartResponse(BaseModel):
    success: bool
    error: str | None = None


@app.post("/add-to-cart", response_model=CartResponse)
def cart_endpoint(req: CartRequest) -> CartResponse:
    return CartResponse(**add_to_cart(req.booking_url, req.email, req.password))


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("playwright_service.main:app", host="0.0.0.0", port=8001)
```

- [ ] **Step 3: Create `playwright_service/Dockerfile`**

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY playwright_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY playwright_service/ ./playwright_service/
CMD ["python", "-m", "playwright_service.main"]
```

- [ ] **Step 4: Commit**

```bash
git add playwright_service/browser.py playwright_service/main.py playwright_service/Dockerfile
git commit -m "feat(m4): Playwright sidecar FastAPI service"
```

---

### Task 4.2: Booking Client

**Files:**
- Create: `core/booking.py`
- Create: `tests/test_booking.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_booking.py`:

```python
import httpx
import pytest
from unittest.mock import MagicMock
from core.booking import attempt_cart_add


def make_settings(url="http://playwright:8001"):
    s = MagicMock()
    s.playwright_service_url = url
    return s


def test_returns_true_on_success(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is True


def test_returns_false_on_service_failure(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": False, "error": "Login failed"})
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False


def test_returns_false_on_http_500(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(500)
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False


def test_returns_false_on_connection_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_booking.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.booking'`

- [ ] **Step 3: Implement `core/booking.py`**

```python
import logging
import httpx

logger = logging.getLogger(__name__)


def attempt_cart_add(booking_url: str, email: str, password: str, settings) -> bool:
    try:
        resp = httpx.post(
            f"{settings.playwright_service_url}/add-to-cart",
            json={"booking_url": booking_url, "email": email, "password": password},
            timeout=60.0,
        )
        if not resp.is_success:
            logger.error("Sidecar returned HTTP %d", resp.status_code)
            return False
        data = resp.json()
        if not data.get("success"):
            logger.warning("Cart add failed: %s", data.get("error"))
        return bool(data.get("success"))
    except httpx.HTTPError as e:
        logger.error("HTTP error contacting sidecar: %s", e)
        return False
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_booking.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Coverage check**

```bash
pytest tests/test_booking.py --cov=core/booking --cov-report=term-missing
```

Expected: ≥80%.

- [ ] **Step 6: Commit**

```bash
git add core/booking.py tests/test_booking.py
git commit -m "feat(m4): booking HTTP client for Playwright sidecar"
```

---

### Task 4.3: Sidecar Health Check

- [ ] **Step 1: Build and start Playwright container**

```bash
docker compose build playwright
docker compose up playwright -d
```

- [ ] **Step 2: Verify health endpoint**

```bash
curl http://localhost:8001/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Stop container**

```bash
docker compose down
```

- [ ] **Step 4: Commit docker-compose stub if not yet present**

Create a minimal `docker-compose.yml` (full version in M6):

```yaml
services:
  playwright:
    build:
      context: .
      dockerfile: playwright_service/Dockerfile
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```

```bash
git add docker-compose.yml
git commit -m "feat(m4): docker-compose with playwright sidecar"
```

---

### M4 PR

- [ ] **Create PR**

```bash
git push origin feat/m4-booking-sidecar
gh pr create \
  --title "feat: Playwright sidecar service and booking client" \
  --base main \
  --body "## M4: Booking Sidecar

### What's in this PR
- playwright_service/: FastAPI app + Playwright browser automation
- Logs in to Recreation.gov, navigates to campsite, clicks Add to Cart
- core/booking.py: httpx client, handles all failure modes (non-fatal)
- 4 booking client unit tests (success, service failure, HTTP 500, connection error)
- Docker container verified with /health check

### Coverage
core/booking.py ≥80%

### Verified
\`docker compose up playwright -d && curl http://localhost:8001/health\` → {\"status\":\"ok\"}"
```

---

---

# M5: Core Runner + Scheduler

**Branch:** `feat/m5-runner-scheduler`
**PR title:** `feat: scan runner, scheduler, and integration test`

### Deliverables
- `core/runner.py` executes full scan cycle, writes all DB records
- `core/scheduler.py` manages APScheduler jobs per active scan
- Full integration test (`tests/test_integration.py`) runs end-to-end with mocked I/O
- Coverage ≥85% on runner, ≥70% on scheduler
- ARCHITECTURE.md data flow section verified

### PR Merge Checklist
- [ ] `pytest tests/test_runner.py -v` — 5 passed
- [ ] `pytest tests/test_scheduler.py -v` — 3 passed
- [ ] `pytest tests/test_integration.py -v` — 2 passed
- [ ] `pytest tests/ --cov=core/runner --cov-report=term-missing` — ≥85%
- [ ] `pytest tests/ --cov=core/scheduler --cov-report=term-missing` — ≥70%

---

### Task 5.1: Scan Runner

**Files:**
- Create: `core/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_runner.py`:

```python
import pytest
from datetime import datetime, date
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Scan, ScanRun, ScanResult
from core.runner import run_scan


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def settings():
    s = MagicMock()
    s.encryption_key = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ="
    s.playwright_service_url = "http://playwright:8001"
    return s


@pytest.fixture
def scan_id(factory):
    with factory() as db:
        user = User(email="test@example.com", recreationgov_email="rg@example.com")
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            rec_area_ids=[1076],
            nights=3,
            polling_interval=300,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status="active",
        )
        db.add(scan)
        db.commit()
        return scan.id


def make_site(campsite_id="10357088", check_in=date(2026, 7, 3)):
    site = MagicMock()
    site.campsite_id = campsite_id
    site.facility_name = "Union West"
    site.campsite_site_name = "1"
    site.campsite_type = "STANDARD NONELECTRIC"
    site.booking_date = datetime.combine(check_in, datetime.min.time())
    site.booking_end_date = datetime.combine(date(2026, 7, 6), datetime.min.time())
    site.booking_url = f"https://www.recreation.gov/camping/campsites/{campsite_id}"
    site.booking_nights = 3
    return site


def test_run_writes_scan_run_on_no_results(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[])
    run_scan(scan_id, factory, settings)
    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "no_results"
        assert run.sites_found == 0
        assert run.finished_at is not None


def test_run_writes_scan_run_on_error(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", side_effect=RuntimeError("boom"))
    run_scan(scan_id, factory, settings)
    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "error"
        assert "boom" in run.error_message


def test_run_saves_result_notifies_and_marks_cart(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.cart_added is True
        assert result.notified is True
    mock_notify.assert_called_once()


def test_dedup_skips_same_site_same_date(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 1


def test_dedup_notifies_same_site_different_date(factory, scan_id, settings, mocker):
    site_a = make_site(check_in=date(2026, 7, 3))
    site_b = make_site(check_in=date(2026, 7, 10))
    mocker.patch("core.runner.check_availability", side_effect=[[site_a], [site_b]])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 2
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_runner.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.runner'`

- [ ] **Step 3: Implement `core/runner.py`**

```python
import logging
from datetime import datetime
from db.models import Scan, ScanRun, ScanResult, User
from core.availability import check_availability
from core.booking import attempt_cart_add
from core.crypto import decrypt_password
from core.notifier import notify, NotificationPayload

logger = logging.getLogger(__name__)


def run_scan(scan_id: int, session_factory, settings) -> None:
    with session_factory() as db:
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.status == "active").first()
        if not scan:
            logger.warning("Scan %d not found or inactive", scan_id)
            return

        run = ScanRun(scan_id=scan_id, started_at=datetime.utcnow())
        db.add(run)
        db.flush()

        try:
            sites = check_availability(scan)
            run.sites_found = len(sites)
            run.outcome = "success" if sites else "no_results"
            user = db.query(User).filter(User.id == scan.user_id).first()

            for site in sites:
                booking_date = (
                    site.booking_date.date()
                    if hasattr(site.booking_date, "date")
                    else site.booking_date
                )
                booking_end_date = (
                    site.booking_end_date.date()
                    if hasattr(site.booking_end_date, "date")
                    else site.booking_end_date
                )

                if scan.notify_on_new_only:
                    exists = (
                        db.query(ScanResult)
                        .filter(
                            ScanResult.scan_id == scan_id,
                            ScanResult.campsite_id == str(site.campsite_id),
                            ScanResult.booking_date == booking_date,
                        )
                        .first()
                    )
                    if exists:
                        continue

                result = ScanResult(
                    scan_run_id=run.id,
                    scan_id=scan_id,
                    campsite_id=str(site.campsite_id),
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    first_seen_at=datetime.utcnow(),
                )
                db.add(result)
                db.flush()

                cart_added = False
                if user and user.recreationgov_email and user.recreationgov_password:
                    try:
                        pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
                        cart_added = attempt_cart_add(
                            site.booking_url, user.recreationgov_email, pw, settings
                        )
                    except Exception as e:
                        logger.error("Cart add error for scan %d: %s", scan_id, e)

                result.cart_added = cart_added
                if cart_added:
                    result.cart_added_at = datetime.utcnow()

                payload = NotificationPayload(
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    cart_added=cart_added,
                    nights=scan.nights,
                )
                try:
                    notify(scan, payload, settings)
                    result.notified = True
                    result.notified_at = datetime.utcnow()
                except Exception as e:
                    logger.error("Notify error for scan %d: %s", scan_id, e)

        except Exception as e:
            logger.exception("Scan %d failed: %s", scan_id, e)
            run.outcome = "error"
            run.error_message = str(e)
            run.sites_found = 0
        finally:
            run.finished_at = datetime.utcnow()
            db.commit()
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_runner.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Coverage check**

```bash
pytest tests/test_runner.py --cov=core/runner --cov-report=term-missing
```

Expected: ≥85%.

- [ ] **Step 6: Commit**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "feat(m5): scan runner with dedup, cart, and notification dispatch"
```

---

### Task 5.2: Scheduler

**Files:**
- Create: `core/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:

```python
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Scan
from core.scheduler import sync_jobs, build_scheduler


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def add_scan(factory, status="active", interval=300):
    with factory() as db:
        user = User(email="t@e.com")
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            nights=1,
            polling_interval=interval,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status=status,
        )
        db.add(scan)
        db.commit()
        return scan.id


def test_sync_adds_active_scan(factory):
    scan_id = add_scan(factory, status="active", interval=300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.add_job.assert_called_once()
    assert scheduler.add_job.call_args[1]["id"] == f"scan_{scan_id}"
    assert scheduler.add_job.call_args[1]["seconds"] == 300


def test_sync_skips_paused_scan(factory):
    add_scan(factory, status="paused")
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.add_job.assert_not_called()


def test_sync_removes_stale_job(factory):
    scan_id = add_scan(factory, status="active")
    stale_job = MagicMock()
    stale_job.id = "scan_9999"
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [stale_job]
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.remove_job.assert_called_once_with("scan_9999")
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_scheduler.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.scheduler'`

- [ ] **Step 3: Implement `core/scheduler.py`**

```python
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from core.runner import run_scan

logger = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")


def sync_jobs(scheduler: BackgroundScheduler, session_factory, settings) -> None:
    from db.models import Scan
    with session_factory() as db:
        active = db.query(Scan).filter(Scan.status == "active").all()
        active_ids = {f"scan_{s.id}" for s in active}
        active_map = {f"scan_{s.id}": s for s in active}

    existing_ids = {job.id for job in scheduler.get_jobs() if job.id.startswith("scan_")}

    for job_id in existing_ids - active_ids:
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)

    for job_id in active_ids - existing_ids:
        scan = active_map[job_id]
        scheduler.add_job(
            run_scan,
            trigger=IntervalTrigger(seconds=scan.polling_interval),
            id=job_id,
            args=[scan.id, session_factory, settings],
            max_instances=1,
            coalesce=True,
        )
        logger.info("Scheduled %s every %ds", job_id, scan.polling_interval)


def start_scheduler(session_factory, settings) -> BackgroundScheduler:
    scheduler = build_scheduler()
    sync_jobs(scheduler, session_factory, settings)
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(seconds=60),
        id="__sync_jobs__",
        args=[scheduler, session_factory, settings],
    )
    scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/test_scheduler.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat(m5): APScheduler with sync_jobs and auto-refresh"
```

---

### Task 5.3: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_integration.py`:

```python
"""
End-to-end integration tests. Real SQLite, real session factory.
All external I/O (camply, httpx, SMTP, Telegram) is mocked.
Verifies that runner + DB interaction produces correct final state.
"""
import pytest
from datetime import datetime, date
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Scan, ScanRun, ScanResult
from db.session import make_session_factory, get_db
from core.runner import run_scan
from cryptography.fernet import Fernet


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def settings(fernet_key):
    s = MagicMock()
    s.encryption_key = fernet_key
    s.playwright_service_url = "http://playwright:8001"
    return s


def seed_user_and_scan(factory, fernet_key):
    from core.crypto import encrypt_password
    with factory() as db:
        user = User(
            email="test@example.com",
            recreationgov_email="rg@example.com",
            recreationgov_password=encrypt_password("secret123", fernet_key),
        )
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            rec_area_ids=[1076],
            nights=3,
            polling_interval=300,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status="active",
        )
        db.add(scan)
        db.commit()
        return scan.id


def make_site():
    s = MagicMock()
    s.campsite_id = "10357088"
    s.facility_name = "Union West"
    s.campsite_site_name = "1"
    s.campsite_type = "STANDARD NONELECTRIC"
    s.booking_date = datetime(2026, 7, 3)
    s.booking_end_date = datetime(2026, 7, 6)
    s.booking_url = "https://www.recreation.gov/camping/campsites/10357088"
    s.booking_nights = 3
    return s


def test_full_scan_cycle_creates_complete_db_state(factory, settings, fernet_key, mocker):
    scan_id = seed_user_and_scan(factory, fernet_key)
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mocker.patch("core.runner.notify")

    run_scan(scan_id, factory, settings)

    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "success"
        assert run.sites_found == 1
        assert run.finished_at is not None

        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.campsite_id == "10357088"
        assert result.cart_added is True
        assert result.notified is True
        assert result.booking_url == "https://www.recreation.gov/camping/campsites/10357088"


def test_full_scan_cycle_on_error_still_writes_run(factory, settings, fernet_key, mocker):
    scan_id = seed_user_and_scan(factory, fernet_key)
    mocker.patch("core.runner.check_availability", side_effect=Exception("network error"))

    run_scan(scan_id, factory, settings)

    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "error"
        assert "network error" in run.error_message
        assert run.finished_at is not None
        assert db.query(ScanResult).filter(ScanResult.scan_id == scan_id).count() == 0
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_integration.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Run full suite with coverage**

```bash
pytest tests/ --cov=core --cov=db --cov-report=term-missing \
  --ignore=playwright_service/browser.py
```

Expected: runner ≥85%, availability ≥85%, notifier ≥80%, booking ≥80%, crypto 100%.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(m5): end-to-end integration test for full scan cycle"
```

---

### M5 PR

- [ ] **Create PR**

```bash
git push origin feat/m5-runner-scheduler
gh pr create \
  --title "feat: scan runner, scheduler, and integration test" \
  --base main \
  --body "## M5: Core Runner + Scheduler

### What's in this PR
- core/runner.py: full scan execution — availability check, scan_run write, dedup, cart add, notify, result write
- core/scheduler.py: APScheduler with sync_jobs (adds/removes jobs as scan statuses change)
- tests/test_runner.py: 5 unit tests including dedup scenarios
- tests/test_scheduler.py: 3 unit tests
- tests/test_integration.py: 2 end-to-end tests with real SQLite, all I/O mocked

### Coverage
- core/runner.py ≥85%
- core/scheduler.py ≥70%

### Key behaviors verified
- scan_run always written (even on error)
- dedup by campsite_id + booking_date (same site, different dates = two notifications)
- notify_on_new_only=false allows repeat notifications
- cart add failure is non-fatal (user still notified)"
```

---

---

# M6: CLI + Deployment

**Branch:** `feat/m6-cli-deploy`
**PR title:** `feat: CLI, Docker Compose, and VPS deployment`

### Deliverables
- Full `cli.py` with seed, list-scans, pause, resume, delete-scan, test-notify
- `main.py` entry point with graceful shutdown
- `Dockerfile` for app container
- Complete `docker-compose.yml` (app + playwright, health check, volume mount)
- `.dockerignore`
- `config/scans.yaml` example with two realistic scans
- `docker compose up -d` starts both containers; scans execute and notifications fire
- README.md updated with final deployment steps

### PR Merge Checklist
- [ ] `python cli.py seed config/scans.yaml && python cli.py list-scans` — scans appear
- [ ] `python cli.py test-notify 1` — notification received
- [ ] `python cli.py pause 1 && python cli.py list-scans` — shows paused
- [ ] `docker compose build` — no errors
- [ ] `docker compose up -d && docker compose logs app` — logs show `CampBuddy running` + scheduled jobs
- [ ] `pytest tests/ -v` — all tests still pass

---

### Task 6.1: CLI

**Files:**
- Create: `cli.py`

- [ ] **Step 1: Implement `cli.py`**

```python
import logging
import yaml
import click
from db.models import User, Scan
from db.session import make_engine, create_tables, make_session_factory, get_db
from config.settings import get_settings
from core.crypto import encrypt_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_factory():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_tables(engine)
    return make_session_factory(engine), settings


@click.group()
def cli():
    """CampBuddy — campsite availability monitor."""


@cli.command()
@click.argument("yaml_path", default="config/scans.yaml")
def seed(yaml_path: str):
    """Seed users and scans from YAML. Safe to run multiple times."""
    factory, settings = get_factory()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    with get_db(factory) as db:
        for u in data.get("users", []):
            user = db.query(User).filter(User.email == u["email"]).first()
            if not user:
                user = User(email=u["email"])
                db.add(user)
                db.flush()
                logger.info("Created user %s", u["email"])
            if u.get("telegram_chat_id"):
                user.telegram_chat_id = str(u["telegram_chat_id"])
            if u.get("recreationgov_email"):
                user.recreationgov_email = u["recreationgov_email"]
            if u.get("recreationgov_password"):
                user.recreationgov_password = encrypt_password(
                    str(u["recreationgov_password"]), settings.encryption_key
                )
        db.flush()

        for s in data.get("scans", []):
            user = db.query(User).filter(User.email == s["user_email"]).first()
            if not user:
                logger.error("User %s not found — skipping scan", s["user_email"])
                continue
            scan = Scan(
                user_id=user.id,
                provider=s.get("provider", "RecreationDotGov"),
                polling_interval=s.get("polling_interval", 300),
                rec_area_ids=s.get("rec_area_ids"),
                campground_ids=s.get("campground_ids"),
                campsite_ids=s.get("campsite_ids"),
                search_windows=s["search_windows"],
                nights=s.get("nights", 1),
                days_of_week=s.get("days_of_week"),
                weekends_only=s.get("weekends_only", False),
                notify_via_email=s.get("notify_via_email", True),
                notify_via_telegram=s.get("notify_via_telegram", False),
                notify_on_new_only=s.get("notify_on_new_only", True),
            )
            db.add(scan)
            logger.info("Added scan for %s (%s)", s["user_email"], s.get("provider", "RecreationDotGov"))

    click.echo("Seed complete.")


@cli.command("list-scans")
def list_scans():
    """List all scans and their current status."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scans = db.query(Scan).join(User).all()
        if not scans:
            click.echo("No scans found.")
            return
        for s in scans:
            windows = len(s.search_windows)
            click.echo(
                f"[{s.id:3}] {s.status:9} | {s.user.email:30} | {s.provider:20} | "
                f"interval={s.polling_interval}s | {windows} window(s)"
            )


@cli.command()
@click.argument("scan_id", type=int)
def pause(scan_id: int):
    """Pause an active scan (keeps all history)."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        scan.status = "paused"
    click.echo(f"Scan {scan_id} paused.")


@cli.command()
@click.argument("scan_id", type=int)
def resume(scan_id: int):
    """Resume a paused scan."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        scan.status = "active"
    click.echo(f"Scan {scan_id} resumed.")


@cli.command("delete-scan")
@click.argument("scan_id", type=int)
@click.confirmation_option(prompt="Delete scan and all its history?")
def delete_scan(scan_id: int):
    """Delete a scan and all associated run history."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        db.delete(scan)
    click.echo(f"Scan {scan_id} deleted.")


@cli.command("test-notify")
@click.argument("scan_id", type=int)
def test_notify(scan_id: int):
    """Send a test notification for a scan to verify channels work."""
    from datetime import date
    from core.notifier import notify, NotificationPayload
    factory, settings = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        payload = NotificationPayload(
            facility_name="TEST — Upper Pines Campground",
            site_name="42",
            campsite_type="STANDARD NONELECTRIC",
            booking_date=date(2026, 7, 4),
            booking_end_date=date(2026, 7, 7),
            booking_url="https://www.recreation.gov/camping/campsites/99999",
            cart_added=False,
            nights=3,
        )
        notify(scan, payload, settings)
    click.echo("Test notification sent.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI commands**

```bash
mkdir -p data
python cli.py seed config/scans.yaml
python cli.py list-scans
python cli.py pause 1
python cli.py list-scans   # should show status=paused
python cli.py resume 1
python cli.py list-scans   # should show status=active
```

Expected: all commands succeed with appropriate output.

- [ ] **Step 3: Commit**

```bash
git add cli.py
git commit -m "feat(m6): CLI — seed, list, pause, resume, delete, test-notify"
```

---

### Task 6.2: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement `main.py`**

```python
import logging
import signal
import sys
import time
from db.session import make_engine, create_tables, make_session_factory
from core.scheduler import start_scheduler
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_tables(engine)
    session_factory = make_session_factory(engine)

    scheduler = start_scheduler(session_factory, settings)

    def _shutdown(sig, _frame):
        logger.info("Shutting down (signal %d)...", sig)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("CampBuddy running. SIGINT or SIGTERM to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

```bash
timeout 5 python main.py || true
```

Expected: logs show `Scheduler started` and `CampBuddy running` before timeout exits.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat(m6): main entry point with graceful SIGTERM shutdown"
```

---

### Task 6.3: Docker Setup

**Files:**
- Create: `Dockerfile`
- Update: `docker-compose.yml` (full version)
- Create: `.dockerignore`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
CMD ["python", "main.py"]
```

- [ ] **Step 2: Update `docker-compose.yml` (full version)**

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    volumes:
      - ./data:/app/data
    depends_on:
      playwright:
        condition: service_healthy
    restart: unless-stopped

  playwright:
    build:
      context: .
      dockerfile: playwright_service/Dockerfile
    expose:
      - "8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
```

- [ ] **Step 3: Create `.dockerignore`**

```
.env
data/
__pycache__/
*.pyc
.pytest_cache/
tests/
*.egg-info/
.git/
```

- [ ] **Step 4: Build both images**

```bash
docker compose build
```

Expected: both images build without errors.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat(m6): Dockerfile and docker-compose.yml for VPS deployment"
```

---

### Task 6.4: Config Example

**Files:**
- Create: `config/scans.yaml`

- [ ] **Step 1: Create `config/scans.yaml`**

```yaml
# CampBuddy scan configuration
# Run: python cli.py seed config/scans.yaml
# Passwords are encrypted at seed time — plain text here is safe on a local machine.

users:
  - email: you@example.com
    telegram_chat_id: ""                   # optional — find yours by messaging @userinfobot
    recreationgov_email: you@example.com
    recreationgov_password: your-password  # plain here, Fernet-encrypted in DB

scans:
  # Watch two rec areas for a 3-night weekend in July
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 300                  # check every 5 minutes
    rec_area_ids: [1076, 2991]
    search_windows:
      - start_date: "2026-07-03"
        end_date: "2026-07-06"
    nights: 3
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true

  # Watch a specific rec area for any available consecutive weekend nights
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 600
    rec_area_ids: [2991]
    search_windows:
      - start_date: "2026-07-12"
        end_date: "2026-07-13"
      - start_date: "2026-07-19"
        end_date: "2026-07-20"
      - start_date: "2026-07-26"
        end_date: "2026-07-27"
    nights: 1
    notify_via_email: true
    notify_via_telegram: true
    notify_on_new_only: true

  # Watch for any 4-night stretch at a single campground over an entire summer season
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 900
    rec_area_ids: [2991]
    search_windows:
      - start_date: "2026-06-01"
        end_date: "2026-09-01"
    nights: 4
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true
```

- [ ] **Step 2: Commit**

```bash
git add config/scans.yaml
git commit -m "docs(m6): example scans.yaml with three realistic scan configurations"
```

---

### Task 6.5: Final Smoke Test + README Update

- [ ] **Step 1: Full test suite**

```bash
pytest tests/ -v --ignore=playwright_service/browser.py
```

Expected: all tests pass.

- [ ] **Step 2: Coverage report**

```bash
pytest tests/ --cov=core --cov=db --cov-report=term-missing \
  --ignore=playwright_service/browser.py
```

Expected output (minimum):

```
core/runner.py        ≥85%
core/availability.py  ≥85%
core/notifier.py      ≥80%
core/booking.py       ≥80%
core/crypto.py        100%
db/models.py          ≥75%
db/session.py         ≥75%
core/scheduler.py     ≥70%
```

- [ ] **Step 3: End-to-end Docker smoke test**

```bash
# Ensure .env is populated
python cli.py seed config/scans.yaml
docker compose up -d
sleep 15
docker compose logs app | grep "Scheduled\|CampBuddy running"
docker compose down
```

Expected: logs contain `Scheduled scan_1` and `CampBuddy running`.

- [ ] **Step 4: Update README.md deployment section**

Add to README.md under Deployment:

```markdown
## Updating scans after deployment

```bash
# On VPS: edit config/scans.yaml, then re-seed
python cli.py seed config/scans.yaml
# Scheduler auto-picks up new scans within 60 seconds — no restart needed
```

## Monitoring

```bash
docker compose logs -f app          # live logs
docker compose logs playwright      # browser automation logs
docker compose ps                   # container health
```

## Backup

```bash
# On VPS — add to crontab
cp data/campbuddy.db data/campbuddy.db.$(date +%Y%m%d)
```
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs(m6): deployment, monitoring, and backup instructions"
```

---

### M6 PR

- [ ] **Run final coverage report and capture output**

```bash
pytest tests/ --cov=core --cov=db --cov-report=term-missing \
  --ignore=playwright_service/browser.py 2>&1 | tail -20
```

- [ ] **Create PR**

```bash
git push origin feat/m6-cli-deploy
gh pr create \
  --title "feat: CLI, Docker Compose, and VPS deployment" \
  --base main \
  --body "## M6: CLI + Deployment

### What's in this PR
- cli.py: seed, list-scans, pause, resume, delete-scan, test-notify
- main.py: entry point with SIGINT/SIGTERM graceful shutdown
- Dockerfile for app container (python:3.11-slim)
- docker-compose.yml: app + playwright sidecar, health check, volume mount
- config/scans.yaml: three example scans covering different use cases
- README.md: deployment, monitoring, backup instructions

### Deployment verified
\`docker compose up -d\` → containers start → scheduler fires jobs → logs show scan activity

### Test suite
All tests pass. Coverage targets met across all modules."
```

---

## Phase 1 Complete

After M6 merges, Phase 1 is done. The system:
- Monitors campground availability on schedule via camply
- Attempts Playwright add-to-cart when sites are found
- Notifies via email and/or Telegram with direct booking URL
- Stores full run history in SQLite
- Is managed via CLI and configured via YAML
- Runs on a VPS via Docker Compose

**Next:** Phase 2 plan — web dashboard (FastAPI + HTMX, manage scans in a browser).
