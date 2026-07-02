# Per-scan auto-book flag, two-phase notifications, and sidecar batching

**Date:** 2026-07-01
**Status:** Approved (design)
**Branch:** `feat/per-scan-autobook-and-notify-ordering`

## Problem

A production scan (id 6) showed found sites in the UI but sent no email. Investigation
found three compounding issues:

1. **Auto cart-add is not configurable per scan.** It runs for every scan whenever the
   *user* has Recreation.gov credentials stored (`core/runner.py:101`). There is no
   per-scan toggle.
2. **Notification is gated behind cart-add and happens only at the very end of the run.**
   Non-carted sites are batched and the digest is sent only after the entire per-site
   loop finishes (`core/runner.py:137`). The run's `sites_found`/`outcome` are also only
   written at the end (`core/runner.py:151`). Each cart-add blocks up to 60s on the
   Playwright sidecar (`core/booking.py:12`), so a run with many sites takes tens of
   minutes — and if the process restarts mid-loop, the email never sends and the run is
   orphaned at `sites_found=0`/`outcome=null`.
3. **The sidecar logs into Recreation.gov from scratch on every single call**
   (`playwright_service/browser.py:85-124`), with deliberately slow "human typing." N
   sites = N full logins.

## Goals

1. A per-scan `auto_book` flag that cannot be enabled unless the owning user has both a
   Recreation.gov email and password.
2. Send an "available" digest **before** any cart-add (fast, reliable). When `auto_book`
   is on, always send a second "cart results" digest **after** attempting cart-add.
3. Optimize the sidecar so a run performs a single login instead of one per site, and so
   a slow/dead sidecar fails fast instead of costing 60s per site.

## Non-goals (deliberately out of scope — tracked as a follow-up ticket)

- Persistent warm browser pool kept alive across sidecar requests.
- Caching each user's authenticated `storage_state` (cookies) to skip login across runs.
- Retrying a *failed* Email #1 on the next run. `notify_on_new_only` dedup is keyed on
  result-row existence, so a failed email is not retried today; changing that risks
  duplicate result rows and is a separate change.

---

## Design

### 1. Per-scan `auto_book` flag

**Schema (`db/models.py`).** Add to `Scan`:

```python
auto_book: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Default `False` — a deliberate behavior change from today's implicit "on if creds exist."
Existing scans become non-auto-booking until the owner opts in. A migration is generated
in the same commit (per `docs/agents/schema-changes.md`) with a server default of `false`
for the backfill.

**API schemas (`api/schemas.py`).** Add `auto_book: bool = False` to `ScanCreate`,
`auto_book: Optional[bool] = None` to `ScanUpdate`, and `auto_book: bool` to
`ScanResponse`.

**Validation rule — "block at write + auto-disable on credential removal."**

- *Block at write:* enforced in the service layer (`core/services/scans.py`) inside
  `create_scan` and `update_scan`, where both the user row and incoming data are
  available. If the effective `auto_book` would be `True` and the user does not have
  **both** `recreationgov_email` and `recreationgov_password`, raise a new
  `ValidationFailed` exception mapped to HTTP 422. Add `auto_book` to the `_UPDATABLE`
  set. For `update_scan`, "effective" means the incoming value if present, else the
  scan's current value (so unrelated PATCHes to an already-auto-book scan are re-checked
  and rejected if creds vanished out-of-band).
- *Auto-disable on credential removal:* in `core/services/users.py::update_profile`,
  after applying changes, if the user no longer has both `recreationgov_email` and
  `recreationgov_password` (i.e. either was cleared to empty/null), set
  `auto_book = False` on all of that user's non-deleted scans in the same transaction.

**Exception mapping.** Add `ValidationFailed` to `core/services/exceptions.py` and a
handler in `api/main.py` returning 422 (mirroring how `LimitExceeded`/`InvalidState` are
surfaced today).

**Seed/CLI.** `config/scans.yaml` and the `cli.py seed` path accept an optional
`auto_book` per scan (default `False`). Seeding applies the same credential validation
and fails loudly if violated.

### 2. Two-phase notification flow

**Runner rewrite (`core/runner.py`).** New ordering:

1. **TX1 (fast):** load scan + user, create `ScanRun` with `started_at`.
2. **check_availability** — slow I/O, no lock held (unchanged).
3. **TX2 (fast):** apply `notify_on_new_only` dedup → `new_sites`. Insert a `ScanResult`
   for each new site (`cart_added=False`). Collect `(result_id, payload)`.
4. **Finalize the run now** — set `sites_found = len(sites)`,
   `outcome = "success" if sites else "no_results"`, `finished_at = now`. This happens
   *before* cart-add, so the run record is correct and complete even if the sidecar
   stage crashes. Cart-add and Email #2 are best-effort follow-ups that never mutate the
   run row.
5. **Email #1 — "available" digest** (`new_sites` only). Sent immediately.
   - On success: mark those results `notified=True`, `notified_at=now`.
   - On failure: log at ERROR, leave `notified=False` (honest flag). Do not abort the run.
   - If `new_sites` is empty, skip (nothing new to notify).
6. **If `scan.auto_book`** (defense-in-depth: and user has creds):
   - Health-preflight the sidecar. If down, skip cart-add; Email #2 reports
     "auto-book unavailable."
   - Otherwise send **one batch** cart-add request for all `new_sites` (see §3), then
     update each `ScanResult.cart_added`/`cart_added_at` from the per-site results.
   - **Email #2 — "cart results" digest**, always sent when `auto_book` is on (even if
     every cart-add failed). Wrapped in try/except, logged on failure; never affects the
     run row or the `notified` flag.

`sites_found` retains today's meaning (total sites found this run, not just new). Both
emails are mirrored to Telegram when `notify_via_telegram` is set.

**Notifier (`core/notifier.py`).** Replace the current `notify()` (per-site immediate) and
`notify_digest()` with two phase-aware entry points:

- `notify_available(scan, payloads, settings)` — subject/body: "N sites available — book
  now," manual booking links. If `scan.auto_book`, append a line noting an auto-book
  attempt is in progress and a follow-up will arrive.
- `notify_cart_results(scan, payloads, settings)` — subject/body: which sites are now in
  the cart ("pay within ~15 min") vs. which failed ("book manually"), based on each
  payload's `cart_added`. Also handles the "auto-book unavailable" case.

Each fans out to email and/or Telegram per the scan's channel flags, reusing the existing
`send_email*` / `send_telegram*` helpers (extended for the two subjects/bodies). Send
failures are caught and logged per channel, as today.

### 3. Sidecar batching

**New batch endpoint (`playwright_service/`).** `POST /add-to-cart-batch`:

```jsonc
// request
{ "email": "...", "password": "...",
  "sites": [ {"booking_url": "...", "check_in": "MM-DD-YYYY", "check_out": "MM-DD-YYYY"}, ... ] }
// response — results aligned by index with request.sites
{ "results": [ {"success": true, "error": null}, {"success": false, "error": "..."} ] }
```

Behavior: **log in once**, reuse the same authenticated context/page, then loop the sites
adding each to cart, collecting a per-site result. A failure on one site is captured and
the loop continues to the next. `browser.py` is refactored so the login step and the
single-site cart step are reusable helpers shared by both `/add-to-cart` (kept for the
CLI `test-notify` and back-compat) and `/add-to-cart-batch`.

**Client + timeout hygiene (`core/booking.py`).** Add `attempt_cart_add_batch(sites, ...)`
that calls the batch endpoint with one bounded overall timeout (scaled to site count,
not 60s × N) and returns the aligned results. Add a `sidecar_healthy()` preflight
(`GET /health`, short timeout) used by the runner to fail fast when the sidecar is down.
The existing single `attempt_cart_add` remains for the CLI path.

---

## Data flow (auto_book on, happy path)

```
scheduler → run_scan
  TX1: ScanRun(started_at)
  check_availability → sites
  TX2: dedup → new_sites; insert ScanResults; finalize run (sites_found, outcome, finished_at)
  Email #1 "available" → on success mark new_sites notified
  sidecar /health ok → POST /add-to-cart-batch (1 login, N adds)
       → update ScanResult.cart_added per site
  Email #2 "cart results"
```

## Error handling

| Failure | Behavior |
|---|---|
| `check_availability` raises | Run marked `outcome=error`, `error_message`; no emails (unchanged). |
| Email #1 send fails | Logged; results stay `notified=False`; run already finalized; cart-add still proceeds. |
| Sidecar `/health` down | Skip cart-add; Email #2 = "auto-book unavailable." |
| Batch request fails/times out | All sites `cart_added=False`; Email #2 reports manual-booking. |
| Email #2 send fails | Logged; run + results unaffected. |
| Process restart after step 4 | Run record already complete; only the (best-effort) cart-add/Email #2 are lost. |

## Testing

Mock all external I/O (camply, httpx to sidecar, smtplib, Telegram); in-memory SQLite
(`docs/agents/testing.md`).

- **Model/migration:** `auto_book` default False; migration upgrade/downgrade round-trips.
- **Validation:** create/update with `auto_book=true` and no creds → 422; with creds → ok.
  Clearing creds via `update_profile` flips `auto_book=false` on all the user's scans.
  Effective-value check on unrelated PATCH.
- **Runner ordering:** run is finalized (`sites_found`/`outcome`/`finished_at`) before
  cart-add; Email #1 sent before any sidecar call (assert call order); Email #2 sent iff
  `auto_book`; `notified` set only on Email #1 success; crash during cart-add leaves run
  finalized and results committed.
- **Notifier:** phase-1 vs phase-2 subject/body; auto-book "in progress" line; cart
  results split (in-cart vs manual); channel fan-out honoring `notify_via_email` /
  `notify_via_telegram`.
- **Sidecar/client:** batch aligns results by index; one login for N sites; a single-site
  failure doesn't abort the batch; `sidecar_healthy()` preflight; bounded batch timeout.

## Follow-up (separate ticket)

Persistent warm browser pool + cross-run `storage_state` (cookie) caching, and
retry-on-failed-notification. Tracked in
[onurburak9/campbuddy#24](https://github.com/onurburak9/campbuddy/issues/24).
