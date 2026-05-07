# CampBuddy Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core campsite monitoring engine — camply-powered availability scanning, Playwright add-to-cart automation, email + Telegram notifications, full run history in SQLite, all driven by YAML config.

**Architecture:** APScheduler fires periodic jobs per scan config. Each job calls camply's OO API for availability, attempts Playwright add-to-cart via an isolated sidecar service, and dispatches notifications. All results are written to SQLite regardless of outcome.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, APScheduler 3.x, camply 0.34+, Playwright (sidecar FastAPI service), httpx, cryptography (Fernet), pydantic-settings, click, pytest

---

## File Map

```
campbuddy/
├── config/
│   ├── settings.py           # pydantic-settings — loads .env
│   └── scans.yaml            # Phase 1 scan + user definitions
├── core/
│   ├── availability.py       # camply OO API wrapper → list[AvailableCampsite]
│   ├── booking.py            # httpx client → playwright sidecar
│   ├── crypto.py             # Fernet encrypt/decrypt helpers
│   ├── notifier.py           # email (smtplib) + Telegram (requests)
│   ├── runner.py             # executes one scan end-to-end
│   └── scheduler.py          # APScheduler setup + job registration
├── db/
│   ├── models.py             # SQLAlchemy ORM: User, Scan, ScanRun, ScanResult
│   └── session.py            # engine, SessionLocal, create_tables, get_db
├── playwright_service/
│   ├── browser.py            # Playwright add-to-cart logic
│   ├── main.py               # FastAPI: POST /add-to-cart
│   ├── requirements.txt
│   └── Dockerfile
├── tests/
│   ├── conftest.py           # fixtures: in-memory DB, mock settings, sample scan
│   ├── test_models.py
│   ├── test_crypto.py
│   ├── test_availability.py
│   ├── test_notifier.py
│   ├── test_booking.py
│   └── test_runner.py
├── cli.py                    # seed DB from scans.yaml; list/pause/delete scans
├── main.py                   # entry point: init DB + start scheduler
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── requirements.txt
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `playwright_service/requirements.txt`
- Create: `.env.example`
- Create: `tests/__init__.py`, `core/__init__.py`, `db/__init__.py`, `config/__init__.py`, `playwright_service/__init__.py`

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
```

- [ ] **Step 2: Create `playwright_service/requirements.txt`**

```
playwright==1.44.0
fastapi==0.111.0
uvicorn==0.29.0
```

- [ ] **Step 3: Create `.env.example`**

```
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key-here

# SMTP (e.g. Gmail app password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=CampBuddy <you@gmail.com>

# Telegram bot token from @BotFather (leave empty to disable)
TELEGRAM_BOT_TOKEN=

# Playwright sidecar URL (matches docker-compose service name)
PLAYWRIGHT_SERVICE_URL=http://playwright:8001

# SQLite path (mounted volume in Docker)
DATABASE_URL=sqlite:///./data/campbuddy.db
```

- [ ] **Step 4: Create empty `__init__.py` files**

```bash
touch tests/__init__.py core/__init__.py db/__init__.py config/__init__.py playwright_service/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt playwright_service/requirements.txt .env.example tests/__init__.py core/__init__.py db/__init__.py config/__init__.py playwright_service/__init__.py
git commit -m "feat: project scaffold and dependencies"
```

---

## Task 2: Settings Module

**Files:**
- Create: `config/settings.py`

- [ ] **Step 1: Write test**

Create `tests/test_settings.py`:

```python
import os
import pytest
from config.settings import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.smtp_user == "test@example.com"
    assert s.playwright_service_url == "http://playwright:8001"


def test_settings_telegram_defaults_empty(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == ""
```

- [ ] **Step 2: Run test to verify it fails**

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

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_settings.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat: settings module with pydantic-settings"
```

---

## Task 3: Database Models and Session

**Files:**
- Create: `db/models.py`
- Create: `db/session.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write tests**

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


def test_create_user(db):
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.created_at is not None


def test_create_scan(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        provider="RecreationDotGov",
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        rec_area_ids=[1076],
        nights=3,
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.commit()
    assert scan.id is not None
    assert scan.status == "active"


def test_create_scan_run_always_written(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        provider="RecreationDotGov",
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        nights=1,
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
        outcome="no_results",
        sites_found=0,
    )
    db.add(run)
    db.commit()
    assert run.id is not None
    assert run.outcome == "no_results"


def test_create_scan_result(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        provider="RecreationDotGov",
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        nights=1,
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
```

- [ ] **Step 2: Run tests to verify they fail**

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

    scans: Mapped[list["Scan"]] = relationship(back_populates="user")


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
    runs: Mapped[list["ScanRun"]] = relationship(back_populates="scan")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="scan")


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

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add db/models.py db/session.py tests/test_models.py
git commit -m "feat: SQLAlchemy models and session factory"
```

---

## Task 4: Crypto Helpers

**Files:**
- Create: `core/crypto.py`
- Create: `tests/test_crypto.py`

- [ ] **Step 1: Write tests**

Create `tests/test_crypto.py`:

```python
from cryptography.fernet import Fernet
from core.crypto import encrypt_password, decrypt_password


def test_roundtrip():
    key = Fernet.generate_key().decode()
    plaintext = "s3cr3t-p@ssword!"
    encrypted = encrypt_password(plaintext, key)
    assert encrypted != plaintext
    assert decrypt_password(encrypted, key) == plaintext


def test_encrypted_value_differs_each_call():
    key = Fernet.generate_key().decode()
    a = encrypt_password("same", key)
    b = encrypt_password("same", key)
    # Fernet uses random IV so ciphertext differs
    assert a != b


def test_decrypt_wrong_key_raises():
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    encrypted = encrypt_password("secret", key1)
    import pytest
    with pytest.raises(Exception):
        decrypt_password(encrypted, key2)
```

- [ ] **Step 2: Run tests to verify they fail**

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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_crypto.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/crypto.py tests/test_crypto.py
git commit -m "feat: Fernet encrypt/decrypt helpers"
```

---

## Task 5: Availability Wrapper

**Files:**
- Create: `core/availability.py`
- Create: `tests/test_availability.py`

- [ ] **Step 1: Write tests**

Create `tests/test_availability.py`:

```python
from datetime import date
from unittest.mock import MagicMock, patch
from core.availability import check_availability
from db.models import Scan


def make_scan(**kwargs):
    defaults = dict(
        provider="RecreationDotGov",
        rec_area_ids=[1076],
        campground_ids=None,
        campsite_ids=None,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        nights=3,
        weekends_only=False,
        days_of_week=None,
    )
    defaults.update(kwargs)
    scan = MagicMock(spec=Scan)
    for k, v in defaults.items():
        setattr(scan, k, v)
    return scan


def test_returns_list_of_sites(mocker):
    mock_site = MagicMock()
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [mock_site]
    mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    scan = make_scan()
    result = check_availability(scan)

    assert result == [mock_site]
    mock_search.get_matching_campsites.assert_called_once_with(continuous=False)


def test_returns_empty_list_when_no_sites(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    scan = make_scan()
    result = check_availability(scan)
    assert result == []


def test_multiple_search_windows_passed(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = mocker.patch("core.availability.SearchRecreationDotGov", return_value=mock_search)

    scan = make_scan(search_windows=[
        {"start_date": "2026-07-03", "end_date": "2026-07-06"},
        {"start_date": "2026-07-10", "end_date": "2026-07-13"},
    ])
    check_availability(scan)

    call_kwargs = mock_cls.call_args.kwargs
    assert len(call_kwargs["search_window"]) == 2


def test_unsupported_provider_raises(mocker):
    import pytest
    scan = make_scan(provider="UnknownProvider")
    with pytest.raises(ValueError, match="Unsupported provider"):
        check_availability(scan)
```

- [ ] **Step 2: Run tests to verify they fail**

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

    kwargs = dict(
        search_window=windows,
        nights=scan.nights,
        weekends_only=scan.weekends_only,
    )
    if scan.rec_area_ids:
        kwargs["recreation_area"] = scan.rec_area_ids
    if scan.campground_ids:
        kwargs["campgrounds"] = scan.campground_ids
    if scan.campsite_ids:
        kwargs["campsites"] = scan.campsite_ids
    if scan.days_of_week:
        kwargs["days_of_the_week"] = scan.days_of_week

    search = cls(**kwargs)
    sites = search.get_matching_campsites(continuous=False)
    logger.info("Scan %s found %d site(s)", getattr(scan, "id", "?"), len(sites))
    return sites
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_availability.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add core/availability.py tests/test_availability.py
git commit -m "feat: camply availability wrapper"
```

---

## Task 6: Notifier

**Files:**
- Create: `core/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write tests**

Create `tests/test_notifier.py`:

```python
import smtplib
from datetime import date
from unittest.mock import MagicMock, patch, call
from core.notifier import NotificationPayload, send_email, send_telegram, notify
from config.settings import Settings


def make_settings(**kwargs):
    defaults = dict(
        encryption_key="key",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="from@example.com",
        smtp_password="pass",
        smtp_from="CampBuddy <from@example.com>",
        telegram_bot_token="bot123:token",
        playwright_service_url="http://playwright:8001",
        database_url="sqlite:///:memory:",
    )
    defaults.update(kwargs)
    s = MagicMock(spec=Settings)
    for k, v in defaults.items():
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


def test_send_email_cart_added(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    settings = make_settings()

    send_email("to@example.com", make_payload(cart_added=True), settings)

    instance.sendmail.assert_called_once()
    args = instance.sendmail.call_args[0]
    assert "Added to cart" in args[2]
    assert "https://www.recreation.gov/camping/campsites/10357088" in args[2]


def test_send_email_cart_failed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    settings = make_settings()

    send_email("to@example.com", make_payload(cart_added=False), settings)

    args = instance.sendmail.call_args[0]
    assert "book manually" in args[2].lower()
    assert "https://www.recreation.gov/camping/campsites/10357088" in args[2]


def test_send_telegram(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    settings = make_settings()

    send_telegram("123456789", make_payload(cart_added=True), settings)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    text = call_kwargs["json"]["text"]
    assert "Union West" in text
    assert "https://www.recreation.gov/camping/campsites/10357088" in text


def test_notify_dispatches_based_on_scan_prefs(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_telegram = mocker.patch("core.notifier.send_telegram")
    settings = make_settings()

    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user = MagicMock()
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = "123456"

    notify(scan, make_payload(), settings)

    mock_email.assert_called_once()
    mock_telegram.assert_called_once()


def test_notify_skips_telegram_when_no_chat_id(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_telegram = mocker.patch("core.notifier.send_telegram")
    settings = make_settings()

    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user = MagicMock()
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = None

    notify(scan, make_payload(), settings)

    mock_email.assert_called_once()
    mock_telegram.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

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


def _format_dates(payload: NotificationPayload) -> str:
    fmt = "%b %-d"
    return f"{payload.booking_date.strftime(fmt)} – {payload.booking_end_date.strftime(fmt)}"


def _cart_status_email(cart_added: bool) -> str:
    if cart_added:
        return "Added to cart — complete payment within ~15 min"
    return "Could not add to cart automatically — book manually now"


def _cart_status_telegram(cart_added: bool) -> str:
    if cart_added:
        return "✅ Added to cart — complete payment within ~15 min"
    return "⚠️ Could not add to cart automatically — book manually now"


def send_email(to: str, payload: NotificationPayload, settings) -> None:
    dates = _format_dates(payload)
    subject = f"Campsite available — {payload.facility_name} [{dates}]"

    body = (
        f"Site:   {payload.facility_name} — Site {payload.site_name} ({payload.campsite_type})\n"
        f"Dates:  {dates} ({payload.nights} nights)\n"
        f"Status: {_cart_status_email(payload.cart_added)}\n\n"
        f"Book here: {payload.booking_url}\n"
    )

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())

    logger.info("Email sent to %s for %s", to, payload.facility_name)


def send_telegram(chat_id: str, payload: NotificationPayload, settings) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured, skipping")
        return

    dates = _format_dates(payload)
    text = (
        f"🏕 Campsite available!\n"
        f"{payload.facility_name} — Site {payload.site_name}\n"
        f"{dates} ({payload.nights} nights) · {payload.campsite_type}\n\n"
        f"{_cart_status_telegram(payload.cart_added)}\n"
        f"🔗 {payload.booking_url}"
    )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    if not resp.ok:
        logger.error("Telegram send failed: %s", resp.text)
    else:
        logger.info("Telegram message sent to %s", chat_id)


def notify(scan, payload: NotificationPayload, settings) -> None:
    if scan.notify_via_email and scan.user.email:
        try:
            send_email(scan.user.email, payload, settings)
        except Exception as e:
            logger.error("Email notification failed: %s", e)

    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram(scan.user.telegram_chat_id, payload, settings)
        except Exception as e:
            logger.error("Telegram notification failed: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifier.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add core/notifier.py tests/test_notifier.py
git commit -m "feat: email and Telegram notifier"
```

---

## Task 7: Playwright Sidecar Service

**Files:**
- Create: `playwright_service/browser.py`
- Create: `playwright_service/main.py`
- Create: `playwright_service/Dockerfile`

Note: No unit tests for browser.py — it drives a real browser against a live site. Integration is validated manually (Task 13). The FastAPI app is thin enough that tests would just mock Playwright itself.

- [ ] **Step 1: Implement `playwright_service/browser.py`**

```python
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.recreation.gov/login"
CART_BUTTON_SELECTOR = "button[data-component='book-campsite'], button:has-text('Add to Cart'), button:has-text('Book Now')"
LOGIN_EMAIL_SELECTOR = "input[name='email'], input[type='email']"
LOGIN_PASSWORD_SELECTOR = "input[name='password'], input[type='password']"
LOGIN_SUBMIT_SELECTOR = "button[type='submit']:has-text('Log In'), button:has-text('Sign In')"


def add_to_cart(booking_url: str, email: str, password: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Log in first
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            page.fill(LOGIN_EMAIL_SELECTOR, email)
            page.fill(LOGIN_PASSWORD_SELECTOR, password)
            page.click(LOGIN_SUBMIT_SELECTOR)
            page.wait_for_url(lambda url: "login" not in url, timeout=15_000)

            # Navigate to campsite
            page.goto(booking_url, wait_until="networkidle", timeout=30_000)

            # Click add-to-cart / book now
            page.wait_for_selector(CART_BUTTON_SELECTOR, timeout=10_000)
            page.click(CART_BUTTON_SELECTOR)
            page.wait_for_timeout(3_000)

            # Confirm we reached cart or checkout page
            if "cart" in page.url or "checkout" in page.url:
                logger.info("Successfully added to cart: %s", booking_url)
                return {"success": True}

            logger.warning("Cart page not reached after click, URL: %s", page.url)
            return {"success": False, "error": "Cart page not reached"}

        except PlaywrightTimeout as e:
            logger.error("Timeout during cart add: %s", e)
            return {"success": False, "error": f"Timeout: {e}"}
        except Exception as e:
            logger.error("Unexpected error during cart add: %s", e)
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
    result = add_to_cart(req.booking_url, req.email, req.password)
    return CartResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

- [ ] **Step 3: Create `playwright_service/Dockerfile`**

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY playwright_service/requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium
COPY playwright_service/ ./playwright_service/
COPY playwright_service/__init__.py ./playwright_service/
CMD ["python", "-m", "playwright_service.main"]
```

- [ ] **Step 4: Verify the service starts locally**

```bash
cd /path/to/campbuddy
pip install playwright==1.44.0 fastapi==0.111.0 uvicorn==0.29.0
playwright install chromium
python -m playwright_service.main &
curl http://localhost:8001/health
```

Expected: `{"status":"ok"}`

```bash
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add playwright_service/browser.py playwright_service/main.py playwright_service/Dockerfile
git commit -m "feat: Playwright add-to-cart sidecar service"
```

---

## Task 8: Booking Client

**Files:**
- Create: `core/booking.py`
- Create: `tests/test_booking.py`

- [ ] **Step 1: Write tests**

Create `tests/test_booking.py`:

```python
import pytest
import httpx
from unittest.mock import MagicMock, patch
from core.booking import attempt_cart_add


def make_settings(url="http://playwright:8001"):
    s = MagicMock()
    s.playwright_service_url = url
    return s


def test_returns_true_on_success(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    result = attempt_cart_add(
        booking_url="https://www.recreation.gov/camping/campsites/123",
        email="user@example.com",
        password="secret",
        settings=make_settings(),
    )
    assert result is True


def test_returns_false_on_service_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": False, "error": "Login failed"})
    )
    result = attempt_cart_add(
        booking_url="https://www.recreation.gov/camping/campsites/123",
        email="user@example.com",
        password="secret",
        settings=make_settings(),
    )
    assert result is False


def test_returns_false_on_http_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(500)
    )
    result = attempt_cart_add(
        booking_url="https://www.recreation.gov/camping/campsites/123",
        email="user@example.com",
        password="secret",
        settings=make_settings(),
    )
    assert result is False


def test_returns_false_on_connection_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = attempt_cart_add(
        booking_url="https://www.recreation.gov/camping/campsites/123",
        email="user@example.com",
        password="secret",
        settings=make_settings(),
    )
    assert result is False
```

- [ ] **Step 2: Install respx for HTTP mocking**

```bash
pip install respx==0.21.1
echo "respx==0.21.1" >> requirements.txt
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_booking.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.booking'`

- [ ] **Step 4: Implement `core/booking.py`**

```python
import logging
import httpx

logger = logging.getLogger(__name__)


def attempt_cart_add(booking_url: str, email: str, password: str, settings) -> bool:
    url = f"{settings.playwright_service_url}/add-to-cart"
    try:
        resp = httpx.post(
            url,
            json={"booking_url": booking_url, "email": email, "password": password},
            timeout=60.0,
        )
        if not resp.is_success:
            logger.error("Playwright service returned %d", resp.status_code)
            return False
        data = resp.json()
        if not data.get("success"):
            logger.warning("Cart add failed: %s", data.get("error"))
        return bool(data.get("success"))
    except httpx.HTTPError as e:
        logger.error("HTTP error calling playwright service: %s", e)
        return False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_booking.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add core/booking.py tests/test_booking.py requirements.txt
git commit -m "feat: booking client for playwright sidecar"
```

---

## Task 9: Scan Runner

**Files:**
- Create: `core/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write tests**

Create `tests/test_runner.py`:

```python
import pytest
from datetime import datetime, date
from unittest.mock import MagicMock, patch, call
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from db.models import Base, User, Scan, ScanRun, ScanResult
from core.runner import run_scan
from core.notifier import NotificationPayload


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session


@pytest.fixture
def settings():
    s = MagicMock()
    s.encryption_key = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ="
    s.playwright_service_url = "http://playwright:8001"
    return s


@pytest.fixture
def scan_in_db(db):
    user = User(
        email="test@example.com",
        recreationgov_email="rg@example.com",
        recreationgov_password=None,
    )
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        provider="RecreationDotGov",
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
    return scan


def make_site(campsite_id="10357088", booking_date=date(2026, 7, 3)):
    site = MagicMock()
    site.campsite_id = campsite_id
    site.facility_name = "Union West"
    site.campsite_site_name = "1"
    site.campsite_type = "STANDARD NONELECTRIC"
    site.booking_date = datetime.combine(booking_date, datetime.min.time())
    site.booking_end_date = datetime.combine(date(2026, 7, 6), datetime.min.time())
    site.booking_url = f"https://www.recreation.gov/camping/campsites/{campsite_id}"
    site.booking_nights = 3
    return site


def test_run_writes_scan_run_on_no_results(db, scan_in_db, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[])
    factory = sessionmaker(bind=db.get_bind())
    run_scan(scan_in_db.id, factory, settings)

    run = db.query(ScanRun).filter(ScanRun.scan_id == scan_in_db.id).first()
    assert run is not None
    assert run.outcome == "no_results"
    assert run.sites_found == 0


def test_run_writes_scan_run_on_error(db, scan_in_db, settings, mocker):
    mocker.patch("core.runner.check_availability", side_effect=RuntimeError("boom"))
    factory = sessionmaker(bind=db.get_bind())
    run_scan(scan_in_db.id, factory, settings)

    run = db.query(ScanRun).filter(ScanRun.scan_id == scan_in_db.id).first()
    assert run is not None
    assert run.outcome == "error"
    assert "boom" in run.error_message


def test_run_saves_result_and_notifies(db, scan_in_db, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mock_notify = mocker.patch("core.runner.notify")
    factory = sessionmaker(bind=db.get_bind())

    run_scan(scan_in_db.id, factory, settings)

    result = db.query(ScanResult).filter(ScanResult.scan_id == scan_in_db.id).first()
    assert result is not None
    assert result.cart_added is True
    assert result.notified is True
    mock_notify.assert_called_once()


def test_dedup_skips_already_seen_site(db, scan_in_db, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mock_notify = mocker.patch("core.runner.notify")
    factory = sessionmaker(bind=db.get_bind())

    # Run twice
    run_scan(scan_in_db.id, factory, settings)
    run_scan(scan_in_db.id, factory, settings)

    # notify_on_new_only=True so second run should not notify again
    assert mock_notify.call_count == 1


def test_dedup_notifies_same_site_different_date(db, scan_in_db, settings, mocker):
    site_a = make_site(campsite_id="10357088", booking_date=date(2026, 7, 3))
    site_b = make_site(campsite_id="10357088", booking_date=date(2026, 7, 10))
    mocker.patch("core.runner.check_availability", side_effect=[[site_a], [site_b]])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    factory = sessionmaker(bind=db.get_bind())

    run_scan(scan_in_db.id, factory, settings)
    run_scan(scan_in_db.id, factory, settings)

    # Different dates — both should notify
    assert mock_notify.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_runner.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.runner'`

- [ ] **Step 3: Implement `core/runner.py`**

```python
import logging
from datetime import datetime, date
from sqlalchemy.orm import sessionmaker
from db.models import Scan, ScanRun, ScanResult, User
from core.availability import check_availability
from core.booking import attempt_cart_add
from core.crypto import decrypt_password
from core.notifier import notify, NotificationPayload

logger = logging.getLogger(__name__)


def run_scan(scan_id: int, session_factory: sessionmaker, settings) -> None:
    with session_factory() as db:
        scan = (
            db.query(Scan)
            .filter(Scan.id == scan_id, Scan.status == "active")
            .first()
        )
        if not scan:
            logger.warning("Scan %d not found or not active", scan_id)
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
                    existing = (
                        db.query(ScanResult)
                        .filter(
                            ScanResult.scan_id == scan_id,
                            ScanResult.campsite_id == str(site.campsite_id),
                            ScanResult.booking_date == booking_date,
                        )
                        .first()
                    )
                    if existing:
                        logger.debug("Skipping already-seen site %s on %s", site.campsite_id, booking_date)
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
                        password = decrypt_password(user.recreationgov_password, settings.encryption_key)
                        cart_added = attempt_cart_add(
                            site.booking_url, user.recreationgov_email, password, settings
                        )
                    except Exception as e:
                        logger.error("Cart add error: %s", e)

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
                    logger.error("Notification error: %s", e)

        except Exception as e:
            logger.exception("Scan %d failed: %s", scan_id, e)
            run.outcome = "error"
            run.error_message = str(e)
            run.sites_found = 0
        finally:
            run.finished_at = datetime.utcnow()
            db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_runner.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "feat: scan runner with dedup, booking, and notifications"
```

---

## Task 10: Scheduler

**Files:**
- Create: `core/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write tests**

Create `tests/test_scheduler.py`:

```python
import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base, User, Scan
from core.scheduler import build_scheduler, sync_jobs


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def settings():
    s = MagicMock()
    s.encryption_key = "key"
    return s


def add_scan(factory, status="active", polling_interval=300):
    with factory() as db:
        user = User(email="test@example.com")
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            provider="RecreationDotGov",
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            nights=1,
            polling_interval=polling_interval,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status=status,
        )
        db.add(scan)
        db.commit()
        return scan.id


def test_sync_jobs_adds_active_scan(factory, settings):
    scan_id = add_scan(factory, status="active", polling_interval=300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, settings)
    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args[1]
    assert call_kwargs["id"] == f"scan_{scan_id}"
    assert call_kwargs["seconds"] == 300


def test_sync_jobs_skips_paused_scan(factory, settings):
    add_scan(factory, status="paused")
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, settings)
    scheduler.add_job.assert_not_called()


def test_sync_jobs_removes_job_for_deleted_scan(factory, settings):
    scan_id = add_scan(factory, status="active")
    existing_job = MagicMock()
    existing_job.id = f"scan_{scan_id + 999}"
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [existing_job]
    sync_jobs(scheduler, factory, settings)
    scheduler.remove_job.assert_called_once_with(f"scan_{scan_id + 999}")
```

- [ ] **Step 2: Run tests to verify they fail**

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
        active_scans = db.query(Scan).filter(Scan.status == "active").all()
        active_ids = {f"scan_{s.id}" for s in active_scans}

    existing_ids = {job.id for job in scheduler.get_jobs()}

    # Remove jobs for scans no longer active
    for job_id in existing_ids:
        if job_id not in active_ids:
            scheduler.remove_job(job_id)
            logger.info("Removed job %s", job_id)

    # Add jobs for new active scans
    for scan in active_scans:
        job_id = f"scan_{scan.id}"
        if job_id not in existing_ids:
            scheduler.add_job(
                run_scan,
                trigger=IntervalTrigger(seconds=scan.polling_interval),
                id=job_id,
                args=[scan.id, session_factory, settings],
                max_instances=1,
                coalesce=True,
            )
            logger.info("Scheduled job %s every %ds", job_id, scan.polling_interval)


def start_scheduler(session_factory, settings) -> BackgroundScheduler:
    scheduler = build_scheduler()
    sync_jobs(scheduler, session_factory, settings)

    # Periodically re-sync to pick up new/paused scans
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(seconds=60),
        id="sync_jobs",
        args=[scheduler, session_factory, settings],
    )

    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scheduler.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: APScheduler job management"
```

---

## Task 11: CLI and YAML Seeder

**Files:**
- Create: `cli.py`
- Create: `config/scans.yaml`

- [ ] **Step 1: Create example `config/scans.yaml`**

```yaml
users:
  - email: you@example.com
    telegram_chat_id: "123456789"      # optional — leave empty string to disable
    recreationgov_email: you@example.com
    recreationgov_password: your-plaintext-password  # encrypted when seeded

scans:
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 300              # seconds
    rec_area_ids: [1076, 2991]
    search_windows:
      - start_date: "2026-07-03"
        end_date: "2026-07-06"
    nights: 3
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true

  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 600
    rec_area_ids: [2991]
    search_windows:
      - start_date: "2026-07-12"
        end_date: "2026-07-13"
      - start_date: "2026-07-19"
        end_date: "2026-07-20"
    nights: 1
    notify_via_email: true
    notify_via_telegram: true
    notify_on_new_only: true
```

- [ ] **Step 2: Implement `cli.py`**

```python
import os
import sys
import yaml
import click
import logging
from sqlalchemy.orm import sessionmaker
from db.models import User, Scan, ScanRun, ScanResult
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
    """CampBuddy CLI — manage scans and users."""


@cli.command()
@click.argument("yaml_path", default="config/scans.yaml")
def seed(yaml_path: str):
    """Seed users and scans from a YAML file."""
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
                user.telegram_chat_id = u["telegram_chat_id"]
            if u.get("recreationgov_email"):
                user.recreationgov_email = u["recreationgov_email"]
            if u.get("recreationgov_password"):
                user.recreationgov_password = encrypt_password(
                    u["recreationgov_password"], settings.encryption_key
                )

        db.flush()

        for s in data.get("scans", []):
            user = db.query(User).filter(User.email == s["user_email"]).first()
            if not user:
                logger.error("User %s not found for scan", s["user_email"])
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
            logger.info("Added scan for user %s (%s)", s["user_email"], s.get("provider"))

    click.echo("Seed complete.")


@cli.command()
def list_scans():
    """List all scans and their status."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scans = db.query(Scan).join(User).all()
        if not scans:
            click.echo("No scans found.")
            return
        for s in scans:
            click.echo(
                f"[{s.id}] {s.status:8} | user={s.user.email} | {s.provider} | "
                f"interval={s.polling_interval}s | windows={len(s.search_windows)}"
            )


@cli.command()
@click.argument("scan_id", type=int)
def pause(scan_id: int):
    """Pause an active scan."""
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


@cli.command()
@click.argument("scan_id", type=int)
def delete_scan(scan_id: int):
    """Delete a scan and all its history."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        db.delete(scan)
    click.echo(f"Scan {scan_id} deleted.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 3: Verify seed works against a test DB**

```bash
cp .env.example .env
# Fill in ENCRYPTION_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
mkdir -p data
DATABASE_URL=sqlite:///./data/test.db python cli.py seed config/scans.yaml
DATABASE_URL=sqlite:///./data/test.db python cli.py list-scans
rm data/test.db
```

Expected: scan list shows the two scans from scans.yaml.

- [ ] **Step 4: Commit**

```bash
git add cli.py config/scans.yaml
git commit -m "feat: CLI seed, list, pause, resume, delete commands"
```

---

## Task 12: Main Entry Point

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


def main():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_tables(engine)
    session_factory = make_session_factory(engine)

    scheduler = start_scheduler(session_factory, settings)

    def shutdown(sig, frame):
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("CampBuddy running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests to confirm nothing is broken**

```bash
pytest tests/ -v --ignore=tests/test_settings.py
```

Expected: all tests pass (test_settings may fail without a .env file — that's expected in CI).

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point with graceful shutdown"
```

---

## Task 13: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
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

- [ ] **Step 2: Create `docker-compose.yml`**

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
      retries: 3
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

- [ ] **Step 4: Build and verify both images build cleanly**

```bash
docker compose build
```

Expected: both `app` and `playwright` images build without errors.

- [ ] **Step 5: Smoke test — seed DB and start the stack**

```bash
# Make sure .env is populated with real values
python cli.py seed config/scans.yaml
docker compose up -d
docker compose logs -f
```

Expected: logs show `CampBuddy running` and scheduled jobs firing. No import errors or crashes.

```bash
docker compose down
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: Docker setup for app and playwright sidecar"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ SQLite + SQLAlchemy models (Task 3)
- ✅ APScheduler running scans (Task 10)
- ✅ camply OO API integration (Task 5)
- ✅ Playwright add-to-cart sidecar (Task 7)
- ✅ Email notifications (Task 6)
- ✅ Telegram notifications (Task 6)
- ✅ Full run history always written (Task 9)
- ✅ Fernet-encrypted Recreation.gov password (Task 4)
- ✅ Per-scan notification prefs (Task 3)
- ✅ notify_on_new_only with campsite_id + booking_date dedup (Task 9)
- ✅ Multiple search windows (Task 5)
- ✅ scans.yaml + CLI seed (Task 11)
- ✅ Docker Compose deploy (Task 13)
- ✅ Graceful shutdown (Task 12)

**Phases 2 and 3** (web dashboard, Telegram bot) are explicitly out of scope for this plan.
