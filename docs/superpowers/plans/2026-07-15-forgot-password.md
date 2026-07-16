# Forgot Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user who forgot their password recover their account through a self-service, emailed reset-link flow (`POST /api/v1/auth/forgot-password` + `POST /api/v1/auth/reset-password`), with matching `/forgot-password` and `/reset-password` pages in the web UI.

**Architecture:** A new `password_reset_tokens` table stores a SHA-256 hash of a single-use, 30-minute token (never the raw value). `create_password_reset_token` (service layer) issues a token for a known email and invalidates any prior unused one; the route emails a reset link via a new `send_password_reset_email` (reusing the existing SMTP setup in `core/notifier.py`) and always responds `{"ok": true}`, regardless of whether the email exists, to avoid leaking account existence. `reset_password_with_token` validates and consumes the token and updates the password; the route then logs the user in via the existing `issue_session_cookie` helper, mirroring `/register`. The frontend adds `ForgotPasswordForm`/`ForgotPasswordPage` and `ResetPasswordForm`/`ResetPasswordPage`, both using the existing `AuthLayout` shell, plus a `resetPassword` action on `AuthContext` (parallel to `login`/`register`) and a plain `auth.forgotPassword` API call (no context needed since it doesn't change auth state).

**Tech Stack:** FastAPI + Pydantic v1 + SQLAlchemy + Alembic (backend), React + TypeScript + Vite + TanStack Query + React Router v6 (frontend), pytest + pytest-mock (backend tests), Vitest + Testing Library + MSW (frontend tests).

## Global Constraints

- Backend: mock all external I/O (SMTP); use in-memory/file SQLite for DB-touching tests (`docs/agents/testing.md`).
- Backend: pydantic v1 syntax only (`validator`, not `field_validator`) — see `docs/agents/code-conventions.md`.
- Timezone-aware datetimes everywhere: `datetime.now(timezone.utc)`, never `datetime.utcnow()`.
- Every `db/models.py` change needs a matching Alembic migration in the same commit (`docs/agents/schema-changes.md`).
- Store a SHA-256 hash of the reset token in the DB, never the raw token.
- One active (unused) reset token per user at a time — issuing a new one invalidates the previous unused one.
- Token lifetime: 30 minutes. Single-use: consuming it (successfully) sets `used_at`; reusing an already-used or expired token is rejected.
- `POST /auth/forgot-password` always returns `{"ok": true}` and never distinguishes a known vs. unknown email in its response, status code, or timing-sensitive branching (mirrors the enumeration-safety approach already used in `/auth/login`).
- On successful reset, log the user in (session cookie), same as `/register`.
- Password minimum length: 8 characters (`Field(..., min_length=8)`), same as `RegisterRequest`.

---

### Task 1: `password_reset_tokens` table

**Files:**
- Modify: `db/models.py`
- Create: `migrations/versions/<generated>_add_password_reset_tokens.py`

**Interfaces:**
- Produces: `PasswordResetToken` model — `id`, `user_id` (FK → `users.id`, indexed), `token_hash` (unique, indexed), `expires_at`, `used_at` (nullable), `created_at`.

- [ ] **Step 1: Add the model**

In `db/models.py`, add after the `User` class (after its `scans` relationship, before `class Scan(Base):`). No new imports are needed — `ForeignKey`, `String`, `Integer`, `Optional`, `datetime` are already imported in this file.

```python
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow)
```

- [ ] **Step 2: Generate the migration**

Run: `.venv/bin/alembic revision --autogenerate -m "add password reset tokens"`
Expected: a new file created under `migrations/versions/`.

- [ ] **Step 3: Review the generated file**

Open the new file and confirm `upgrade()`/`downgrade()` are equivalent to (autogenerate's exact statement order may vary slightly, that's fine):

```python
def upgrade() -> None:
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
```

If autogenerate produced something meaningfully different (e.g. missing the foreign key), edit the file to match the above by hand.

- [ ] **Step 4: Verify the migration applies cleanly and matches the model**

Use a throwaway database file so this never touches any real local `data/campbuddy.db`:

```bash
mkdir -p data
DATABASE_URL="sqlite:///./data/_migration_check.db" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite:///./data/_migration_check.db" .venv/bin/alembic check
rm -f data/_migration_check.db
```
Expected: `alembic upgrade head` runs without error; `alembic check` prints `No new upgrade operations detected.`

- [ ] **Step 5: Commit**

```bash
git add db/models.py migrations/versions/
git commit -m "feat: add password_reset_tokens table"
```

---

### Task 2: `app_base_url` setting

**Files:**
- Modify: `config/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.app_base_url: str` (default `"http://localhost:5173"`), read from `.env` var `APP_BASE_URL`. Used in Task 5 to build the reset link.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_settings.py`:

```python
def test_app_base_url_defaults_to_localhost(env):
    s = Settings(_env_file=None)
    assert s.app_base_url == "http://localhost:5173"


def test_app_base_url_can_be_overridden(env):
    env.setenv("APP_BASE_URL", "https://campbuddy.example.com")
    s = Settings(_env_file=None)
    assert s.app_base_url == "https://campbuddy.example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_settings.py -v -k app_base_url`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'app_base_url'`

- [ ] **Step 3: Add the setting**

In `config/settings.py`, add to the `Settings` class (after `registration_enabled: bool = True`):

```python
    app_base_url: str = "http://localhost:5173"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_settings.py -v -k app_base_url`
Expected: 2 passed

- [ ] **Step 5: Run the full settings test file to check for regressions**

Run: `.venv/bin/pytest tests/test_settings.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat: add APP_BASE_URL settings flag"
```

---

### Task 3: `create_password_reset_token` service function

**Files:**
- Modify: `core/services/users.py`
- Test: `tests/services/test_users.py`

**Interfaces:**
- Consumes: `PasswordResetToken` (Task 1), `User` (existing).
- Produces: `create_password_reset_token(db, email: str) -> Optional[str]` — returns a raw, URL-safe token on success (and persists only its SHA-256 hash with a 30-minute expiry), or `None` if no active user has that email. Invalidates any prior unused token for the same user before issuing a new one.

- [ ] **Step 1: Write the failing tests**

Add to the top of `tests/services/test_users.py`, extending the existing import lines:

```python
import hashlib
from datetime import datetime, timezone, timedelta
from db.models import User, Scan, PasswordResetToken
from core.services.users import get_user_by_email, update_profile, scans_used, register_user, create_password_reset_token
```

(this replaces the existing `from db.models import User, Scan` and `from core.services.users import get_user_by_email, update_profile, scans_used, register_user` lines)

Add the test cases (anywhere after the imports):

```python
def test_create_password_reset_token_returns_token_for_existing_user(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    assert token is not None
    assert len(token) > 20


def test_create_password_reset_token_persists_hashed_token_with_expiry(db):
    u = make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    row = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == u.id).first()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.used_at is None
    assert row.expires_at > datetime.now(timezone.utc) + timedelta(minutes=29)
    assert row.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=30)


def test_create_password_reset_token_invalidates_prior_unused_token(db):
    make_user(db, "reset@e.com")
    first_token = create_password_reset_token(db, "reset@e.com")
    create_password_reset_token(db, "reset@e.com")
    first_row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hashlib.sha256(first_token.encode()).hexdigest()
    ).first()
    assert first_row.used_at is not None


def test_create_password_reset_token_returns_none_for_unknown_email(db):
    assert create_password_reset_token(db, "ghost@e.com") is None


def test_create_password_reset_token_returns_none_for_soft_deleted_user(db):
    u = make_user(db, "gone@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    assert create_password_reset_token(db, "gone@e.com") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k create_password_reset_token`
Expected: FAIL with `ImportError: cannot import name 'create_password_reset_token'`

- [ ] **Step 3: Implement `create_password_reset_token`**

In `core/services/users.py`, update the imports at the top of the file:

```python
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from db.models import User, Scan, PasswordResetToken
from core.services.exceptions import NotFound, InvalidState
from core.crypto import encrypt_password
```

(this replaces the existing `from db.models import User, Scan` line; the other two import lines are unchanged)

Add the function (anywhere after `register_user`):

```python
def create_password_reset_token(db, email: str) -> Optional[str]:
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if not user:
        return None
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({"used_at": datetime.now(timezone.utc)}, synchronize_session="fetch")
    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(token)
    db.flush()
    return raw_token
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k create_password_reset_token`
Expected: 5 passed

- [ ] **Step 5: Run the full service test file to check for regressions**

Run: `.venv/bin/pytest tests/services/test_users.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add core/services/users.py tests/services/test_users.py
git commit -m "feat: add create_password_reset_token service function"
```

---

### Task 4: `send_password_reset_email` notifier function

**Files:**
- Modify: `core/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Produces: `send_password_reset_email(to: str, reset_url: str, settings) -> None` — sends a plain-text email containing the reset link, same `smtplib` pattern as `send_email`.

- [ ] **Step 1: Write the failing tests**

Add `send_password_reset_email` to the existing import block at the top of `tests/test_notifier.py`:

```python
from core.notifier import (
    NotificationPayload,
    _available_body,
    notify_available,
    notify_cart_results,
    send_email,
    send_email_digest,
    send_password_reset_email,
    send_telegram,
    send_telegram_digest,
)
```

Add the test cases (anywhere after `test_email_contains_booking_url_and_cart_status`):

```python
def test_password_reset_email_contains_reset_url(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_password_reset_email(
        "to@example.com", "https://app.example.com/reset-password?token=abc123", make_settings()
    )
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "https://app.example.com/reset-password?token=abc123" in body


def test_password_reset_email_sent_to_correct_recipient(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_password_reset_email(
        "to@example.com", "https://app.example.com/reset-password?token=abc123", make_settings()
    )
    from_addr, to_addr, _ = instance.sendmail.call_args[0]
    assert from_addr == "CampBuddy <from@example.com>"
    assert to_addr == "to@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_notifier.py -v -k password_reset_email`
Expected: FAIL with `ImportError: cannot import name 'send_password_reset_email'`

- [ ] **Step 3: Implement `send_password_reset_email`**

In `core/notifier.py`, add the function (anywhere after `send_email`):

```python
def send_password_reset_email(to: str, reset_url: str, settings) -> None:
    body = (
        "A password reset was requested for your CampBuddy account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        "This link expires in 30 minutes. If you didn't request this, ignore this email.\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = "Reset your CampBuddy password"

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Password reset email sent to %s", to)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_notifier.py -v -k password_reset_email`
Expected: 2 passed

- [ ] **Step 5: Run the full notifier test file to check for regressions**

Run: `.venv/bin/pytest tests/test_notifier.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add core/notifier.py tests/test_notifier.py
git commit -m "feat: add send_password_reset_email notifier function"
```

---

### Task 5: `POST /auth/forgot-password` route

**Files:**
- Modify: `api/schemas.py`
- Modify: `api/routes/auth.py`
- Test: `tests/api/test_auth.py`

**Interfaces:**
- Consumes: `create_password_reset_token` (Task 3), `send_password_reset_email` (Task 4), `settings.app_base_url` (Task 2).
- Produces: `ForgotPasswordRequest(email: str)` schema; `POST /api/v1/auth/forgot-password` — always 200 `{"ok": true}`.

- [ ] **Step 1: Add the schema**

In `api/schemas.py`, add the class after `RegisterRequest`:

```python
class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3)

    @validator("email")
    def valid_email_format(cls, v):
        if not _EMAIL_RE.fullmatch(v):
            raise ValueError("Invalid email format")
        return v
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/api/test_auth.py`. First add the needed import at the top (extending the existing `from db.models import User` line to `from db.models import User, PasswordResetToken`), then add:

```python
def test_forgot_password_returns_ok_for_known_email(client, user_in_db, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_send.assert_called_once()


def test_forgot_password_returns_ok_for_unknown_email_without_sending(client, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_send.assert_not_called()


def test_forgot_password_creates_reset_token_for_known_email(client, user_in_db, mocker):
    mocker.patch("api.routes.auth.send_password_reset_email")
    client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    with get_db(api_db.get_factory()) as db:
        token = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_in_db["id"]).first()
        assert token is not None
        assert token.used_at is None


def test_forgot_password_reset_url_contains_token_and_base_url(client, user_in_db, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    to, reset_url, _settings = mock_send.call_args[0]
    assert to == "user@example.com"
    assert reset_url.startswith("http://localhost:5173/reset-password?token=")


def test_forgot_password_malformed_email_returns_422(client):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_forgot_password_email_send_failure_still_returns_ok(client, user_in_db, mocker):
    mocker.patch("api.routes.auth.send_password_reset_email", side_effect=Exception("smtp down"))
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k forgot_password`
Expected: FAIL with 404 (no such route)

- [ ] **Step 4: Implement the route**

In `api/routes/auth.py`, update the imports:

```python
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, hash_password, COOKIE_NAME, issue_session_cookie
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, RegisterRequest, ForgotPasswordRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, register_user, scans_used, create_password_reset_token
from core.services.exceptions import NotFound, InvalidState
from core.notifier import send_password_reset_email
```

Add the route (after `register()`):

```python
@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    raw_token = create_password_reset_token(db, body.email)
    if raw_token:
        reset_url = f"{settings.app_base_url}/reset-password?token={raw_token}"
        try:
            send_password_reset_email(body.email, reset_url, settings)
        except Exception as e:
            logger.error("Password reset email failed: %s", e)
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k forgot_password`
Expected: 6 passed

- [ ] **Step 6: Run the full auth test file to check for regressions**

Run: `.venv/bin/pytest tests/api/test_auth.py -v`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add api/schemas.py api/routes/auth.py tests/api/test_auth.py
git commit -m "feat: add POST /auth/forgot-password endpoint"
```

---

### Task 6: `reset_password_with_token` service function

**Files:**
- Modify: `core/services/users.py`
- Test: `tests/services/test_users.py`

**Interfaces:**
- Consumes: `PasswordResetToken` (Task 1), `create_password_reset_token` (Task 3, used in tests to obtain a valid token), `NotFound` (existing).
- Produces: `reset_password_with_token(db, raw_token: str, hashed_password: str) -> User` — validates the token (exists, unused, unexpired), marks it used, updates the user's password. Raises `NotFound` for any invalid/expired/used/unknown-user case. Takes an **already-hashed** password, same boundary as `register_user`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/test_users.py`, extending the import line from Task 3 to also import `reset_password_with_token`:

```python
from core.services.users import get_user_by_email, update_profile, scans_used, register_user, create_password_reset_token, reset_password_with_token
```

Add the test cases:

```python
def test_reset_password_with_token_updates_password_and_marks_used(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    user = reset_password_with_token(db, token, "new-hashed-value")
    assert user.hashed_password == "new-hashed-value"
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hashlib.sha256(token.encode()).hexdigest()
    ).first()
    assert row.used_at is not None


def test_reset_password_with_token_raises_not_found_for_unknown_token(db):
    with pytest.raises(NotFound):
        reset_password_with_token(db, "not-a-real-token", "hashed")


def test_reset_password_with_token_raises_not_found_for_expired_token(db):
    u = make_user(db, "reset@e.com")
    token = PasswordResetToken(
        user_id=u.id,
        token_hash=hashlib.sha256("expired-token".encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(token)
    db.flush()
    with pytest.raises(NotFound):
        reset_password_with_token(db, "expired-token", "hashed")


def test_reset_password_with_token_raises_not_found_for_already_used_token(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    reset_password_with_token(db, token, "hashed-1")
    with pytest.raises(NotFound):
        reset_password_with_token(db, token, "hashed-2")


def test_reset_password_with_token_raises_not_found_for_soft_deleted_user(db):
    u = make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(NotFound):
        reset_password_with_token(db, token, "hashed")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k reset_password_with_token`
Expected: FAIL with `ImportError: cannot import name 'reset_password_with_token'`

- [ ] **Step 3: Implement `reset_password_with_token`**

In `core/services/users.py`, add the function (after `create_password_reset_token`):

```python
def reset_password_with_token(db, raw_token: str, hashed_password: str) -> User:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not token:
        raise NotFound("Invalid or expired reset link")
    user = db.query(User).filter(User.id == token.user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise NotFound("Invalid or expired reset link")
    token.used_at = datetime.now(timezone.utc)
    user.hashed_password = hashed_password
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k reset_password_with_token`
Expected: 5 passed

- [ ] **Step 5: Run the full service test file to check for regressions**

Run: `.venv/bin/pytest tests/services/test_users.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add core/services/users.py tests/services/test_users.py
git commit -m "feat: add reset_password_with_token service function"
```

---

### Task 7: `POST /auth/reset-password` route

**Files:**
- Modify: `api/schemas.py`
- Modify: `api/routes/auth.py`
- Test: `tests/api/test_auth.py`

**Interfaces:**
- Consumes: `reset_password_with_token` (Task 6), `hash_password`/`issue_session_cookie` (existing, already imported).
- Produces: `ResetPasswordRequest(token: str, password: str)` schema; `POST /api/v1/auth/reset-password` — 200 `{"ok": true}` + session cookie on success; 400 on invalid/expired/reused token; 422 on weak password.

- [ ] **Step 1: Add the schema**

In `api/schemas.py`, add the class after `ForgotPasswordRequest`:

```python
class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/api/test_auth.py`. This file doesn't import from `core.services.users` yet — add a new import line near the top (after the `from api.auth import ...` line):

```python
from core.services.users import create_password_reset_token
```

Add the test cases:

```python
def test_reset_password_sets_cookie_and_updates_password(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "newlongpassword"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies
    login_resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "newlongpassword"})
    assert login_resp.status_code == 200


def test_reset_password_old_password_no_longer_works(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    client.post("/api/v1/auth/reset-password", json={"token": token, "password": "newlongpassword"})
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_reset_password_invalid_token_returns_400(client):
    resp = client.post("/api/v1/auth/reset-password", json={"token": "bogus", "password": "newlongpassword"})
    assert resp.status_code == 400


def test_reset_password_reused_token_returns_400(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    client.post("/api/v1/auth/reset-password", json={"token": token, "password": "firstnewpw"})
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "secondnewpw"})
    assert resp.status_code == 400


def test_reset_password_short_password_returns_422(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "short"})
    assert resp.status_code == 422
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k "reset_password and not forgot"`
Expected: FAIL with 404 (no such route)

- [ ] **Step 4: Implement the route**

In `api/routes/auth.py`, update the imports:

```python
from api.schemas import LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest, MeResponse
from core.services.users import get_user_by_email, register_user, scans_used, create_password_reset_token, reset_password_with_token
```

(these replace the corresponding import lines from Task 5)

Add the route (after `forgot_password()`):

```python
@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, response: Response, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    try:
        user = reset_password_with_token(db, body.token, hash_password(body.password))
    except NotFound:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")
    issue_session_cookie(response, user.id, settings)
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k "reset_password and not forgot"`
Expected: 5 passed

- [ ] **Step 6: Run the full backend test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add api/schemas.py api/routes/auth.py tests/api/test_auth.py
git commit -m "feat: add POST /auth/reset-password endpoint"
```

---

### Task 8: Frontend API client + `resetPassword` in `AuthContext`

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/contexts/AuthContext.tsx`
- Test: `frontend/src/contexts/AuthContext.test.tsx`

**Interfaces:**
- Produces: `auth.forgotPassword(email): Promise<void>`; `auth.resetPassword(token, password): Promise<void>`; `useAuth().resetPassword: (token: string, password: string) => Promise<void>`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/contexts/AuthContext.test.tsx` (inside the existing `describe("AuthContext", ...)` block, after the "registers and authenticates" test):

```tsx
  it("resets password and authenticates", async () => {
    let reset = false;
    server.use(
      http.get("/api/v1/auth/me", () =>
        reset
          ? HttpResponse.json({ id: 3, email: "reset@e.com", scan_limit: 5, scans_used: 0 })
          : new HttpResponse(null, { status: 401 })
      ),
      http.post("/api/v1/auth/reset-password", () => { reset = true; return HttpResponse.json(undefined); })
    );
    function ResetProbe() {
      const { isAuthenticated, isLoading, resetPassword } = useAuth();
      if (isLoading) return <span>loading</span>;
      return (
        <div>
          <span>{isAuthenticated ? "in" : "out"}</span>
          <button onClick={() => resetPassword("sometoken", "newlongpassword")}>reset</button>
        </div>
      );
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider><ResetProbe /></AuthProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("out")).toBeInTheDocument());
    await userEvent.click(screen.getByText("reset"));
    await waitFor(() => expect(screen.getByText("in")).toBeInTheDocument());
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/contexts/AuthContext.test.tsx`
Expected: FAIL — `resetPassword` is not a function

- [ ] **Step 3: Add `forgotPassword` and `resetPassword` to the API client**

In `frontend/src/api/auth.ts`, add alongside `register`:

```ts
  forgotPassword: (email: string) =>
    fetchApi<void>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, password: string) =>
    fetchApi<void>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }),
```

- [ ] **Step 4: Add `resetPassword` to `AuthContext`**

In `frontend/src/contexts/AuthContext.tsx`, add to the `AuthCtx` interface:

```ts
  resetPassword: (token: string, password: string) => Promise<void>;
```

Add the implementation next to `register`:

```ts
  const resetPassword = async (token: string, password: string) => {
    await auth.resetPassword(token, password);
    await qc.invalidateQueries({ queryKey: ["me"] });
  };
```

Add `resetPassword` to the `Ctx.Provider` value object (alongside `login`, `register`, `logout`).

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/contexts/AuthContext.test.tsx`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/contexts/AuthContext.tsx frontend/src/contexts/AuthContext.test.tsx
git commit -m "feat: add forgotPassword/resetPassword API client and context action"
```

---

### Task 9: `ForgotPasswordForm` + `ForgotPasswordPage` + route + login-page link

**Files:**
- Create: `frontend/src/components/auth/ForgotPasswordForm.tsx`
- Create: `frontend/src/components/auth/ForgotPasswordForm.test.tsx`
- Create: `frontend/src/components/auth/ForgotPasswordPage.tsx`
- Modify: `frontend/src/components/auth/LoginForm.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `auth.forgotPassword` (Task 8, called directly — this form doesn't need `AuthContext` since it never changes auth state), `AuthLayout`/`Spinner` (existing), `Input`/`Button` (existing).
- Produces: `ForgotPasswordForm`, `ForgotPasswordPage` components; `/forgot-password` route in `App.tsx`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/auth/ForgotPasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const forgotPassword = vi.fn();
vi.mock("../../api/auth", () => ({ auth: { forgotPassword } }));

import { ForgotPasswordForm } from "./ForgotPasswordForm";

describe("ForgotPasswordForm", () => {
  it("shows a check-your-email message on submit", async () => {
    forgotPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ForgotPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(screen.getByText(/check your email/i)).toBeInTheDocument());
    expect(forgotPassword).toHaveBeenCalledWith("a@b.c");
  });

  it("shows the same check-your-email message even for an unknown address", async () => {
    forgotPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ForgotPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "ghost@b.c");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(screen.getByText(/check your email/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/auth/ForgotPasswordForm.test.tsx`
Expected: FAIL — cannot find module `./ForgotPasswordForm`

- [ ] **Step 3: Implement `ForgotPasswordForm`**

Create `frontend/src/components/auth/ForgotPasswordForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { auth } from "../../api/auth";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await auth.forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Check your email</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          If an account exists for {email}, we've sent a link to reset your password.
        </p>
        <Link to="/login" className="text-sm text-forest-600 hover:underline">Back to sign in</Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Forgot password?</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Enter your email and we'll send you a reset link</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Sending…" : "Send reset link"}
      </Button>
      <p className="text-sm text-stone-500 dark:text-[#888]">
        <Link to="/login" className="text-forest-600 hover:underline">Back to sign in</Link>
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/auth/ForgotPasswordForm.test.tsx`
Expected: 2 passed

- [ ] **Step 5: Add `ForgotPasswordPage`**

Create `frontend/src/components/auth/ForgotPasswordPage.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { Spinner } from "../ui/Spinner";

export function ForgotPasswordPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <ForgotPasswordForm />
    </AuthLayout>
  );
}
```

- [ ] **Step 6: Add the "Forgot password?" link to `LoginForm`**

In `frontend/src/components/auth/LoginForm.tsx`, add before the closing `</form>` tag, after the `<Input id="password" ...>` and before the `{error && ...}` line:

```tsx
      <div className="text-right">
        <Link to="/forgot-password" className="text-sm text-forest-600 hover:underline">Forgot password?</Link>
      </div>
```

- [ ] **Step 7: Register the `/forgot-password` route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { ForgotPasswordPage } from "./components/auth/ForgotPasswordPage";
```

Add the route (after the `/register` route):

```tsx
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
```

- [ ] **Step 8: Run the full frontend test suite**

Run (from `frontend/`): `npx vitest run`
Expected: all passed

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/auth/ForgotPasswordForm.tsx frontend/src/components/auth/ForgotPasswordForm.test.tsx frontend/src/components/auth/ForgotPasswordPage.tsx frontend/src/components/auth/LoginForm.tsx frontend/src/App.tsx
git commit -m "feat: add forgot-password page, form, and route"
```

---

### Task 10: `ResetPasswordForm` + `ResetPasswordPage` + route

**Files:**
- Create: `frontend/src/components/auth/ResetPasswordForm.tsx`
- Create: `frontend/src/components/auth/ResetPasswordForm.test.tsx`
- Create: `frontend/src/components/auth/ResetPasswordPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useAuth().resetPassword` (Task 8), `AuthLayout`/`Spinner` (existing), `Input`/`Button` (existing), `ApiError` (`../../api/client`).
- Produces: `ResetPasswordForm`, `ResetPasswordPage` components; `/reset-password` route in `App.tsx`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/auth/ResetPasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const resetPassword = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ resetPassword }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
  useSearchParams: () => [new URLSearchParams("token=abc123")],
}));

import { ResetPasswordForm } from "./ResetPasswordForm";

describe("ResetPasswordForm", () => {
  it("resets the password and navigates home on success", async () => {
    resetPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
    expect(resetPassword).toHaveBeenCalledWith("abc123", "longenough");
  });

  it("shows an error when passwords don't match, without calling resetPassword", async () => {
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument());
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("shows an error with a link to request a new one on 400 invalid/expired token", async () => {
    resetPassword.mockRejectedValueOnce(new ApiError(400, "Invalid or expired reset link"));
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(screen.getByText(/invalid or expired reset link/i)).toBeInTheDocument());
    expect(screen.getByText(/request a new link/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/auth/ResetPasswordForm.test.tsx`
Expected: FAIL — cannot find module `./ResetPasswordForm`

- [ ] **Step 3: Implement `ResetPasswordForm`**

Create `frontend/src/components/auth/ResetPasswordForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function ResetPasswordForm() {
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      await resetPassword(token, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setError(err.message);
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Set a new password</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Choose a new password for your account</p>
      </div>
      <Input id="password" label="New password" type="password" autoComplete="new-password"
        value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
      <Input id="confirm-password" label="Confirm password" type="password" autoComplete="new-password"
        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={8} required />
      {error && (
        <p className="text-sm text-[#DC2626]">
          {error} <Link to="/forgot-password" className="underline">Request a new link</Link>
        </p>
      )}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Resetting…" : "Reset password"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/auth/ResetPasswordForm.test.tsx`
Expected: 3 passed

- [ ] **Step 5: Add `ResetPasswordPage`**

Create `frontend/src/components/auth/ResetPasswordPage.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { ResetPasswordForm } from "./ResetPasswordForm";
import { Spinner } from "../ui/Spinner";

export function ResetPasswordPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <ResetPasswordForm />
    </AuthLayout>
  );
}
```

- [ ] **Step 6: Register the `/reset-password` route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { ResetPasswordPage } from "./components/auth/ResetPasswordPage";
```

Add the route (after the `/forgot-password` route):

```tsx
        <Route path="/reset-password" element={<ResetPasswordPage />} />
```

- [ ] **Step 7: Run the full frontend test suite**

Run (from `frontend/`): `npx vitest run`
Expected: all passed

- [ ] **Step 8: Run the full backend test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all passed

- [ ] **Step 9: Manually verify in the browser**

Run: `cd frontend && npm run dev`, then open `http://localhost:5173/login`, click "Forgot password?", submit an email that belongs to an existing account, check the CampBuddy log output (or your test SMTP inbox) for the reset email, copy the `token` query param from the link, navigate to `http://localhost:5173/reset-password?token=<token>`, set a new password, and confirm you land on the dashboard logged in. Then log out and confirm the new password works via `/login`, and that re-visiting the same reset link a second time shows the "invalid or expired" error.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/auth/ResetPasswordForm.tsx frontend/src/components/auth/ResetPasswordForm.test.tsx frontend/src/components/auth/ResetPasswordPage.tsx frontend/src/App.tsx
git commit -m "feat: add reset-password page, form, and route"
```
