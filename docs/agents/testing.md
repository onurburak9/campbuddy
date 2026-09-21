# Testing Guide

## Stack

- `pytest` + `pytest-mock` (already in requirements)
- Always run with the venv: `.venv/bin/pytest` or activate first

## Rules

- Mock all external I/O: camply, httpx, smtplib, requests (Telegram)
- Use in-memory SQLite for all DB tests (`sqlite:///:memory:`)
- No test may make real network calls
- Tests live in `tests/` mirroring `core/` and `db/`

## Commands

```bash
pytest tests/ -v                                              # run all tests
pytest tests/ --cov=core --cov=db --cov-report=term-missing  # with coverage
```

## Frontend

Two layers, both run from `frontend/`:

```bash
npm test                # vitest — unit + component (jsdom, msw)
npm run test:e2e        # playwright — real Chromium against the dev server
npx tsc --noEmit        # typecheck (covers src/ and e2e/)
```

Rules:

- E2E specs live in `e2e/` and need no backend — every `/api/v1` call is stubbed
  through the single `page.route` handler in `e2e/support/app.ts`, so an
  unstubbed call fails loudly instead of hitting the dead dev proxy.
- vitest ignores `e2e/**` (see `vite.config.ts`); Playwright only reads `e2e/`.
- Never hard-code an absolute date in a test. Either pin the clock with
  `vi.useFakeTimers({ toFake: ["Date"] })`, or derive dates from today via
  `isoDaysFromToday()`. Fixed fixtures silently rot into the past.
