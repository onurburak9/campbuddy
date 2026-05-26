# Phase 2 Backend — REST API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI REST API and shared service layer so users can manage their scans via browser.

**Architecture:** One Docker image (`app` + `api` containers, different entry points) sharing a SQLite volume. A new `core/services/` layer holds all business logic, imported by both the API routes and the existing CLI. FastAPI sits in `api/`, wired up with session-cookie JWT auth and per-user scan limits.

**Tech Stack:** FastAPI, uvicorn, bcrypt, python-jose[cryptography], python-multipart, pydantic v1 (already pinned), SQLAlchemy 2 (already present), pytest + FastAPI TestClient.

> **Note:** The React frontend is a separate follow-on plan (`2026-05-12-phase2-frontend.md`). This plan produces a fully tested, Dockerised API that the frontend can target.

---

## File Map

### Created
| File | Responsibility |
|------|---------------|
| `core/services/__init__.py` | empty package marker |
| `core/services/exceptions.py` | domain exceptions (NotFound, Forbidden, LimitExceeded) |
| `core/services/scans.py` | scan CRUD + ownership + limit enforcement |
| `core/services/users.py` | profile reads + credential updates |
| `core/services/history.py` | paginated run + result queries |
| `api/__init__.py` | empty package marker |
| `api/database.py` | singleton session factory, init(url) for tests |
| `api/auth.py` | bcrypt helpers + JWT create/decode |
| `api/deps.py` | FastAPI dependencies: get_db_dep, get_current_user |
| `api/main.py` | FastAPI app, lifespan, router wiring |
| `api/routes/__init__.py` | empty package marker |
| `api/routes/auth.py` | POST /auth/login, POST /auth/logout, GET /auth/me |
| `api/routes/scans.py` | full scan CRUD + pause/resume + history sub-routes |
| `api/routes/users.py` | PATCH /users/me |
| `api/schemas.py` | pydantic v1 request/response models |
| `tests/services/__init__.py` | empty package marker |
| `tests/services/conftest.py` | in-memory db fixture |
| `tests/services/test_scans.py` | service layer scan tests |
| `tests/services/test_users.py` | service layer user tests |
| `tests/services/test_history.py` | service layer history tests |
| `tests/api/__init__.py` | empty package marker |
| `tests/api/conftest.py` | TestClient + seeded user fixtures |
| `tests/api/test_auth.py` | login/logout/me route tests |
| `tests/api/test_scans.py` | scan route tests |
| `tests/api/test_users.py` | profile route tests |

### Modified
| File | Change |
|------|--------|
| `db/models.py` | Add `hashed_password` (nullable str), `scan_limit` (int default 5) to `User` |
| `config/settings.py` | Add `api_secret_key: str` field |
| `cli.py` | Add `--password` and `--scan-limit` options to `update-user` |
| `requirements.txt` | Add fastapi, uvicorn[standard], passlib[bcrypt], python-jose[cryptography], python-multipart |
| `docker-compose.yml` | Add `api` service; `app` stays unchanged |
| `.env.example` | Add `API_SECRET_KEY=` entry |

---

## Task 1: Add new dependencies to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the new packages**

Open `requirements.txt` and append after the existing entries:

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
```

- [ ] **Step 2: Install them in the venv**

```bash
.venv/bin/pip install fastapi==0.111.0 "uvicorn[standard]==0.29.0" "passlib[bcrypt]==1.7.4" "python-jose[cryptography]==3.3.0" python-multipart==0.0.9
```

Expected: all packages install without conflicts. pydantic v1 remains pinned.

- [ ] **Step 3: Verify no pydantic conflict**

```bash
.venv/bin/python -c "import pydantic; print(pydantic.VERSION)"
```

Expected output: `1.10.22`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add fastapi, uvicorn, passlib, python-jose deps"
```

---

## Task 2: DB model changes — hashed_password and scan_limit

**Files:**
- Modify: `db/models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_models.py`:

```python
def test_user_has_hashed_password_and_scan_limit(db):
    user = User(email="authuser@example.com", hashed_password="somehash", scan_limit=3)
    db.add(user)
    db.commit()
    assert user.hashed_password == "somehash"
    assert user.scan_limit == 3


def test_user_scan_limit_defaults_to_five(db):
    user = User(email="defaultlimit@example.com")
    db.add(user)
    db.commit()
    assert user.scan_limit == 5


def test_user_hashed_password_nullable(db):
    user = User(email="nopassword@example.com")
    db.add(user)
    db.commit()
    assert user.hashed_password is None
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_models.py::test_user_has_hashed_password_and_scan_limit -v
```

Expected: `FAILED` — `User` has no `hashed_password` attribute.

- [ ] **Step 3: Add columns to User model**

In `db/models.py`, add two lines inside the `User` class after the `deleted_at` column:

```python
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scan_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_models.py -v
```

Expected: all model tests pass.

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_models.py
git commit -m "feat(models): add hashed_password and scan_limit to User"
```

---

## Task 3: Settings — api_secret_key

**Files:**
- Modify: `config/settings.py`
- Modify: `.env.example` (create if absent)

- [ ] **Step 1: Write failing test**

Add to `tests/test_settings.py`:

```python
def test_api_secret_key_loaded_from_env(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "my-secret")
    from config.settings import Settings
    s = Settings(
        encryption_key="ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWY=",
        smtp_user="u@e.com",
        smtp_password="pw",
        smtp_from="u@e.com",
        api_secret_key="my-secret",
    )
    assert s.api_secret_key == "my-secret"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_settings.py::test_api_secret_key_loaded_from_env -v
```

Expected: `FAILED` — `Settings` has no `api_secret_key` field.

- [ ] **Step 3: Add the field to Settings**

In `config/settings.py`, add inside the `Settings` class after `database_url`:

```python
    api_secret_key: str
```

- [ ] **Step 4: Run to verify pass**

```bash
.venv/bin/pytest tests/test_settings.py -v
```

Expected: all settings tests pass.

- [ ] **Step 5: Update .env.example**

Check if `.env.example` exists:

```bash
ls .env.example 2>/dev/null || echo "missing"
```

Add this line to `.env.example` (create the file if missing, append if existing):

```
API_SECRET_KEY=  # generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

- [ ] **Step 6: Commit**

```bash
git add config/settings.py tests/test_settings.py .env.example
git commit -m "feat(settings): add api_secret_key for JWT signing"
```

---

## Task 4: CLI — --password and --scan-limit for update-user

**Files:**
- Modify: `cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
def test_update_user_sets_hashed_password(runner, factory):
    user_id = _seed_user(factory)
    result = runner.invoke(cli, ["update-user", str(user_id), "--password", "hunter2"])
    assert result.exit_code == 0
    with factory() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.hashed_password is not None
        assert user.hashed_password != "hunter2"  # must be hashed


def test_update_user_sets_scan_limit(runner, factory):
    user_id = _seed_user(factory)
    result = runner.invoke(cli, ["update-user", str(user_id), "--scan-limit", "3"])
    assert result.exit_code == 0
    with factory() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.scan_limit == 3
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_cli.py::test_update_user_sets_hashed_password tests/test_cli.py::test_update_user_sets_scan_limit -v
```

Expected: `FAILED` — no `--password` or `--scan-limit` options.

- [ ] **Step 3: Update update-user command in cli.py**

Replace the `update_user` command definition (find it around line 198). Add the two new options and their handling:

```python
@cli.command("update-user")
@click.argument("user_id", type=int)
@click.option("--email", default=None, help="New login email address.")
@click.option("--recreationgov-email", default=None, help="Recreation.gov account email.")
@click.option("--recreationgov-password", default=None, help="Recreation.gov password (will be encrypted).")
@click.option("--clear-password", is_flag=True, help="Remove stored Recreation.gov password.")
@click.option("--telegram-chat-id", default=None, help="Telegram chat ID.")
@click.option("--password", default=None, help="Web UI login password (will be hashed).")
@click.option("--scan-limit", default=None, type=int, help="Maximum number of active scans.")
def update_user(user_id, email, recreationgov_email, recreationgov_password, clear_password, telegram_chat_id, password, scan_limit):
    """Update fields on a user row."""
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    factory, settings = get_factory()
    with get_db(factory) as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            click.echo(f"User {user_id} not found.")
            return
        if email:
            user.email = email
        if recreationgov_email:
            user.recreationgov_email = recreationgov_email
        if recreationgov_password:
            user.recreationgov_password = encrypt_password(recreationgov_password, settings.encryption_key)
        if clear_password:
            user.recreationgov_password = None
        if telegram_chat_id:
            user.telegram_chat_id = telegram_chat_id
        if password:
            user.hashed_password = _pwd.hash(password)
        if scan_limit is not None:
            user.scan_limit = scan_limit
        click.echo(f"User {user_id} updated: email={user.email} rec_email={user.recreationgov_email} "
                   f"password={'set' if user.recreationgov_password else 'none'} "
                   f"telegram={user.telegram_chat_id} "
                   f"scan_limit={user.scan_limit}")
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

Expected: all CLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat(cli): add --password and --scan-limit to update-user"
```

---

## Task 5: Service layer — exceptions + scans service

**Files:**
- Create: `core/services/__init__.py`
- Create: `core/services/exceptions.py`
- Create: `core/services/scans.py`
- Create: `tests/services/__init__.py`
- Create: `tests/services/conftest.py`
- Create: `tests/services/test_scans.py`

- [ ] **Step 1: Create package files**

Create `core/services/__init__.py` — empty file.
Create `tests/services/__init__.py` — empty file.

- [ ] **Step 2: Create exceptions.py**

Create `core/services/exceptions.py`:

```python
class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


class LimitExceeded(Exception):
    pass
```

- [ ] **Step 3: Create tests/services/conftest.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Base, User
from db.session import make_session_factory, get_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def make_user(db, email="u@e.com", scan_limit=5, hashed_password=None):
    user = User(email=email, scan_limit=scan_limit, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user
```

- [ ] **Step 4: Write failing tests for scans service**

Create `tests/services/test_scans.py`:

```python
import pytest
from datetime import datetime, timezone
from db.models import Scan, ScanStatus
from core.services.scans import (
    list_scans,
    get_scan,
    create_scan,
    update_scan,
    delete_scan,
    pause_scan,
    resume_scan,
)
from core.services.exceptions import NotFound, Forbidden, LimitExceeded
from tests.services.conftest import make_user


WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def test_list_scans_returns_only_owners_scans(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    assert len(list_scans(db, u1.id)) == 1
    assert len(list_scans(db, u2.id)) == 0


def test_list_scans_excludes_soft_deleted(db):
    from datetime import timezone
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    scan.deleted_at = datetime.now(timezone.utc)
    db.flush()
    assert list_scans(db, u.id) == []


def test_get_scan_raises_not_found_for_missing(db):
    u = make_user(db)
    with pytest.raises(NotFound):
        get_scan(db, 9999, u.id)


def test_get_scan_raises_forbidden_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(Forbidden):
        get_scan(db, scan.id, u2.id)


def test_create_scan_returns_scan(db):
    u = make_user(db, scan_limit=5)
    data = {"search_windows": WINDOWS, "nights": 2}
    scan = create_scan(db, u.id, data)
    assert scan.id is not None
    assert scan.user_id == u.id
    assert scan.nights == 2


def test_create_scan_raises_limit_exceeded(db):
    u = make_user(db, scan_limit=2)
    for _ in range(2):
        Scan(user_id=u.id, search_windows=WINDOWS)
        s = Scan(user_id=u.id, search_windows=WINDOWS)
        db.add(s)
    db.flush()
    with pytest.raises(LimitExceeded):
        create_scan(db, u.id, {"search_windows": WINDOWS})


def test_create_scan_soft_deleted_not_counted_against_limit(db):
    u = make_user(db, scan_limit=1)
    s = Scan(user_id=u.id, search_windows=WINDOWS,
             deleted_at=datetime.now(timezone.utc))
    db.add(s)
    db.flush()
    scan = create_scan(db, u.id, {"search_windows": WINDOWS})
    assert scan.id is not None


def test_update_scan_changes_fields(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, nights=1)
    db.add(scan)
    db.flush()
    updated = update_scan(db, scan.id, u.id, {"nights": 3, "name": "Yosemite"})
    assert updated.nights == 3
    assert updated.name == "Yosemite"


def test_delete_scan_soft_deletes(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    delete_scan(db, scan.id, u.id)
    db.flush()
    assert scan.deleted_at is not None


def test_pause_scan_sets_status(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.active)
    db.add(scan)
    db.flush()
    result = pause_scan(db, scan.id, u.id)
    assert result.status == ScanStatus.paused


def test_resume_scan_sets_status(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.paused)
    db.add(scan)
    db.flush()
    result = resume_scan(db, scan.id, u.id)
    assert result.status == ScanStatus.active
```

- [ ] **Step 5: Run to verify failure**

```bash
.venv/bin/pytest tests/services/test_scans.py -v
```

Expected: `FAILED` — `core.services.scans` module not found.

- [ ] **Step 6: Implement core/services/scans.py**

Create `core/services/scans.py`:

```python
from datetime import datetime, timezone
from db.models import Scan, ScanStatus, User
from core.services.exceptions import NotFound, Forbidden, LimitExceeded


def _now():
    return datetime.now(timezone.utc)


def list_scans(db, user_id: int) -> list:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .order_by(Scan.created_at.desc())
        .all()
    )


def get_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.deleted_at.is_(None)).first()
    if not scan:
        raise NotFound(f"Scan {scan_id} not found")
    if scan.user_id != user_id:
        raise Forbidden(f"Scan {scan_id} belongs to another user")
    return scan


def create_scan(db, user_id: int, data: dict) -> Scan:
    user = db.query(User).filter(User.id == user_id).first()
    active_count = (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )
    if active_count >= user.scan_limit:
        raise LimitExceeded(f"Scan limit of {user.scan_limit} reached")
    scan = Scan(user_id=user_id, **data)
    db.add(scan)
    db.flush()
    return scan


def update_scan(db, scan_id: int, user_id: int, data: dict) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    for key, value in data.items():
        setattr(scan, key, value)
    db.flush()
    return scan


def delete_scan(db, scan_id: int, user_id: int) -> None:
    scan = get_scan(db, scan_id, user_id)
    scan.deleted_at = _now()
    db.flush()


def pause_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    scan.status = ScanStatus.paused
    db.flush()
    return scan


def resume_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    scan.status = ScanStatus.active
    db.flush()
    return scan
```

- [ ] **Step 7: Run tests**

```bash
.venv/bin/pytest tests/services/test_scans.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add core/services/ tests/services/
git commit -m "feat(services): scan service — CRUD, ownership, scan limit"
```

---

## Task 6: Service layer — users and history

**Files:**
- Create: `core/services/users.py`
- Create: `core/services/history.py`
- Create: `tests/services/test_users.py`
- Create: `tests/services/test_history.py`

- [ ] **Step 1: Write failing tests for users service**

Create `tests/services/test_users.py`:

```python
import pytest
from db.models import User, Scan
from core.services.users import get_user_by_email, update_profile, scans_used
from core.services.exceptions import NotFound
from tests.services.conftest import make_user

ENCRYPTION_KEY = "ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWY="
WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def test_get_user_by_email_returns_user(db):
    u = make_user(db, "find@e.com")
    result = get_user_by_email(db, "find@e.com")
    assert result.id == u.id


def test_get_user_by_email_raises_not_found(db):
    with pytest.raises(NotFound):
        get_user_by_email(db, "ghost@e.com")


def test_update_profile_changes_email(db):
    u = make_user(db, "old@e.com")
    result = update_profile(db, u.id, {"email": "new@e.com"}, ENCRYPTION_KEY)
    assert result.email == "new@e.com"


def test_update_profile_encrypts_recreationgov_password(db):
    u = make_user(db)
    result = update_profile(db, u.id, {"recreationgov_password": "s3cr3t"}, ENCRYPTION_KEY)
    assert result.recreationgov_password is not None
    assert result.recreationgov_password != "s3cr3t"


def test_scans_used_counts_only_active(db):
    from datetime import datetime, timezone
    u = make_user(db)
    s1 = Scan(user_id=u.id, search_windows=WINDOWS)
    s2 = Scan(user_id=u.id, search_windows=WINDOWS)
    s3 = Scan(user_id=u.id, search_windows=WINDOWS,
              deleted_at=datetime.now(timezone.utc))
    db.add_all([s1, s2, s3])
    db.flush()
    assert scans_used(db, u.id) == 2
```

- [ ] **Step 2: Write failing tests for history service**

Create `tests/services/test_history.py`:

```python
import pytest
from datetime import datetime, date, timezone
from db.models import Scan, ScanRun, ScanResult, ScanOutcome
from core.services.history import list_runs, list_results
from core.services.exceptions import Forbidden
from tests.services.conftest import make_user

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _make_run(db, scan_id):
    run = ScanRun(
        scan_id=scan_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        outcome=ScanOutcome.success,
        sites_found=1,
    )
    db.add(run)
    db.flush()
    return run


def _make_result(db, scan_id, run_id):
    r = ScanResult(
        scan_run_id=run_id,
        scan_id=scan_id,
        campsite_id="1",
        facility_name="F",
        site_name="S",
        campsite_type="T",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://example.com",
        first_seen_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.flush()
    return r


def test_list_runs_returns_runs_for_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    _make_run(db, scan.id)
    _make_run(db, scan.id)
    runs = list_runs(db, scan.id, u.id, page=1, page_size=10)
    assert len(runs) == 2


def test_list_runs_raises_forbidden_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(Forbidden):
        list_runs(db, scan.id, u2.id)


def test_list_runs_paginates(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    for _ in range(5):
        _make_run(db, scan.id)
    page1 = list_runs(db, scan.id, u.id, page=1, page_size=3)
    page2 = list_runs(db, scan.id, u.id, page=2, page_size=3)
    assert len(page1) == 3
    assert len(page2) == 2


def test_list_results_returns_results_for_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    _make_result(db, scan.id, run.id)
    results = list_results(db, scan.id, u.id, page=1, page_size=10)
    assert len(results) == 1
```

- [ ] **Step 3: Run to verify failure**

```bash
.venv/bin/pytest tests/services/test_users.py tests/services/test_history.py -v
```

Expected: `FAILED` — modules not found.

- [ ] **Step 4: Implement core/services/users.py**

Create `core/services/users.py`:

```python
from db.models import User, Scan
from core.services.exceptions import NotFound
from core.crypto import encrypt_password


def get_user_by_email(db, email: str) -> User:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound(f"User {email} not found")
    return user


def update_profile(db, user_id: int, data: dict, encryption_key: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    allowed = {"email", "telegram_chat_id", "recreationgov_email", "recreationgov_password"}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "recreationgov_password":
            user.recreationgov_password = encrypt_password(value, encryption_key)
        else:
            setattr(user, key, value)
    db.flush()
    return user


def scans_used(db, user_id: int) -> int:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )
```

- [ ] **Step 5: Implement core/services/history.py**

Create `core/services/history.py`:

```python
from db.models import ScanRun, ScanResult
from core.services.scans import get_scan


def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20) -> list:
    get_scan(db, scan_id, user_id)
    return (
        db.query(ScanRun)
        .filter(ScanRun.scan_id == scan_id)
        .order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def list_results(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20) -> list:
    get_scan(db, scan_id, user_id)
    return (
        db.query(ScanResult)
        .filter(ScanResult.scan_id == scan_id)
        .order_by(ScanResult.first_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
```

- [ ] **Step 6: Run all service tests**

```bash
.venv/bin/pytest tests/services/ -v
```

Expected: all 20+ service tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/services/users.py core/services/history.py tests/services/test_users.py tests/services/test_history.py
git commit -m "feat(services): users and history services"
```

---

## Task 7: API foundation — database singleton, auth helpers, deps

**Files:**
- Create: `api/__init__.py`
- Create: `api/database.py`
- Create: `api/auth.py`
- Create: `api/deps.py`

- [ ] **Step 1: Create api/__init__.py**

Empty file.

- [ ] **Step 2: Create api/database.py**

```python
from db.session import make_engine, create_tables, make_session_factory

_factory = None


def init(database_url: str = None) -> None:
    global _factory
    if database_url is None:
        from config.settings import get_settings
        database_url = get_settings().database_url
    engine = make_engine(database_url)
    create_tables(engine)
    _factory = make_session_factory(engine)


def get_factory():
    return _factory
```

- [ ] **Step 3: Create api/auth.py**

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError

ALGORITHM = "HS256"
EXPIRE_HOURS = 24
COOKIE_NAME = "campbuddy_session"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: int, secret_key: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret_key, algorithm=ALGORITHM)


def decode_token(token: str, secret_key: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None
```

- [ ] **Step 4: Create api/deps.py**

```python
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from api.auth import decode_token, COOKIE_NAME
from api.database import get_factory
from config.settings import get_settings
from db.models import User
from db.session import get_db


def get_db_dep():
    with get_db(get_factory()) as db:
        yield db


def get_current_user(
    db: Session = Depends(get_db_dep),
    campbuddy_session: Optional[str] = Cookie(default=None),
) -> User:
    if not campbuddy_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    settings = get_settings()
    user_id = decode_token(campbuddy_session, settings.api_secret_key)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
```

- [ ] **Step 5: Commit**

```bash
git add api/ 
git commit -m "feat(api): database singleton, auth helpers, deps"
```

---

## Task 8: API schemas

**Files:**
- Create: `api/schemas.py`

- [ ] **Step 1: Create api/schemas.py**

```python
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class MeResponse(BaseModel):
    id: int
    email: str
    scan_limit: int
    scans_used: int

    class Config:
        orm_mode = True


class ScanCreate(BaseModel):
    provider: str = "RecreationDotGov"
    name: Optional[str] = None
    polling_interval: int = 300
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: List[dict]
    nights: int = 1
    days_of_week: Optional[List[int]] = None
    weekends_only: bool = False
    notify_via_email: bool = True
    notify_via_telegram: bool = False
    notify_on_new_only: bool = True


class ScanUpdate(BaseModel):
    name: Optional[str] = None
    polling_interval: Optional[int] = None
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: Optional[List[dict]] = None
    nights: Optional[int] = None
    days_of_week: Optional[List[int]] = None
    weekends_only: Optional[bool] = None
    notify_via_email: Optional[bool] = None
    notify_via_telegram: Optional[bool] = None
    notify_on_new_only: Optional[bool] = None


class ScanResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    name: Optional[str]
    status: str
    polling_interval: int
    rec_area_ids: Optional[List[int]]
    campground_ids: Optional[List[int]]
    campsite_ids: Optional[List[int]]
    search_windows: List[dict]
    nights: int
    days_of_week: Optional[List[int]]
    weekends_only: bool
    notify_via_email: bool
    notify_via_telegram: bool
    notify_on_new_only: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ScanRunResponse(BaseModel):
    id: int
    scan_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    outcome: Optional[str]
    sites_found: int
    error_message: Optional[str]

    class Config:
        orm_mode = True


class ScanResultResponse(BaseModel):
    id: int
    scan_id: int
    campsite_id: str
    facility_name: str
    site_name: str
    campsite_type: str
    booking_date: date
    booking_end_date: date
    booking_url: str
    first_seen_at: datetime
    cart_added: bool
    notified: bool

    class Config:
        orm_mode = True


class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    recreationgov_email: Optional[str] = None
    recreationgov_password: Optional[str] = None
```

- [ ] **Step 2: Commit**

```bash
git add api/schemas.py
git commit -m "feat(api): pydantic v1 request/response schemas"
```

---

## Task 9: API routes — auth

**Files:**
- Create: `api/routes/__init__.py`
- Create: `api/routes/auth.py`
- Create: `api/main.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/conftest.py`
- Create: `tests/api/test_auth.py`

- [ ] **Step 1: Create api/routes/__init__.py**

Empty file.

- [ ] **Step 2: Create api/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import database as api_db
from api.routes import auth, scans, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_db.init()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
```

- [ ] **Step 3: Create api/routes/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, create_token, COOKIE_NAME
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, scans_used
from core.services.exceptions import NotFound

router = APIRouter()


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db_dep)):
    try:
        user = get_user_by_email(db, body.email)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    settings = get_settings()
    token = create_token(user.id, settings.api_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        email=user.email,
        scan_limit=user.scan_limit,
        scans_used=scans_used(db, user.id),
    )
```

- [ ] **Step 4: Create stub files for scans and users routes** (needed so main.py imports work)

Create `api/routes/scans.py`:

```python
from fastapi import APIRouter
router = APIRouter()
```

Create `api/routes/users.py`:

```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 5: Create tests/api/__init__.py**

Empty file.

- [ ] **Step 6: Create tests/api/conftest.py**

```python
import os
import pytest
from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from db.models import Base, User
from db.session import make_session_factory, get_db
from api.main import app
import api.database as api_db
from api.auth import hash_password

os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-unit-tests-32ch")
os.environ.setdefault("ENCRYPTION_KEY", "ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWY=")
os.environ.setdefault("SMTP_USER", "t@e.com")
os.environ.setdefault("SMTP_PASSWORD", "pw")
os.environ.setdefault("SMTP_FROM", "t@e.com")


@pytest.fixture(autouse=True)
def setup_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    api_db._factory = make_session_factory(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def user_in_db():
    with get_db(api_db.get_factory()) as db:
        user = User(
            email="user@example.com",
            hashed_password=hash_password("password123"),
            scan_limit=5,
        )
        db.add(user)
        db.flush()
        return {"id": user.id, "email": user.email}


@pytest.fixture
def auth_client(client, user_in_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    return client, user_in_db
```

- [ ] **Step 7: Write failing tests for auth routes**

Create `tests/api/test_auth.py`:

```python
import pytest
from db.models import User
import api.database as api_db
from db.session import get_db
from api.auth import hash_password


def test_login_sets_cookie(client, user_in_db):
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies


def test_login_wrong_password_returns_401(client, user_in_db):
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "pw"})
    assert resp.status_code == 401


def test_login_user_with_no_password_returns_401(client):
    with get_db(api_db.get_factory()) as db:
        user = User(email="nopass@example.com")
        db.add(user)
    resp = client.post("/api/v1/auth/login", json={"email": "nopass@example.com", "password": "anything"})
    assert resp.status_code == 401


def test_logout_clears_cookie(client, user_in_db):
    client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200


def test_me_returns_user_info(auth_client):
    client, user_info = auth_client
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["scan_limit"] == 5
    assert data["scans_used"] == 0


def test_me_returns_401_without_cookie(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
```

- [ ] **Step 8: Run to verify failure**

```bash
.venv/bin/pytest tests/api/test_auth.py -v
```

Expected: some tests pass, some fail depending on import errors. Fix any import issues before proceeding.

- [ ] **Step 9: Run auth tests**

```bash
.venv/bin/pytest tests/api/test_auth.py -v
```

Expected: all 7 auth tests pass.

- [ ] **Step 10: Commit**

```bash
git add api/ tests/api/
git commit -m "feat(api): auth routes — login, logout, me"
```

---

## Task 10: API routes — scans

**Files:**
- Modify: `api/routes/scans.py`
- Create: `tests/api/test_scans.py`

- [ ] **Step 1: Write failing scan route tests**

Create `tests/api/test_scans.py`:

```python
import pytest
from db.models import Scan, User
from db.session import get_db
import api.database as api_db
from api.auth import hash_password

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _make_scan(user_id, **kwargs):
    with get_db(api_db.get_factory()) as db:
        scan = Scan(user_id=user_id, search_windows=WINDOWS, **kwargs)
        db.add(scan)
        db.flush()
        return scan.id


def test_list_scans_returns_empty_for_new_user(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/scans")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_scan_returns_201(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "nights": 2})
    assert resp.status_code == 201
    data = resp.json()
    assert data["nights"] == 2
    assert data["status"] == "active"


def test_create_scan_enforces_limit(auth_client):
    client, info = auth_client
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == info["id"]).first()
        user.scan_limit = 1
    client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert resp.status_code == 409


def test_get_scan_returns_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id


def test_get_scan_returns_403_for_wrong_owner(auth_client):
    client, _ = auth_client
    with get_db(api_db.get_factory()) as db:
        other = User(email="other@e.com", hashed_password=hash_password("pw"), scan_limit=5)
        db.add(other)
        db.flush()
        other_id = other.id
    scan_id = _make_scan(other_id)
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 403


def test_get_scan_returns_404_for_missing(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/scans/9999")
    assert resp.status_code == 404


def test_update_scan_changes_nights(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.patch(f"/api/v1/scans/{scan_id}", json={"nights": 4})
    assert resp.status_code == 200
    assert resp.json()["nights"] == 4


def test_delete_scan_soft_deletes(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.delete(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 204
    resp2 = client.get(f"/api/v1/scans/{scan_id}")
    assert resp2.status_code == 404


def test_pause_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.post(f"/api/v1/scans/{scan_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_resume_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"], status="paused")
    resp = client.post(f"/api/v1/scans/{scan_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_list_runs_returns_empty(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_results_returns_empty(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}/results")
    assert resp.status_code == 200
    assert resp.json() == []


def test_all_scan_routes_require_auth(client):
    for method, path in [
        ("GET", "/api/v1/scans"),
        ("POST", "/api/v1/scans"),
        ("GET", "/api/v1/scans/1"),
        ("PATCH", "/api/v1/scans/1"),
        ("DELETE", "/api/v1/scans/1"),
    ]:
        resp = getattr(client, method.lower())(path, json={})
        assert resp.status_code == 401, f"{method} {path} should return 401"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/api/test_scans.py -v
```

Expected: `FAILED` — scans router has no routes.

- [ ] **Step 3: Implement api/routes/scans.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from api.deps import get_db_dep, get_current_user
from api.schemas import ScanCreate, ScanUpdate, ScanResponse, ScanRunResponse, ScanResultResponse
from core.services import scans as scans_svc
from core.services import history as history_svc
from core.services.exceptions import NotFound, Forbidden, LimitExceeded

router = APIRouter()


def _scan_errors(exc):
    if isinstance(exc, NotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, Forbidden):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, LimitExceeded):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


@router.get("", response_model=List[ScanResponse])
def list_scans(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.list_scans(db, user.id)


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def create_scan(body: ScanCreate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.create_scan(db, user.id, body.dict(exclude_unset=False))
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.get_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.patch("/{scan_id}", response_model=ScanResponse)
def update_scan(scan_id: int, body: ScanUpdate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.update_scan(db, scan_id, user.id, body.dict(exclude_unset=True))
    except Exception as exc:
        _scan_errors(exc)


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        scans_svc.delete_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.post("/{scan_id}/pause", response_model=ScanResponse)
def pause_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.pause_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.post("/{scan_id}/resume", response_model=ScanResponse)
def resume_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.resume_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}/runs", response_model=List[ScanRunResponse])
def list_runs(scan_id: int, page: int = 1, page_size: int = 20,
              db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return history_svc.list_runs(db, scan_id, user.id, page=page, page_size=page_size)
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}/results", response_model=List[ScanResultResponse])
def list_results(scan_id: int, page: int = 1, page_size: int = 20,
                 db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return history_svc.list_results(db, scan_id, user.id, page=page, page_size=page_size)
    except Exception as exc:
        _scan_errors(exc)
```

- [ ] **Step 4: Run scan route tests**

```bash
.venv/bin/pytest tests/api/test_scans.py -v
```

Expected: all scan route tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/routes/scans.py tests/api/test_scans.py
git commit -m "feat(api): scan routes — CRUD, pause/resume, history"
```

---

## Task 11: API routes — users (profile)

**Files:**
- Modify: `api/routes/users.py`
- Create: `tests/api/test_users.py`

- [ ] **Step 1: Write failing test**

Create `tests/api/test_users.py`:

```python
def test_patch_profile_updates_email(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"email": "updated@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "updated@example.com"


def test_patch_profile_updates_telegram(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"telegram_chat_id": "999888"})
    assert resp.status_code == 200
    assert resp.json()["telegram_chat_id"] == "999888"


def test_patch_profile_encrypts_recreationgov_password(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"recreationgov_password": "s3cr3t"})
    assert resp.status_code == 200
    from db.models import User
    from db.session import get_db
    import api.database as api_db
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.email == "user@example.com").first()
        assert user.recreationgov_password is not None
        assert user.recreationgov_password != "s3cr3t"


def test_patch_profile_requires_auth(client):
    resp = client.patch("/api/v1/users/me", json={"email": "x@e.com"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/api/test_users.py -v
```

Expected: `FAILED` — no routes in users router.

- [ ] **Step 3: Implement api/routes/users.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.deps import get_db_dep, get_current_user
from api.schemas import ProfileUpdate
from config.settings import get_settings
from core.services.users import update_profile
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ProfileResponse(BaseModel):
    id: int
    email: str
    telegram_chat_id: Optional[str]
    recreationgov_email: Optional[str]
    scan_limit: int

    class Config:
        orm_mode = True


@router.patch("/me", response_model=ProfileResponse)
def patch_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    settings = get_settings()
    return update_profile(db, user.id, body.dict(exclude_unset=True), settings.encryption_key)
```

- [ ] **Step 4: Run all API tests**

```bash
.venv/bin/pytest tests/api/ -v
```

Expected: all API tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/routes/users.py tests/api/test_users.py
git commit -m "feat(api): profile route — PATCH /users/me"
```

---

## Task 12: Run full test suite

- [ ] **Step 1: Run all tests with coverage**

```bash
.venv/bin/pytest tests/ --cov=core --cov=api --cov=db --cov=config --cov-report=term-missing -v
```

Expected: all tests pass. Coverage on `core/services/` and `api/` at 90%+.

- [ ] **Step 2: Fix any failures before proceeding**

If any test fails, fix it now. Do not proceed to Docker until the full suite is green.

---

## Task 13: Docker — api service

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the api service**

Open `docker-compose.yml` and add the `api` service alongside the existing `app` service. The two services use the same image but different commands:

```yaml
  api:
    build: .
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    volumes:
      - ./data:/app/data
    env_file: .env
    depends_on:
      - app
    networks:
      - internal
```

Ensure `app` and `playwright` are also on the `internal` network (not exposed publicly). Only `frontend` (Phase 2 frontend plan) will expose port 80.

The full `networks:` section to add at the bottom of `docker-compose.yml`:

```yaml
networks:
  internal:
    driver: bridge
```

And add `networks: [internal]` to `app` and `playwright` services as well.

- [ ] **Step 2: Verify the api container starts**

```bash
docker compose build api && docker compose up api -d && sleep 3 && docker compose logs api
```

Expected: uvicorn starts, logs `Application startup complete`.

```bash
curl http://localhost:8000/api/v1/auth/me
```

Expected: `{"detail":"Unauthorized"}` (401 — no cookie) confirms the API is reachable.

- [ ] **Step 3: Stop and commit**

```bash
docker compose down
git add docker-compose.yml
git commit -m "feat(docker): add api service sharing app image"
```

---

## Task 14: Final smoke test + push

- [ ] **Step 1: Run full test suite one more time**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests pass, no warnings about missing env vars.

- [ ] **Step 2: Push branch to origin**

```bash
git push -u origin HEAD
```

- [ ] **Step 3: Open PR targeting main**

The PR should include a note that the frontend plan (`2026-05-12-phase2-frontend.md`) is the follow-on and that the API is fully functional and tested independently.

---

## Summary

| Milestone | Tasks | Deliverable |
|-----------|-------|-------------|
| M1 — Dependencies + DB | 1–4 | New columns, CLI options, new packages |
| M2 — Service layer | 5–6 | `core/services/` — scans, users, history |
| M3 — API foundation | 7–8 | Auth helpers, deps, schemas |
| M4 — API routes | 9–11 | All routes tested, auth enforced |
| M5 — Docker | 12–13 | `api` container running alongside `app` |

After this plan: implement `2026-05-12-phase2-frontend.md` (React SPA).
