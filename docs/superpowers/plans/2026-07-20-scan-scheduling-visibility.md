# Scan Scheduling Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A newly created scan gets checked within seconds instead of up to ~6 minutes, editing a running scan's interval actually changes its cadence, and the API/UI surface when the next check will happen and how long the last one took.

**Architecture:** All scheduling logic lives in `core/scheduler.py`'s `sync_jobs()`, which already polls the DB and diffs against APScheduler's live job set every cycle. We extend that diff: scans with zero `ScanRun` rows get an explicit `next_run_time=now` on `add_job()` (bypassing `IntervalTrigger`'s own "first fire = now+interval" default), and scans whose `polling_interval` no longer matches their live job's interval get removed and re-added with the new interval. `next_run_at`/`last_run_duration_seconds` are derived from existing `ScanRun` rows inside `core/services/history.py`'s `stats()` — no new columns, no scheduler-to-DB writes. The frontend renders those two new stats fields and polls briefly (via React Query's `refetchInterval`) until the scan's first run lands.

**Tech Stack:** APScheduler 3.10.4 (already a dependency) — specifically its `add_job(..., next_run_time=...)` parameter, which overrides a job's first scheduled fire time regardless of what its trigger would otherwise compute, while every fire after that still derives from `previous_fire_time + interval`. TanStack Query v5's function-form `refetchInterval` (already a dependency) for self-stopping polling.

## Global Constraints

- No DB migration in this plan — every new value is derived from existing `Scan`/`ScanRun` columns at read time.
- The scheduler process is the sole trigger of scan runs; no API-triggered "run now" endpoint is added.
- `sync_jobs()`'s own discovery cadence goes from 60s to 30s (not lower — avoid materially increasing DB polling load).
- "Fire immediately" eligibility is keyed off **`ScanRun` row existence in the DB**, never off APScheduler's in-memory job set — a scheduler process restart must not cause every active scan to fire at once.
- Changing `polling_interval` on a scan that has already run does **not** force an immediate fire — only genuinely never-run scans get `next_run_time=now`.
- Backend datetimes are always timezone-aware UTC (`datetime.now(timezone.utc)`), matching `core/services/scans.py` and `core/runner.py`.
- Mock all external I/O; backend tests use in-memory SQLite via the existing `factory`/`db` fixtures in `tests/test_scheduler.py` and `tests/services/conftest.py`.

---

## File Structure

- **Modify** `core/scheduler.py` — `sync_jobs()` gains never-run detection (drives `next_run_time`) and a third diff loop for interval-changed jobs; `start_scheduler()`'s own sync interval drops to 30s. New private helper `_add_scan_job()` centralizes job creation so both the "add" and "reschedule" loops share the same never-run logic.
- **Modify** `tests/test_scheduler.py` — new tests for immediate-fire eligibility, restart-safety, interval-change propagation, and the 30s cadence.
- **Modify** `core/services/history.py` — `stats()` gains `next_run_at` and `last_run_duration_seconds`, computed from the `ScanRun` rows it already loads (no new queries).
- **Modify** `tests/services/test_history.py` — new tests for both fields across paused/never-run/recently-run/long-idle scans.
- **Modify** `api/schemas.py` — `ScanStatsResponse` gains the two new optional fields.
- **Modify** `tests/api/test_scans.py` — route test asserting the new fields appear in `GET /scans/{id}/stats`.
- **Modify** `frontend/src/lib/format.ts` — new `relativeFuture()` and `formatSeconds()` (the latter extracted out of the existing `duration()`).
- **Modify** `frontend/src/lib/format.test.ts` — tests for both.
- **Modify** `frontend/src/types/index.ts` — `ScanStats` gains `next_run_at`/`last_run_duration_seconds`.
- **Modify** `frontend/src/hooks/useScans.ts` — `useScanStats` self-gates a 5s `refetchInterval` while its own last-fetched `total_runs` is 0.
- **Modify** `frontend/src/hooks/useRuns.ts` — `useScanRuns` gains an optional trailing `options?: { refetchInterval?: number | false }` param, passed straight through; existing callers (`RunHistoryTab`) are unaffected since they don't pass it.
- **Modify** `frontend/src/components/scans/OverviewTab.tsx` — renders "Next run" / "Last run took", and drives `useScanRuns`'s new option from `stats.total_runs`.
- **Modify** `frontend/src/components/scans/OverviewTab.test.tsx` — assertions for the two new lines.
- **Modify** `frontend/src/components/scans/ConfigCard.tsx` — one-line target-count summary ("Monitoring 2 campgrounds across 1 recreation area").
- **Modify** `frontend/src/components/scans/ConfigCard.test.tsx` — assertions for the summary line.

---

### Task 1: Immediate first run for never-run scans + faster discovery poll

**Files:**
- Modify: `core/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `_add_scan_job(scheduler, scan, session_factory, settings, immediate: bool) -> None` — private helper, consumed by Task 2 inside the same file.
- Produces (behavioral): a scan with zero `ScanRun` rows gets `add_job(..., next_run_time=<now>)`; a scan with at least one `ScanRun` row gets today's unmodified `add_job(...)` call (no `next_run_time` kwarg, `IntervalTrigger` defaults to `now + interval`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py` (after the existing tests, same file):

```python
def test_sync_sets_immediate_next_run_time_for_never_run_scan(factory):
    scan_id = add_scan(factory, status="active", interval=300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    kwargs = scheduler.add_job.call_args[1]
    assert kwargs["id"] == f"scan_{scan_id}"
    assert "next_run_time" in kwargs
    assert kwargs["next_run_time"] is not None


def test_sync_does_not_set_next_run_time_for_scan_with_run_history(factory):
    from datetime import datetime, timezone
    from db.models import ScanRun, ScanOutcome
    scan_id = add_scan(factory, status="active", interval=300)
    with factory() as db:
        db.add(ScanRun(
            scan_id=scan_id, started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0,
        ))
        db.commit()
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    kwargs = scheduler.add_job.call_args[1]
    assert "next_run_time" not in kwargs


def test_start_scheduler_syncs_every_30_seconds(factory):
    from core.scheduler import start_scheduler
    scheduler = start_scheduler(factory, MagicMock())
    try:
        job = scheduler.get_job("__sync_jobs__")
        assert job.trigger.interval.total_seconds() == 30
    finally:
        scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler.py -v -k "immediate_next_run_time or does_not_set_next_run_time or syncs_every_30"`
Expected: FAIL — the first two with `AssertionError` (no `next_run_time` key is ever passed today), the third with `AssertionError: assert 60.0 == 30`.

- [ ] **Step 3: Write the implementation**

Replace the full contents of `core/scheduler.py` with:

```python
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from core.runner import run_scan

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")


def _add_scan_job(scheduler, scan, session_factory, settings, immediate: bool) -> None:
    job_id = f"scan_{scan.id}"
    kwargs = dict(
        trigger=IntervalTrigger(seconds=scan.polling_interval),
        id=job_id,
        args=[scan.id, session_factory, settings],
        max_instances=1,
        coalesce=True,
    )
    if immediate:
        kwargs["next_run_time"] = _now()
    scheduler.add_job(run_scan, **kwargs)
    logger.info(
        "Scheduled %s every %ds%s", job_id, scan.polling_interval,
        " (immediate first run)" if immediate else "",
    )


def sync_jobs(scheduler: BackgroundScheduler, session_factory, settings) -> None:
    from db.models import Scan, ScanRun
    with session_factory() as db:
        active = db.query(Scan).filter(Scan.status == "active", Scan.deleted_at.is_(None)).all()
        active_ids = {f"scan_{s.id}" for s in active}
        active_map = {f"scan_{s.id}": s for s in active}
        scan_ids_with_runs = {
            row[0] for row in db.query(ScanRun.scan_id)
            .filter(ScanRun.scan_id.in_([s.id for s in active]))
            .distinct()
            .all()
        }

    existing_ids = {job.id for job in scheduler.get_jobs() if job.id.startswith("scan_")}

    for job_id in existing_ids - active_ids:
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)

    for job_id in active_ids - existing_ids:
        scan = active_map[job_id]
        never_run = scan.id not in scan_ids_with_runs
        _add_scan_job(scheduler, scan, session_factory, settings, immediate=never_run)


def start_scheduler(session_factory, settings) -> BackgroundScheduler:
    scheduler = build_scheduler()
    sync_jobs(scheduler, session_factory, settings)
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(seconds=30),
        id="__sync_jobs__",
        args=[scheduler, session_factory, settings],
    )
    scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler.py -v`
Expected: PASS — all tests in the file, including the four pre-existing ones (`test_sync_adds_active_scan`, `test_sync_skips_paused_scan`, `test_sync_skips_deleted_scan`, `test_sync_removes_stale_job`), which are unaffected by this change.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: fire a never-run scan's first check immediately, poll for new scans every 30s"
```

---

### Task 2: Propagate `polling_interval` edits to already-scheduled jobs

**Files:**
- Modify: `core/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `_add_scan_job(scheduler, scan, session_factory, settings, immediate: bool) -> None` from Task 1.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py`:

```python
from apscheduler.triggers.interval import IntervalTrigger


def _fake_job(job_id, interval_seconds):
    job = MagicMock()
    job.id = job_id
    job.trigger = IntervalTrigger(seconds=interval_seconds)
    return job


def test_sync_reschedules_job_when_interval_changed(factory):
    from datetime import datetime, timezone
    from db.models import ScanRun, ScanOutcome
    scan_id = add_scan(factory, status="active", interval=300)
    with factory() as db:
        db.add(ScanRun(
            scan_id=scan_id, started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0,
        ))
        db.query(Scan).filter(Scan.id == scan_id).update({"polling_interval": 60})
        db.commit()
    existing_job = _fake_job(f"scan_{scan_id}", 300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [existing_job]
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.remove_job.assert_called_once_with(f"scan_{scan_id}")
    scheduler.add_job.assert_called_once()
    kwargs = scheduler.add_job.call_args[1]
    assert kwargs["trigger"].interval.total_seconds() == 60
    assert "next_run_time" not in kwargs  # already ran before — no forced immediate fire


def test_sync_leaves_job_untouched_when_interval_unchanged(factory):
    scan_id = add_scan(factory, status="active", interval=300)
    existing_job = _fake_job(f"scan_{scan_id}", 300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [existing_job]
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.remove_job.assert_not_called()
    scheduler.add_job.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler.py -v -k "reschedules_job_when_interval_changed or leaves_job_untouched"`
Expected: FAIL — `test_sync_reschedules_job_when_interval_changed` fails because `scheduler.remove_job` is never called today (the intersection of active+existing scans is never revisited).

- [ ] **Step 3: Write the implementation**

In `core/scheduler.py`, inside `sync_jobs()`, change this line:

```python
    existing_ids = {job.id for job in scheduler.get_jobs() if job.id.startswith("scan_")}
```

to:

```python
    existing_jobs = {job.id: job for job in scheduler.get_jobs() if job.id.startswith("scan_")}
    existing_ids = set(existing_jobs)
```

Then, after the `for job_id in active_ids - existing_ids:` loop, add:

```python
    for job_id in active_ids & existing_ids:
        scan = active_map[job_id]
        job = existing_jobs[job_id]
        if job.trigger.interval.total_seconds() != scan.polling_interval:
            scheduler.remove_job(job_id)
            never_run = scan.id not in scan_ids_with_runs
            _add_scan_job(scheduler, scan, session_factory, settings, immediate=never_run)
            logger.info("Rescheduled %s: interval changed to %ds", job_id, scan.polling_interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "fix: propagate polling_interval edits to already-scheduled scan jobs"
```

---

### Task 3: Expose `next_run_at` and `last_run_duration_seconds` from the stats endpoint

**Files:**
- Modify: `core/services/history.py`
- Modify: `api/schemas.py`
- Test: `tests/services/test_history.py`
- Test: `tests/api/test_scans.py`

**Interfaces:**
- Produces: `stats(db, scan_id, user_id) -> dict` now includes `next_run_at: datetime | None` and `last_run_duration_seconds: float | None` alongside the four existing keys.
- Produces: `ScanStatsResponse` (`api/schemas.py`) gains `next_run_at: Optional[datetime]` and `last_run_duration_seconds: Optional[float]` — consumed by the frontend in Task 5 via the JSON field names `next_run_at` / `last_run_duration_seconds`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/test_history.py`:

```python
def test_stats_next_run_at_none_for_paused_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status="paused")
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["next_run_at"] is None


def test_stats_next_run_at_now_for_never_run_active_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["next_run_at"] is not None
    assert abs((result["next_run_at"] - datetime.now(timezone.utc)).total_seconds()) < 5


def test_stats_next_run_at_clamped_to_now_when_overdue(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, polling_interval=300)
    db.add(scan)
    db.flush()
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(ScanRun(
        scan_id=scan.id, started_at=started, finished_at=started + timedelta(seconds=5),
        outcome=ScanOutcome.success, sites_found=0,
    ))
    db.flush()
    result = stats(db, scan.id, u.id)
    # last run was an hour ago with a 300s interval — the "real" next fire is long past, clamp to now
    assert abs((result["next_run_at"] - datetime.now(timezone.utc)).total_seconds()) < 5


def test_stats_next_run_at_in_the_future_when_recently_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, polling_interval=300)
    db.add(scan)
    db.flush()
    started = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.add(ScanRun(
        scan_id=scan.id, started_at=started, finished_at=started + timedelta(seconds=2),
        outcome=ScanOutcome.success, sites_found=0,
    ))
    db.flush()
    result = stats(db, scan.id, u.id)
    expected = started + timedelta(seconds=300)
    assert abs((result["next_run_at"] - expected).total_seconds()) < 2


def test_stats_last_run_duration_seconds_none_when_no_finished_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["last_run_duration_seconds"] is None


def test_stats_last_run_duration_seconds_from_most_recently_started_finished_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    older_start = datetime.now(timezone.utc) - timedelta(hours=1)
    newer_start = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.add_all([
        ScanRun(scan_id=scan.id, started_at=older_start, finished_at=older_start + timedelta(seconds=20),
                outcome=ScanOutcome.success, sites_found=0),
        ScanRun(scan_id=scan.id, started_at=newer_start, finished_at=newer_start + timedelta(seconds=7),
                outcome=ScanOutcome.success, sites_found=0),
    ])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["last_run_duration_seconds"] == 7
```

Update the import line at the top of `tests/services/test_history.py` from:

```python
from datetime import datetime, date, timezone, timedelta
```

(already imports everything needed — no change required there).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_history.py -v -k "next_run_at or last_run_duration"`
Expected: FAIL with `KeyError: 'next_run_at'` (the key doesn't exist in the returned dict yet).

- [ ] **Step 3: Write the implementation**

In `core/services/history.py`, change the imports at the top from:

```python
from db.models import ScanRun, ScanResult, ScanOutcome
from core.services.scans import get_scan
from core.services.exceptions import NotFound
```

to:

```python
from datetime import datetime, timezone, timedelta
from db.models import ScanRun, ScanResult, ScanOutcome, ScanStatus
from core.services.scans import get_scan
from core.services.exceptions import NotFound


def _now():
    return datetime.now(timezone.utc)
```

Then replace the `stats` function body:

```python
def stats(db, scan_id: int, user_id: int) -> dict:
    scan = get_scan(db, scan_id, user_id)
    sites_found = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).count()
    in_cart = (
        db.query(ScanResult)
        .filter(ScanResult.scan_id == scan_id, ScanResult.cart_added.is_(True))
        .count()
    )
    runs = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).all()
    total_runs = len(runs)
    if total_runs == 0:
        success_rate = 0
    else:
        successful = sum(
            1 for r in runs
            if r.outcome in (ScanOutcome.success, ScanOutcome.no_results)
        )
        success_rate = round(successful / total_runs * 100)

    latest_run = max(runs, key=lambda r: r.started_at, default=None)
    if scan.status != ScanStatus.active:
        next_run_at = None
    elif latest_run is None:
        next_run_at = _now()
    else:
        candidate = latest_run.started_at + timedelta(seconds=scan.polling_interval)
        next_run_at = max(_now(), candidate)

    finished_runs = [r for r in runs if r.finished_at is not None]
    last_finished_run = max(finished_runs, key=lambda r: r.started_at, default=None)
    last_run_duration_seconds = (
        (last_finished_run.finished_at - last_finished_run.started_at).total_seconds()
        if last_finished_run else None
    )

    return {
        "sites_found": sites_found,
        "in_cart": in_cart,
        "total_runs": total_runs,
        "success_rate": success_rate,
        "next_run_at": next_run_at,
        "last_run_duration_seconds": last_run_duration_seconds,
    }
```

In `api/schemas.py`, change `ScanStatsResponse` from:

```python
class ScanStatsResponse(BaseModel):
    sites_found: int
    in_cart: int
    total_runs: int
    success_rate: int

    class Config:
        orm_mode = True
```

to:

```python
class ScanStatsResponse(BaseModel):
    sites_found: int
    in_cart: int
    total_runs: int
    success_rate: int
    next_run_at: Optional[datetime]
    last_run_duration_seconds: Optional[float]

    class Config:
        orm_mode = True
```

Add to `tests/api/test_scans.py` (near the other stats-adjacent tests):

```python
def test_get_stats_includes_next_run_and_duration_fields(auth_client):
    client, _ = auth_client
    create = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    scan_id = create.json()["id"]
    resp = client.get(f"/api/v1/scans/{scan_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "next_run_at" in data
    assert data["next_run_at"] is not None  # never-run active scan → "now"
    assert data["last_run_duration_seconds"] is None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_history.py tests/api/test_scans.py -v`
Expected: PASS — all tests in both files, including every pre-existing `test_stats_*` test (unchanged return keys, only additive).

- [ ] **Step 5: Commit**

```bash
git add core/services/history.py api/schemas.py tests/services/test_history.py tests/api/test_scans.py
git commit -m "feat: expose next_run_at and last_run_duration_seconds on scan stats"
```

---

### Task 4: Frontend format helpers and `ScanStats` type

**Files:**
- Modify: `frontend/src/lib/format.ts`
- Modify: `frontend/src/types/index.ts`
- Test: `frontend/src/lib/format.test.ts`

**Interfaces:**
- Produces: `relativeFuture(iso: string): string` — consumed by Task 5.
- Produces: `formatSeconds(seconds: number): string` — consumed by Task 5.
- Produces: `ScanStats` gains `next_run_at: string | null` and `last_run_duration_seconds: number | null` — consumed by Task 5.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/lib/format.test.ts`, inside the existing `describe("format", ...)` block (it already freezes time at `2026-06-24T12:00:00Z` via `beforeEach`):

```ts
  it("relativeFuture renders \"due now\" for a due or overdue time", () => {
    expect(relativeFuture("2026-06-24T12:00:00Z")).toBe("due now");
    expect(relativeFuture("2026-06-24T11:59:00Z")).toBe("due now");
  });
  it("relativeFuture renders minutes ahead", () => {
    expect(relativeFuture("2026-06-24T12:05:00Z")).toMatch(/in 5 min/);
  });
  it("relativeFuture renders hours ahead", () => {
    expect(relativeFuture("2026-06-24T15:00:00Z")).toMatch(/in 3 hr/);
  });
  it("formatSeconds renders sub-minute and multi-minute durations", () => {
    expect(formatSeconds(12)).toBe("12s");
    expect(formatSeconds(75)).toBe("1m 15s");
  });
```

Update the import line at the top of the test file from:

```ts
import { relativeTime, dateRange, duration, dateTime } from "./format";
import { formatInterval } from "./format";
```

to:

```ts
import { relativeTime, dateRange, duration, dateTime, relativeFuture, formatSeconds } from "./format";
import { formatInterval } from "./format";
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL with `relativeFuture is not a function` / `formatSeconds is not a function` (they don't exist yet).

- [ ] **Step 3: Write the implementation**

In `frontend/src/lib/format.ts`, replace the existing `duration` function:

```ts
export function duration(start: string, end: string | null): string {
  if (!end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  return `${min}m ${sec % 60}s`;
}
```

with:

```ts
export function formatSeconds(seconds: number): string {
  const sec = Math.round(seconds);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  return `${min}m ${sec % 60}s`;
}

export function duration(start: string, end: string | null): string {
  if (!end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return formatSeconds(ms / 1000);
}

export function relativeFuture(iso: string): string {
  const then = new Date(iso).getTime();
  const diffSec = Math.round((then - Date.now()) / 1000);
  if (diffSec <= 0) return "due now";
  if (diffSec < 60) return `in ${diffSec}s`;
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `in ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `in ${hours} hr`;
  const days = Math.round(hours / 24);
  return `in ${days} day${days === 1 ? "" : "s"}`;
}
```

In `frontend/src/types/index.ts`, change the `ScanStats` interface from:

```ts
export interface ScanStats {
  sites_found: number;
  in_cart: number;
  total_runs: number;
  success_rate: number; // 0–100
}
```

to:

```ts
export interface ScanStats {
  sites_found: number;
  in_cart: number;
  total_runs: number;
  success_rate: number; // 0–100
  next_run_at: string | null;
  last_run_duration_seconds: number | null;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: PASS — all tests in the file, including the pre-existing `duration renders seconds` test (still `"12s"` — `formatSeconds` preserves the exact same rounding/formatting behavior it was extracted from).

Run: `cd frontend && npx tsc --noEmit`
Expected: no new type errors (confirms nothing else destructures `ScanStats` in a way that breaks).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/lib/format.ts src/lib/format.test.ts src/types/index.ts
git commit -m "feat: add relativeFuture/formatSeconds helpers and extend ScanStats type"
```

---

### Task 5: OverviewTab — show next run, last run duration, and auto-refresh until the first run lands

**Files:**
- Modify: `frontend/src/hooks/useScans.ts`
- Modify: `frontend/src/hooks/useRuns.ts`
- Modify: `frontend/src/components/scans/OverviewTab.tsx`
- Test: `frontend/src/components/scans/OverviewTab.test.tsx`

**Interfaces:**
- Consumes: `relativeFuture`, `formatSeconds` from Task 4 (`frontend/src/lib/format.ts`).
- Consumes: `ScanStats.next_run_at`, `ScanStats.last_run_duration_seconds` from Task 4 (`frontend/src/types/index.ts`).
- Produces: `useScanRuns(scanId, page, pageSize?, outcome?, startedAfter?, options?: { refetchInterval?: number | false })` — 6th param is additive and optional; existing 5-arg call sites (`RunHistoryTab.tsx`) are unaffected.

- [ ] **Step 1: Write the failing test**

Replace `frontend/src/components/scans/OverviewTab.test.tsx` with:

```tsx
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { OverviewTab } from "./OverviewTab";
import type { Scan } from "../../types";

const scan = { id: 7, search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }] } as unknown as Scan;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OverviewTab", () => {
  it("shows last checked and last new site found", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80,
        next_run_at: "2026-06-24T12:05:00Z", last_run_duration_seconds: 12,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([{ id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null }])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([{ id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "F", site_name: "S", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z", last_seen_at: "2026-06-30T11:00:00Z", is_available: true, cart_added: false, notified: true }])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Last checked/i)).toBeInTheDocument());
    expect(screen.getByText(/Last new site found/i)).toBeInTheDocument();
  });

  it("shows next run time and last run duration from stats", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80,
        next_run_at: "2026-06-24T12:05:00Z", last_run_duration_seconds: 12,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Next run/i)).toBeInTheDocument());
    expect(screen.getByText(/in 5 min/)).toBeInTheDocument();
    expect(screen.getByText(/Last run took/i)).toBeInTheDocument();
    expect(screen.getByText("12s")).toBeInTheDocument();
  });

  it("shows dashes for next run and last run duration when absent", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 0, in_cart: 0, total_runs: 0, success_rate: 0,
        next_run_at: null, last_run_duration_seconds: null,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Next run/i)).toBeInTheDocument());
    const nextRunRow = screen.getByText(/Next run/i).closest("span");
    expect(nextRunRow).toHaveTextContent("—");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/scans/OverviewTab.test.tsx`
Expected: FAIL — `screen.getByText(/Next run/i)` not found (the line doesn't exist yet), and the MSW handlers' new `next_run_at`/`last_run_duration_seconds` fields aren't rendered.

- [ ] **Step 3: Write the implementation**

In `frontend/src/hooks/useScans.ts`, change `useScanStats`:

```ts
export function useScanStats(id: number | null) {
  return useQuery({
    queryKey: id ? queryKeys.stats(id) : ["scans", "none", "stats"],
    queryFn: () => scans.stats(id as number),
    enabled: id != null,
    refetchInterval: (query) =>
      query.state.data && query.state.data.total_runs === 0 ? 5000 : false,
  });
}
```

In `frontend/src/hooks/useRuns.ts`, change the `useScanRuns` signature and body:

```ts
export function useScanRuns(
  scanId: number | null,
  page: number,
  pageSize: number = PAGE_SIZE,
  outcome?: string,
  startedAfter?: string,
  options?: { refetchInterval?: number | false },
) {
  return useQuery({
    queryKey: scanId ? queryKeys.runs(scanId, page, pageSize, outcome, startedAfter) : ["scans", "none", "runs", page],
    queryFn: () => runs.list(scanId as number, page, pageSize, outcome, startedAfter),
    enabled: scanId != null,
    refetchInterval: options?.refetchInterval,
  });
}
```

Replace `frontend/src/components/scans/OverviewTab.tsx` with:

```tsx
import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { useScanResults } from "../../hooks/useResults";
import { relativeTime, relativeFuture, formatSeconds } from "../../lib/format";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { ConfigCard } from "./ConfigCard";
import type { Scan } from "../../types";

export function OverviewTab({ scan }: { scan: Scan }) {
  const { data: stats } = useScanStats(scan.id);
  const { data: runs = [] } = useScanRuns(scan.id, 1, undefined, undefined, undefined, {
    refetchInterval: stats?.total_runs === 0 ? 5000 : false,
  });
  const { data: results = [] } = useScanResults(scan.id, 1);

  const lastChecked = runs[0]?.started_at;
  const lastFound = results[0]?.first_seen_at;

  return (
    <div className="space-y-6">
      <StatsRow
        sitesFound={stats?.sites_found ?? 0}
        inCart={stats?.in_cart ?? 0}
        totalRuns={stats?.total_runs ?? 0}
        successRate={stats?.success_rate ?? 0}
      />
      <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm text-stone-500 dark:text-[#888]">
        <span>Last checked: <span className="text-stone-700 dark:text-[#CCC]">{lastChecked ? relativeTime(lastChecked) : "—"}</span></span>
        <span>Last new site found: <span className="text-stone-700 dark:text-[#CCC]">{lastFound ? relativeTime(lastFound) : "—"}</span></span>
        <span>Next run: <span className="text-stone-700 dark:text-[#CCC]">{stats?.next_run_at ? relativeFuture(stats.next_run_at) : "—"}</span></span>
        <span>Last run took: <span className="text-stone-700 dark:text-[#CCC]">{stats?.last_run_duration_seconds != null ? formatSeconds(stats.last_run_duration_seconds) : "—"}</span></span>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Recent Run Health</h3>
        <RunHealthBar runs={runs} />
      </div>
      <ConfigCard scan={scan} />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/scans/OverviewTab.test.tsx src/hooks/useScans.test.tsx`
Expected: PASS — all tests in both files.

Run: `cd frontend && npx vitest run src/components/scans/RunHistoryTab.test.tsx` (if it exists) — confirms the additive 6th param on `useScanRuns` doesn't break its 5-arg call site.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/hooks/useScans.ts src/hooks/useRuns.ts src/components/scans/OverviewTab.tsx src/components/scans/OverviewTab.test.tsx
git commit -m "feat: show next run and last run duration on the scan overview"
```

---

### Task 6: ConfigCard — target-count summary line

**Files:**
- Modify: `frontend/src/components/scans/ConfigCard.tsx`
- Test: `frontend/src/components/scans/ConfigCard.test.tsx`

**Interfaces:**
- None — self-contained, reads only fields already on `Scan` (`rec_area_ids`, `campground_ids`, `campsite_ids`).

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/scans/ConfigCard.test.tsx`, inside the existing `describe("ConfigCard", ...)` block:

```tsx
  it("renders a target-count summary line", () => {
    render(<ConfigCard scan={scan} />);
    expect(screen.getByText("Monitoring 2 campgrounds")).toBeInTheDocument();
  });

  it("joins multiple target categories in the summary", () => {
    render(<ConfigCard scan={scanWithAllIds} />);
    expect(
      screen.getByText("Monitoring 1 campground across 1 recreation area across 1 campsite"),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/scans/ConfigCard.test.tsx`
Expected: FAIL — `getByText("Monitoring 2 campgrounds")` not found (no summary line exists yet).

- [ ] **Step 3: Write the implementation**

In `frontend/src/components/scans/ConfigCard.tsx`, add above the `Row` function:

```tsx
function countLabel(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function targetSummary(scan: Scan): string | null {
  const parts = [
    scan.campground_ids?.length ? countLabel(scan.campground_ids.length, "campground") : null,
    scan.rec_area_ids?.length ? countLabel(scan.rec_area_ids.length, "recreation area") : null,
    scan.campsite_ids?.length ? countLabel(scan.campsite_ids.length, "campsite") : null,
  ].filter(Boolean) as string[];
  return parts.length ? `Monitoring ${parts.join(" across ")}` : null;
}
```

Then in the `ConfigCard` component, add the summary right after the `notifs` computation and render it below the heading:

```tsx
export function ConfigCard({ scan }: { scan: Scan }) {
  const notifs =
    [
      scan.notify_via_email ? "Email" : null,
      scan.notify_via_telegram ? "Telegram" : null,
      scan.notify_on_new_only ? "New only" : null,
    ]
      .filter(Boolean)
      .join(" · ") || "None";
  const summary = targetSummary(scan);

  return (
    <div className="rounded-lg border border-sand-200 bg-white p-5 dark:border-[#222] dark:bg-[#1A1A1A]">
      <h3 className="mb-3 text-sm font-semibold text-stone-800 dark:text-[#EEE]">Configuration</h3>
      {summary && (
        <p className="mb-3 text-sm text-stone-600 dark:text-[#AAA]">{summary}</p>
      )}
      <div className="space-y-2">
        <Row label="Provider">{scan.provider}</Row>
        <Row label="Recreation areas"><IdLinks values={scan.rec_area_ids} base={AREA_URL} /></Row>
        <Row label="Campgrounds"><IdLinks values={scan.campground_ids} base={CAMPGROUND_URL} /></Row>
        <Row label="Campsites"><IdLinks values={scan.campsite_ids} base={CAMPSITE_URL} /></Row>
        <Row label="Search windows">
          <span className="flex flex-wrap gap-1.5">
            {scan.search_windows.map((w, i) => (
              <span key={i} className="rounded-full bg-sand-100 px-2.5 py-0.5 text-xs text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
                {dateRange(w.start_date, w.end_date)}
              </span>
            ))}
          </span>
        </Row>
        <Row label="Nights">{scan.nights}</Row>
        <Row label="Days of week">
          {scan.days_of_week && scan.days_of_week.length ? (
            <span className="flex flex-wrap gap-1">
              {DAYS.map((d, i) => (
                <span key={d} className={cn(
                  "rounded px-1.5 py-0.5 text-xs",
                  scan.days_of_week!.includes(i)
                    ? "bg-forest-600 text-white"
                    : "bg-sand-100 text-stone-400 dark:bg-[#222]",
                )}>
                  {d}
                </span>
              ))}
            </span>
          ) : (
            "Any"
          )}
        </Row>
        <Row label="Weekends only">{scan.weekends_only ? "Yes" : "No"}</Row>
        <Row label="Polling">every {formatInterval(scan.polling_interval)}</Row>
        <Row label="Notifications">{notifs}</Row>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/scans/ConfigCard.test.tsx`
Expected: PASS — all tests in the file, including the three pre-existing ones.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/scans/ConfigCard.tsx src/components/scans/ConfigCard.test.tsx
git commit -m "feat: show a target-count summary on the scan configuration card"
```

---

## Final Verification

After all six tasks:

```bash
.venv/bin/pytest tests/ -v
cd frontend && npx vitest run && npx tsc --noEmit
```

Expected: full backend and frontend suites pass, no type errors.
