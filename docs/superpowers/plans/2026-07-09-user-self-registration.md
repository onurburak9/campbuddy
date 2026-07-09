# User Self-Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a person create their own CampBuddy account from the web UI (`POST /api/v1/auth/register` + a `/register` page), instead of requiring CLI access, while giving the operator an `REGISTRATION_ENABLED` off-switch.

**Architecture:** A new service function (`core/services/users.py::register_user`) creates the `User` row; a new route (`POST /auth/register`) hashes the password, calls the service, and reuses the same cookie-issuing logic as `/login` (extracted into a shared helper) so the new user is auto-logged-in. The frontend gets a `/register` route mirroring the existing `/login` split-screen page, with a new shared `AuthLayout` wrapper so both pages share the same shell.

**Tech Stack:** FastAPI + Pydantic v1 (backend), React + TypeScript + Vite + TanStack Query + React Router v6 (frontend), pytest (backend tests), Vitest + Testing Library (frontend tests).

## Global Constraints

- Backend: mock all external I/O; use in-memory SQLite for DB-touching tests (`docs/agents/testing.md`).
- Backend: pydantic v1 syntax only (`validator`, not `field_validator`; `BaseSettings` is pydantic's built-in, not `pydantic-settings`) — see `docs/agents/code-conventions.md` / ADR 005.
- `core/` must not import from `api/` — password hashing happens in the route layer (`api/auth.py`), the service layer only receives an already-hashed password. (Existing code never imports `api.*` from `core/`; this plan preserves that boundary even though the design spec's pseudocode showed hashing inside the service function.)
- No DB schema changes — registration reuses the existing `User.hashed_password` column and model defaults. No migration in this plan.
- Password minimum length: 8 characters (`Field(..., min_length=8)`).
- Route: `POST /api/v1/auth/register`. Settings flag: `registration_enabled: bool = True`, env var `REGISTRATION_ENABLED`.

---

### Task 1: `registration_enabled` setting

**Files:**
- Modify: `config/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.registration_enabled: bool` (default `True`), read from `.env` var `REGISTRATION_ENABLED`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_settings.py`:

```python
def test_registration_enabled_defaults_true(env):
    s = Settings(_env_file=None)
    assert s.registration_enabled is True


def test_registration_enabled_can_be_disabled(env):
    env.setenv("REGISTRATION_ENABLED", "false")
    s = Settings(_env_file=None)
    assert s.registration_enabled is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_settings.py -v -k registration_enabled`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'registration_enabled'`

- [ ] **Step 3: Add the setting**

In `config/settings.py`, add to the `Settings` class (after `cookie_secure: bool = False`):

```python
    registration_enabled: bool = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_settings.py -v -k registration_enabled`
Expected: 2 passed

- [ ] **Step 5: Run the full settings test file to check for regressions**

Run: `.venv/bin/pytest tests/test_settings.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat: add REGISTRATION_ENABLED settings flag"
```

---

### Task 2: `register_user` service function

**Files:**
- Modify: `core/services/users.py`
- Test: `tests/services/test_users.py`

**Interfaces:**
- Consumes: `core.services.exceptions.InvalidState` (existing).
- Produces: `register_user(db, email: str, hashed_password: str) -> User`. Takes an **already-hashed** password (hashing stays in the API layer per the Global Constraints boundary) and raises `InvalidState` if the email is already registered (case-sensitive exact match, same as `get_user_by_email`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/test_users.py` (add `InvalidState` to the existing `from core.services.exceptions import NotFound` import line, making it `from core.services.exceptions import NotFound, InvalidState`, and add `register_user` to the existing `from core.services.users import get_user_by_email, update_profile, scans_used` import, making it `from core.services.users import get_user_by_email, update_profile, scans_used, register_user`):

```python
def test_register_user_creates_user_with_hashed_password(db):
    user = register_user(db, "new@e.com", "already-hashed-value")
    assert user.id is not None
    assert user.email == "new@e.com"
    assert user.hashed_password == "already-hashed-value"


def test_register_user_defaults_scan_limit_to_five(db):
    user = register_user(db, "new@e.com", "hashed")
    assert user.scan_limit == 5


def test_register_user_leaves_recreationgov_fields_unset(db):
    user = register_user(db, "new@e.com", "hashed")
    assert user.recreationgov_email is None
    assert user.recreationgov_password is None


def test_register_user_raises_invalid_state_for_duplicate_email(db):
    make_user(db, "dup@e.com")
    with pytest.raises(InvalidState):
        register_user(db, "dup@e.com", "hashed")


def test_register_user_allows_email_reused_after_soft_delete(db):
    existing = make_user(db, "gone@e.com")
    existing.deleted_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.flush()
    user = register_user(db, "gone@e.com", "hashed")
    assert user.id != existing.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k register_user`
Expected: FAIL with `ImportError: cannot import name 'register_user'`

- [ ] **Step 3: Implement `register_user`**

In `core/services/users.py`, add the import and function:

```python
from core.services.exceptions import NotFound, InvalidState
```

(replacing the existing `from core.services.exceptions import NotFound` line)

```python
def register_user(db, email: str, hashed_password: str) -> User:
    existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
    if existing:
        raise InvalidState("Email already in use")
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_users.py -v -k register_user`
Expected: 5 passed

- [ ] **Step 5: Run the full service test file to check for regressions**

Run: `.venv/bin/pytest tests/services/test_users.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add core/services/users.py tests/services/test_users.py
git commit -m "feat: add register_user service function"
```

---

### Task 3: Extract shared cookie-issuing helper in `api/auth.py`

**Files:**
- Modify: `api/auth.py`

**Interfaces:**
- Consumes: `create_token(user_id, secret_key)` (existing), `COOKIE_NAME` (existing).
- Produces: `issue_session_cookie(response: Response, user_id: int, settings: "Settings") -> None` — sets the httponly session cookie. Used by both `/login` and the new `/register` route in Task 4.

This is a pure refactor (no behavior change) covered by the existing `test_login_sets_cookie` test in `tests/api/test_auth.py` — no new test needed here; that test must keep passing.

- [ ] **Step 1: Add the helper**

In `api/auth.py`, add imports and the function (after `decode_token`):

```python
from fastapi import Response
from config.settings import Settings
```

```python
def issue_session_cookie(response: Response, user_id: int, settings: Settings) -> None:
    token = create_token(user_id, settings.api_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=86400,
    )
```

- [ ] **Step 2: Use it in the existing `/login` route**

In `api/routes/auth.py`, change the import line:

```python
from api.auth import verify_password, hash_password, COOKIE_NAME, issue_session_cookie
```

(dropping the now-unused `create_token` import from this file)

Replace this block in `login()`:

```python
    settings = get_settings()
    token = create_token(user.id, settings.api_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=86400,
    )
    return {"ok": True}
```

with:

```python
    settings = get_settings()
    issue_session_cookie(response, user.id, settings)
    return {"ok": True}
```

- [ ] **Step 3: Run the existing auth test suite to confirm no regression**

Run: `.venv/bin/pytest tests/api/test_auth.py -v`
Expected: all passed (in particular `test_login_sets_cookie`, `test_expired_jwt_returns_401`, `test_tampered_jwt_returns_401`)

- [ ] **Step 4: Commit**

```bash
git add api/auth.py api/routes/auth.py
git commit -m "refactor: extract issue_session_cookie helper shared by login and register"
```

---

### Task 4: `RegisterRequest` schema

**Files:**
- Modify: `api/schemas.py`

**Interfaces:**
- Produces: `RegisterRequest(email: str, password: str)` — `email` validated against a simple format regex (matching this codebase's existing plain-`str` convention for email fields in `LoginRequest`/`ProfileUpdate`, rather than introducing `pydantic.EmailStr` and its `email-validator` dependency), `password` with `min_length=8`.

No dedicated test file for schemas exists in this codebase (schema validation is exercised through the API tests in Task 5) — this task's correctness is verified there.

- [ ] **Step 1: Add the schema**

In `api/schemas.py`, add near the top (after the existing imports, before `VALID_PROVIDERS`):

```python
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
```

Then add the class after `LoginRequest`:

```python
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)

    @validator("email")
    def valid_email_format(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v
```

- [ ] **Step 2: Commit**

```bash
git add api/schemas.py
git commit -m "feat: add RegisterRequest schema"
```

(No separate test-run step: this schema has no standalone unit test in this codebase's conventions — it's exercised end-to-end in Task 5.)

---

### Task 5: `POST /auth/register` route

**Files:**
- Modify: `api/routes/auth.py`
- Test: `tests/api/test_auth.py`

**Interfaces:**
- Consumes: `RegisterRequest` (Task 4), `register_user` (Task 2), `issue_session_cookie` (Task 3), `hash_password` (existing, already imported in this file), `InvalidState` (`core.services.exceptions`), `settings.registration_enabled` (Task 1).
- Produces: `POST /api/v1/auth/register` — 200 `{"ok": true}` + session cookie on success; 403 if registration disabled; 409 on duplicate email; 422 on weak password / malformed email (handled automatically by FastAPI/Pydantic).

- [ ] **Step 1: Write the failing tests**

Add to `tests/api/test_auth.py` (add `InvalidState` isn't needed here — tests hit the HTTP layer):

```python
def test_register_creates_user_and_sets_cookie(client):
    resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.email == "brand-new@e.com").first()
        assert user is not None
        assert user.scan_limit == 5


def test_register_then_me_returns_new_user(client):
    client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "brand-new@e.com"


def test_register_duplicate_email_returns_409(client, user_in_db):
    resp = client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "longenough"})
    assert resp.status_code == 409


def test_register_short_password_returns_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "short"})
    assert resp.status_code == 422


def test_register_malformed_email_returns_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "longenough"})
    assert resp.status_code == 422


def test_register_disabled_returns_403(client, monkeypatch):
    from config.settings import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    try:
        resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
        assert resp.status_code == 403
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k register`
Expected: FAIL with 404 (no such route) on the first several, since `/register` doesn't exist yet

- [ ] **Step 3: Implement the route**

In `api/routes/auth.py`, update the imports:

```python
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, hash_password, COOKIE_NAME, issue_session_cookie
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, RegisterRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, register_user, scans_used
from core.services.exceptions import NotFound, InvalidState
```

Add the route after `login()`:

```python
@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    if not settings.registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is currently disabled")
    try:
        user = register_user(db, body.email, hash_password(body.password))
    except InvalidState:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    issue_session_cookie(response, user.id, settings)
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/api/test_auth.py -v -k register`
Expected: 6 passed

- [ ] **Step 5: Run the full auth test file to check for regressions**

Run: `.venv/bin/pytest tests/api/test_auth.py -v`
Expected: all passed

- [ ] **Step 6: Run the full backend test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add api/routes/auth.py tests/api/test_auth.py
git commit -m "feat: add POST /auth/register endpoint"
```

---

### Task 6: `AuthLayout` extraction + `register` in `AuthContext`/API client

**Files:**
- Create: `frontend/src/components/auth/AuthLayout.tsx`
- Modify: `frontend/src/components/auth/LoginPage.tsx`
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/contexts/AuthContext.tsx`
- Test: `frontend/src/contexts/AuthContext.test.tsx`

**Interfaces:**
- Produces: `AuthLayout({ children }: { children: React.ReactNode })` component; `auth.register(email, password): Promise<void>` API call; `useAuth().register: (email: string, password: string) => Promise<void>`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/contexts/AuthContext.test.tsx` (this file already has a `wrap()` helper and `server` from `../test/server`):

```tsx
  it("registers and authenticates", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json({ id: 2, email: "new@e.com", scan_limit: 5, scans_used: 0 })
      ),
      http.post("/api/v1/auth/register", () => HttpResponse.json(undefined))
    );
    function RegisterProbe() {
      const { isAuthenticated, register } = useAuth();
      return (
        <div>
          <span>{isAuthenticated ? "in" : "out"}</span>
          <button onClick={() => register("new@e.com", "longenough")}>register</button>
        </div>
      );
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider><RegisterProbe /></AuthProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("out")).toBeInTheDocument());
    await userEvent.click(screen.getByText("register"));
    await waitFor(() => expect(screen.getByText("in")).toBeInTheDocument());
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/contexts/AuthContext.test.tsx`
Expected: FAIL — `register` is not a function / `auth.register` doesn't exist

- [ ] **Step 3: Add `register` to the API client**

In `frontend/src/api/auth.ts`, add alongside `login`:

```ts
  register: (email: string, password: string) =>
    fetchApi<void>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
```

- [ ] **Step 4: Add `register` to `AuthContext`**

In `frontend/src/contexts/AuthContext.tsx`, add `register` to the `AuthCtx` interface:

```ts
  register: (email: string, password: string) => Promise<void>;
```

Add the implementation next to `login`:

```ts
  const register = async (email: string, password: string) => {
    await auth.register(email, password);
    await qc.invalidateQueries({ queryKey: ["me"] });
  };
```

Add `register` to the `Ctx.Provider` value object (alongside `login`, `logout`).

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/contexts/AuthContext.test.tsx`
Expected: 3 passed

- [ ] **Step 6: Extract `AuthLayout` (presentational refactor, no new test — covered by existing `LoginForm.test.tsx` continuing to pass through `LoginPage`'s existing behavior, which has no dedicated test file today)**

Create `frontend/src/components/auth/AuthLayout.tsx`:

```tsx
import { type ReactNode } from "react";
import { NaturePanel } from "./NaturePanel";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <NaturePanel />
      <div className="flex items-center justify-center bg-sand-50 p-8 dark:bg-[#0D0D0D]">
        {children}
      </div>
    </div>
  );
}
```

Update `frontend/src/components/auth/LoginPage.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { LoginForm } from "./LoginForm";
import { Spinner } from "../ui/Spinner";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <LoginForm />
    </AuthLayout>
  );
}
```

- [ ] **Step 7: Run the frontend test suite to check for regressions**

Run (from `frontend/`): `npx vitest run`
Expected: all passed

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/contexts/AuthContext.tsx frontend/src/contexts/AuthContext.test.tsx frontend/src/components/auth/AuthLayout.tsx frontend/src/components/auth/LoginPage.tsx
git commit -m "feat: add register API/context support and extract AuthLayout"
```

---

### Task 7: `RegisterForm` + `RegisterPage` + `/register` route + login-page link

**Files:**
- Create: `frontend/src/components/auth/RegisterForm.tsx`
- Create: `frontend/src/components/auth/RegisterForm.test.tsx`
- Create: `frontend/src/components/auth/RegisterPage.tsx`
- Modify: `frontend/src/components/auth/LoginForm.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useAuth().register` (Task 6), `AuthLayout` (Task 6), `Input`/`Button` (existing `components/ui/`), `ApiError` (`../../api/client`).
- Produces: `RegisterForm`, `RegisterPage` components; `/register` route in `App.tsx`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/auth/RegisterForm.test.tsx` (mirrors `LoginForm.test.tsx`):

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const register = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ register }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

import { RegisterForm } from "./RegisterForm";

describe("RegisterForm", () => {
  it("registers and navigates home on success", async () => {
    register.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });

  it("shows an error when passwords don't match, without calling register", async () => {
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument());
    expect(register).not.toHaveBeenCalled();
  });

  it("shows an error on 409 duplicate email", async () => {
    register.mockRejectedValueOnce(new ApiError(409, "Email already in use"));
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/email already in use/i)).toBeInTheDocument());
  });

  it("shows an error on 403 when registration is disabled", async () => {
    register.mockRejectedValueOnce(new ApiError(403, "Registration is currently disabled"));
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/registration is currently disabled/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/auth/RegisterForm.test.tsx`
Expected: FAIL — cannot find module `./RegisterForm`

- [ ] **Step 3: Implement `RegisterForm`**

Create `frontend/src/components/auth/RegisterForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function RegisterForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
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
      await register(email, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 403)) setError(err.message);
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Create an account</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Start tracking campsite availability</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Input id="password" label="Password" type="password" autoComplete="new-password"
        value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
      <Input id="confirm-password" label="Confirm password" type="password" autoComplete="new-password"
        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={8} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Creating account…" : "Create Account"}
      </Button>
      <p className="text-sm text-stone-500 dark:text-[#888]">
        Already have an account? <Link to="/login" className="text-forest-600 hover:underline">Sign in</Link>
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/auth/RegisterForm.test.tsx`
Expected: 4 passed

- [ ] **Step 5: Add `RegisterPage`**

Create `frontend/src/components/auth/RegisterPage.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { RegisterForm } from "./RegisterForm";
import { Spinner } from "../ui/Spinner";

export function RegisterPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <RegisterForm />
    </AuthLayout>
  );
}
```

- [ ] **Step 6: Add the "Create an account" link to `LoginForm`**

In `frontend/src/components/auth/LoginForm.tsx`, add the import:

```tsx
import { useNavigate, Link } from "react-router-dom";
```

(replacing the existing `import { useNavigate } from "react-router-dom";` line)

Add before the closing `</form>` tag, after the `<Button>`:

```tsx
      <p className="text-sm text-stone-500 dark:text-[#888]">
        Need an account? <Link to="/register" className="text-forest-600 hover:underline">Create one</Link>
      </p>
```

- [ ] **Step 7: Register the `/register` route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { RegisterPage } from "./components/auth/RegisterPage";
```

Add the route (after the `/login` route):

```tsx
        <Route path="/register" element={<RegisterPage />} />
```

- [ ] **Step 8: Run the full frontend test suite**

Run (from `frontend/`): `npx vitest run`
Expected: all passed

- [ ] **Step 9: Manually verify in the browser**

Run: `cd frontend && npm run dev`, then open `http://localhost:5173/login`, click "Create one", fill in the form, submit, and confirm you land on the dashboard logged in as the new user. Then log out and confirm the new account can log back in via `/login`.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/auth/RegisterForm.tsx frontend/src/components/auth/RegisterForm.test.tsx frontend/src/components/auth/RegisterPage.tsx frontend/src/components/auth/LoginForm.tsx frontend/src/App.tsx
git commit -m "feat: add registration page, form, and route"
```
