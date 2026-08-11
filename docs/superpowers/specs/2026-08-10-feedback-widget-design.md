# In-App Feedback Widget → GitHub Issues

## Problem

CampBuddy is about to be shared with friends. There's no lightweight way for them to report bugs or leave feedback without pinging the owner directly, and an email-only channel risks getting lost in an inbox. We want a small always-available widget that turns free-text feedback into a trackable GitHub issue.

## Scope

- A feedback button visible on every authenticated screen (dashboard, settings, admin).
- Submitting feedback captures the current page path and free-text message, and creates a GitHub issue in `onurburak9/campbuddy` labeled `feedback`, including the submitter's identity.
- If GitHub issue creation fails for any reason (missing/bad token, network error, rate limit), fall back to emailing the feedback to the owner via the existing SMTP setup, so feedback is never silently lost.

## Out of scope

- Feedback from logged-out screens (login/register/forgot-password) — the widget only mounts once a user is authenticated, so every submission is tied to a known user. No anonymous-submission or abuse-prevention design needed.
- A toast/notification system — the app doesn't have one today; the feedback modal shows its own inline success/error state.
- Two-way communication (e.g. replying to the friend from the issue) — out of scope for a v1 "let me tell you about a bug" channel.
- Rate limiting — trusted, low-volume, friends-and-family usage.

## Decisions

- **GitHub over email as primary channel**: an inbox is easy to miss; a GitHub issue is trackable, filterable (via the `feedback` label), and sits next to the existing dev workflow for this repo.
- **Email as fallback, not the primary path**: guarantees feedback survives a misconfigured or rate-limited GitHub token, without making email the everyday experience.
- **Auth-gated widget**: mounting it in `ProtectedRoute` (rather than globally in `App.tsx`) means every submission has a known user, sidestepping anonymous-abuse concerns entirely.
- **Single mount point**: `ProtectedRoute` wraps all three authenticated routes (`/`, `/settings`, `/admin`) individually today; rendering the widget there once covers all of them without touching three separate layout files.

## Backend

### Config

`config/settings.py` gains three fields:
- `github_token: str = ""` — a fine-grained PAT scoped to `onurburak9/campbuddy`'s Issues (read/write).
- `github_feedback_repo: str = "onurburak9/campbuddy"`
- `feedback_notify_email: str = ""` — fallback recipient; resolved to `smtp_user` at call time if left blank, so no new required config in the common case.

`.env.example` documents all three, with a comment on how to mint the PAT (Settings → Developer settings → Fine-grained tokens, repo-scoped, Issues: Read and write).

### `core/services/github_client.py` (new)

Mirrors the existing `ridb_assets.py` pattern (a thin, synchronous `httpx` client with its own error type):

```python
class GitHubIssueError(Exception):
    pass

def create_issue(repo: str, token: str, title: str, body: str, labels: list[str], timeout: float = 10.0) -> dict:
    ...
```

- Raises `GitHubIssueError` immediately if `token` is empty (no point making a request that will 401).
- POSTs to `https://api.github.com/repos/{repo}/issues` with the standard GitHub REST headers (`Accept: application/vnd.github+json`, `Authorization: Bearer {token}`).
- Raises `GitHubIssueError` on `httpx.HTTPError` or a non-2xx response, following the `AssetsSearchError` try/except shape.

### `core/services/feedback.py` (new)

```python
def submit_feedback(user: User, page_path: str, message: str, settings) -> None:
    ...
```

- Builds the issue title (`Feedback from {user.email}`) and body (page path, user id/email, UTC timestamp, the message).
- Calls `github_client.create_issue(settings.github_feedback_repo, settings.github_token, title, body, labels=["feedback"])`.
- On `GitHubIssueError`: logs a warning and falls back to `notifier.send_feedback_email(settings.feedback_notify_email or settings.smtp_user, page_path, user, message, settings)`.
- If the fallback email also raises, re-raises as `core.services.exceptions.UpstreamError` (already mapped to a 502 JSON response in `api/main.py`) — the only path where the caller sees a failure.

### `core/notifier.py`

New `send_feedback_email(to: str, page_path: str, user: User, message: str, settings) -> None`, following the same `MIMEText` + `smtplib` shape as the existing `send_*` functions in this module — plain-text, subject `"CampBuddy feedback from {user.email}"`, body includes page path, user email, timestamp, and the message.

### API

`api/schemas.py`: new `FeedbackCreate(BaseModel)`:
```python
class FeedbackCreate(BaseModel):
    page_path: str
    message: str = Field(min_length=1, max_length=2000)
```

`api/routes/feedback.py` (new):
```python
@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_feedback(body: FeedbackCreate, user=Depends(get_current_user)):
    feedback_svc.submit_feedback(user, body.page_path, body.message, get_settings())
```

`api/main.py`: `app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["feedback"])`.

## Frontend

`frontend/src/api/feedback.ts` (new), following the `scans.ts` pattern:
```ts
export const feedback = {
  submit: (pagePath: string, message: string) =>
    fetchApi<void>("/feedback", { method: "POST", body: JSON.stringify({ page_path: pagePath, message }) }),
};
```

`frontend/src/components/feedback/FeedbackWidget.tsx` (new):
- A small fixed-position button (bottom-right corner, visible over any screen content) that opens a modal with a textarea and a submit button.
- Reads the current path via `useLocation()` (`react-router-dom`) at submit time.
- Submit states: idle → submitting (disabled button + spinner) → success (inline "Thanks, filed!" message, modal auto-closes after ~2s) or error (inline "Couldn't send feedback, try again" message, modal stays open so the message isn't lost).

`frontend/src/components/auth/ProtectedRoute.tsx`: renders `<FeedbackWidget />` alongside `{children}` once authenticated, so it appears on `/`, `/settings`, and `/admin` without per-layout wiring.

## Testing

Per `docs/agents/testing.md` (mock all external I/O, in-memory SQLite):

- `tests/core/services/test_github_client.py`: mocks `httpx` (respx) — success, empty token, non-2xx response, network error, all raising/not raising `GitHubIssueError` as expected.
- `tests/core/services/test_feedback.py`: mocks `github_client.create_issue` and `notifier.send_feedback_email` — GitHub success (no email sent), GitHub failure → email fallback called with correct content, both fail → `UpstreamError` raised.
- `tests/api/test_feedback.py` (new): `POST /api/v1/feedback` — 202 on success (mocked service), 401 when unauthenticated, 502 when the service raises `UpstreamError`, 422 on empty/oversized message.
- Frontend: `FeedbackWidget.test.tsx` covering open → submit → success and open → submit → error, via the existing MSW setup (`frontend/src/test/server.ts`).
