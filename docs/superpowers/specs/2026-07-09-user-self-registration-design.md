# User self-registration

**Date:** 2026-07-09
**Status:** Approved (design)
**Branch:** `feat/user-self-registration`

## Problem

Today, creating a CampBuddy user requires shell access to the host: `cli.py seed` (from
`config/scans.yaml`) or `cli.py set-password`. There is no way for a person to create
their own account through the web UI — deferred from Phase 1 of the web UI
([#17](https://github.com/onurburak9/campbuddy/issues/17)) and tracked as one item in
[#22](https://github.com/onurburak9/campbuddy/issues/22).

## Goals

1. A `POST /api/v1/auth/register` endpoint that creates a `User` row with a login
   password and immediately logs the new user in (session cookie), mirroring `/login`.
2. A `/register` page in the web UI, reachable from the login page, using the same
   split-screen shell as `LoginPage`.
3. An operator-controlled `REGISTRATION_ENABLED` setting (default `true`) so self-hosters
   can disable open signup later without a code change.

## Non-goals (deliberately out of scope)

- **Email verification.** This instance is used by a trusted circle who share the URL
  directly; there's no need to confirm the address is reachable. Can be added later if
  the deployment model changes.
- **Invite codes / admin approval.** Same reasoning — open signup is acceptable for the
  current trust model.
- **Self-serve "forgot password."** If a user forgets their password, an admin still
  resets it via the existing `cli.py set-password` / `change-password` commands. A
  follow-up ticket can add an email-based reset-link flow later.
- **Frontend-visible registration-enabled config endpoint.** The register link is always
  rendered; if registration is disabled, submitting shows the backend's error message.
  Simpler than adding a `GET /auth/config` endpoint for a rarely-toggled setting.
- **Rate limiting / CAPTCHA.** Not needed for a trusted-circle, self-hosted deployment.

---

## Design

### 1. Settings toggle

`config/settings.py` — add:

```python
registration_enabled: bool = True
```

Read from `.env` (`REGISTRATION_ENABLED`), same pattern as `cookie_secure`.

### 2. Service layer

`core/services/users.py` — new function:

```python
def register_user(db, email: str, password: str) -> User:
    existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if existing:
        raise InvalidState("Email already in use")
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.flush()
    return user
```

- Uses the existing `InvalidState` exception (already mapped to HTTP 409 in
  `api/main.py`) — no new exception type needed.
- Leaves `recreationgov_email`/`recreationgov_password` unset and `scan_limit` at the
  model default (`5`), identical to what `cli.py seed` produces for a bare user.
- `hash_password` imported from `api.auth` (already used by `set_password`/CLI paths).

### 3. Schema

`api/schemas.py` — new:

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
```

### 4. Route

`api/routes/auth.py` — new `POST /register`:

- If `not settings.registration_enabled`: `HTTPException(403, "Registration is currently disabled")`.
- Calls `register_user(db, body.email, body.password)`.
- On `InvalidState` (duplicate email): let it propagate — the existing `InvalidState`
  handler in `api/main.py` returns 409 with the exception message as `detail`, matching
  the message shape already used in `api/routes/users.py` for the same case.
- On success: set the session cookie exactly as `/login` does. Extract the
  `create_token` + `response.set_cookie(...)` block (currently duplicated between
  `/login` and the new route) into a small `_issue_session_cookie(response, user_id,
  settings)` helper in `api/auth.py`, used by both routes.
- Returns `{"ok": True}` (same shape as `/login`).

### 5. Frontend

- Extract the split-screen markup currently inlined in `LoginPage.tsx` (forest-green
  gradient panel + form panel) into a shared `AuthLayout.tsx` wrapper taking the form as
  `children`. `LoginPage` becomes `<AuthLayout><LoginForm /></AuthLayout>`.
- New `frontend/src/components/auth/RegisterForm.tsx` (sibling to `LoginForm.tsx`) and
  `RegisterPage.tsx` (`<AuthLayout><RegisterForm /></AuthLayout>`), mirroring the
  Login pair.
- New `/register` route in `App.tsx`.
- Login page gets a "Create an account" link; register page gets a "Back to login" link.
- `frontend/src/api/auth.ts` — new `register(email, password)` calling
  `POST /api/v1/auth/register` through the existing `fetchApi` wrapper.
- On success: invalidate/refetch the `["me"]` TanStack Query (same as `login()` does
  today via `AuthContext`), then navigate to `/`.
- Client-side checks (UX only, not re-validated against the server): non-empty email
  shape, password ≥ 8 chars, a "confirm password" field that must match before submit is
  enabled.

## Data flow

```
Submit register form
  → POST /api/v1/auth/register {email, password}
    → registration_enabled? no → 403
    → register_user(db, email, password)
        → email taken? → InvalidState → 409
        → create User(hashed_password=...)
    → set session cookie (same helper as /login)
  → 200 {ok: true}
→ frontend refetches ["me"] → AuthContext sees logged-in user → redirect to "/"
```

## Error handling

| Failure | Behavior |
|---|---|
| `registration_enabled=false` | 403, `detail: "Registration is currently disabled"`; form shows a page-level message. |
| Email already registered | 409 (`InvalidState`), `detail: "Email already in use"`; inline error under the email field. |
| Password < 8 chars | 422 (Pydantic `Field(min_length=8)`); inline error under the password field. |
| Malformed email | 422 (Pydantic `EmailStr`); inline error under the email field. |

## Testing

Mock all external I/O; in-memory SQLite (`docs/agents/testing.md`).

- **`tests/services/test_users.py`:** `register_user` — creates user with hashed
  password and default `scan_limit`; leaves `recreationgov_*` fields unset; raises
  `InvalidState` on duplicate email (case: exact match; a differently-cased duplicate is
  out of scope since login/lookup elsewhere is also exact-match on `email`).
- **`tests/api/test_auth.py`:** register happy path (cookie set and decodes to the new
  user's id, 200 body, user persisted with correct defaults); duplicate email → 409;
  registration disabled (`registration_enabled=False` via settings override) → 403; weak
  password → 422; malformed email → 422.
- **Frontend:** `RegisterForm` test mirroring whatever test pattern exists for
  `LoginForm` (submit happy path, inline error rendering for 409/422/403) — confirm the
  existing pattern during implementation and match it.

## Follow-ups (separate tickets)

- Self-serve "forgot password" via emailed reset link (reusing existing SMTP config).
- Email verification / invite-based signup, if the deployment model ever moves beyond a
  trusted circle.
