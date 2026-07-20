# Forgot password

**Date:** 2026-07-15
**Status:** Approved (design)
**Branch:** `feat/forgot-password`

## Problem

There is no self-service way to recover a forgotten login password. Today an admin
must run `cli.py set-password <email>` on the host. Called out as a deliberate
non-goal in [user self-registration](2026-07-09-user-self-registration-design.md),
which noted registration is open to anyone — meaning a "just email + new password, no
proof of ownership" reset would let any registered user hijack any other user's
account by guessing their email. A token-based, emailed reset link is required to
close that hole.

## Goals

1. `POST /api/v1/auth/forgot-password` — given an email, if an active (non-deleted)
   user exists with it, generate a single-use reset token, email a reset link via the
   existing SMTP config. Always responds `{"ok": true}` regardless of whether the
   email exists, to avoid leaking which emails are registered.
2. `POST /api/v1/auth/reset-password` — given a valid, unexpired, unused token and a
   new password, updates the user's password, invalidates the token, and logs the user
   in (session cookie), mirroring `/register`.
3. Two new pages in the web UI — "Forgot password" (request) and "Reset password"
   (consume) — reachable from the login page, using the existing `AuthLayout` shell.

## Non-goals (deliberately out of scope)

- **Rate limiting / CAPTCHA on `/forgot-password`.** Not needed for a trusted-circle,
  self-hosted deployment (same reasoning as registration).
- **Notifying the user by Telegram.** Password reset is a login-credential action tied
  to the account's email identity; Telegram is only used for availability alerts
  today. Reset links go by email only.
- **"Change password while logged in."** Already covered by `cli.py change-password`
  and out of scope for this ticket, which is specifically about the *forgotten*
  password case.
- **Multiple concurrent valid tokens.** Requesting a new reset link invalidates any
  previous unused token for that user — one active token at a time, simpler to reason
  about and to test.

---

## Design

### 1. Schema

`db/models.py` — new table:

```python
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
```

- Stores a SHA-256 hex digest of the token (`token_hash`), never the raw token — same
  principle as password hashing. The raw token only ever exists in the generated URL
  and the outbound email.
- `alembic revision --autogenerate -m "add password_reset_tokens"` in the same commit,
  per [schema-changes.md](../../agents/schema-changes.md).

### 2. Settings

`config/settings.py` — add:

```python
app_base_url: str = "http://localhost:5173"
```

Used to build the reset link (`{app_base_url}/reset-password?token=...`). Read from
`.env` (`APP_BASE_URL`), same pattern as `cookie_secure`.

### 3. Service layer

`core/services/users.py` — new functions:

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

- Reuses the existing `NotFound` exception (already mapped to HTTP 404 — route layer
  will translate to a generic 400, see Error handling below, so the API doesn't leak
  "not found" language that implies enumeration).
- `hash_password` (bcrypt) stays in `api/auth.py`; the route hashes the new password
  before calling `reset_password_with_token`, same division of responsibility as
  `register`/`set-password`.

### 4. Email

`core/notifier.py` — new function, same `smtplib` pattern as `send_email`:

```python
def send_password_reset_email(to: str, reset_url: str, settings) -> None:
    body = (
        f"A password reset was requested for your CampBuddy account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in 30 minutes. If you didn't request this, ignore this email.\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = "Reset your CampBuddy password"
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
```

### 5. Schemas

`api/schemas.py` — new:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8)
```

### 6. Routes

`api/routes/auth.py` — new:

- `POST /forgot-password`: calls `create_password_reset_token`. If it returns a token,
  builds the reset URL and calls `send_password_reset_email`, catching and logging any
  SMTP exception (never surfaced to the caller — a mail-server hiccup shouldn't reveal
  account existence via a differing response). Always returns `{"ok": True}`.
- `POST /reset-password`: hashes `body.password` via `hash_password`, calls
  `reset_password_with_token`. On `NotFound`, raise `HTTPException(400, "Invalid or
  expired reset link")` (400, not 404 — 404 on this route would itself be a signal).
  On success, issue the session cookie exactly as `/login`/`/register` do and return
  `{"ok": True}`.

### 7. Frontend

- `frontend/src/api/auth.ts` — add:
  ```ts
  forgotPassword: (email: string) =>
    fetchApi<void>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, password: string) =>
    fetchApi<void>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }),
  ```
- `frontend/src/contexts/AuthContext.tsx` — add a `resetPassword(token, password)`
  action parallel to `login`/`register`: calls `auth.resetPassword`, then invalidates
  the `["me"]` query so the app picks up the new session.
- `frontend/src/components/auth/ForgotPasswordForm.tsx` (sibling to `LoginForm.tsx`):
  email input, submit → on success (always, per API contract) replaces the form with a
  static "Check your email for a reset link" panel. No error state to show except
  network/validation failures.
- `frontend/src/components/auth/ForgotPasswordPage.tsx`:
  `<AuthLayout><ForgotPasswordForm /></AuthLayout>`.
- `frontend/src/components/auth/ResetPasswordForm.tsx`: reads `token` from
  `useSearchParams()`, new-password + confirm-password fields (client-side match +
  length check, same UX pattern as `RegisterForm`), calls `resetPassword` from
  `AuthContext`, navigates to `/` on success. On a 400 (invalid/expired token), shows an
  inline error with a link back to `/forgot-password`.
- `frontend/src/components/auth/ResetPasswordPage.tsx`:
  `<AuthLayout><ResetPasswordForm /></AuthLayout>`.
- `App.tsx` — add `/forgot-password` and `/reset-password` routes (same unauthenticated
  tier as `/login`, `/register`).
- `LoginForm.tsx` — add a "Forgot password?" link next to the password field, pointing
  to `/forgot-password`.

## Data flow

```
Request:
Submit forgot-password form
  → POST /auth/forgot-password {email}
    → create_password_reset_token(db, email)
        → user found? invalidate prior unused token, create new one, return raw token
        → user not found? return None
    → token returned? build reset_url, send_password_reset_email (best-effort)
  → 200 {ok: true}  (always, regardless of branch above)
→ frontend shows "check your email" panel

Consume:
User clicks emailed link → /reset-password?token=...
Submit new password
  → POST /auth/reset-password {token, password}
    → reset_password_with_token(db, token, hash_password(password))
        → token invalid/expired/used → NotFound → 400
        → else: mark token used, update user.hashed_password
    → set session cookie (same helper as /login, /register)
  → 200 {ok: true}
→ frontend refetches ["me"] → AuthContext sees logged-in user → redirect to "/"
```

## Error handling

| Failure | Behavior |
|---|---|
| Email not registered (forgot-password) | 200 `{ok: true}` (same as success) — no email sent, no distinguishable response. |
| SMTP send fails | Logged server-side; response is still 200 `{ok: true}` — a mail outage must not reveal account existence via a different status code. |
| Reset token invalid, expired, or already used | 400, `detail: "Invalid or expired reset link"`; form shows a page-level message + link to request a new one. |
| Password < 8 chars (reset) | 422 (Pydantic `Field(min_length=8)`); inline error under the password field. |
| Malformed email (forgot-password) | 422 (Pydantic `EmailStr`); inline error under the email field. |

## Testing

Mock all external I/O (SMTP); in-memory SQLite ([testing.md](../../agents/testing.md)).

- **`tests/services/test_users.py`:**
  `create_password_reset_token` — returns a token for an existing user, persists a
  hashed token with a ~30-min expiry, invalidates a prior unused token when called
  again for the same user, returns `None` for an unknown/soft-deleted email.
  `reset_password_with_token` — updates the password and marks the token used on a
  valid token; raises `NotFound` for an unknown, expired, or already-used token; raises
  `NotFound` if the token's user has since been soft-deleted.
- **`tests/api/test_auth.py`:**
  forgot-password returns `{ok: true}` both for a known and an unknown email (and in
  both cases confirms — via a mocked `send_password_reset_email` — whether it was
  called or not); reset-password happy path (cookie set, 200, password actually
  changed — verify old password no longer works); invalid/expired/reused token → 400;
  weak new password → 422.
- **Frontend:** `ForgotPasswordForm` and `ResetPasswordForm` tests mirroring the
  existing `LoginForm.test.tsx` pattern (submit happy path, inline error rendering,
  token read from query string for the reset form).

## Follow-ups (separate tickets)

- Rate limiting on `/forgot-password` if the deployment model ever moves beyond a
  trusted circle.
