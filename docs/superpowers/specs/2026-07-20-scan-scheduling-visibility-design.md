# Scan Scheduling Visibility — Design Spec

**Date:** 2026-07-20
**Status:** Approved
**Branch:** TBD (new branch off `main`)

## Overview

Three related fixes to how scans start and how their schedule is surfaced, driven
by a user expectation gap: creating a scan today does *not* start checking
right away, and nothing in the API or UI shows when the next check will
happen or how long the last one took.

1. **Immediate first run** — a brand-new scan should be checked within
   seconds, not up to ~6 minutes.
2. **Interval-edit propagation** — editing `polling_interval` on a running
   scan should actually change its cadence (today it silently doesn't).
3. **Next-run / last-run visibility** — surface `next_run_at` and
   `last_run_duration_seconds` through the existing stats endpoint, plus
   target counts already known at creation time (no new RIDB calls).

## Current behavior (data facts)

- The scheduler (`core/scheduler.py`) is a separate long-lived process
  (`main.py`), decoupled from the API. It discovers scan changes only via
  `sync_jobs()`, itself an APScheduler job re-run every 60s.
- `sync_jobs()`'s diff is **membership-only**:
  `existing_ids = {live job ids}`, `active_ids = {active scan ids}`. It adds
  jobs for `active_ids - existing_ids` and removes jobs for
  `existing_ids - active_ids`. Scans in the **intersection** (already
  scheduled, still active) are never revisited — so editing
  `polling_interval` on a running scan is silently ignored until the scan is
  paused/resumed or the process restarts.
- `IntervalTrigger(seconds=scan.polling_interval)` (no `start_date`) defaults
  its first fire to `now + interval`. Combined with the 60s discovery delay,
  a brand-new scan can wait up to `60s + polling_interval` (~6 min at the
  300s default) before its very first check.
- `BackgroundScheduler` uses the default **in-memory** job store, so on
  process restart `existing_ids` starts empty and every active scan looks
  "new" to the membership diff.
- Nothing computes or stores "next run" or "last run duration" anywhere —
  not on the `Scan` model, not in `ScanStatsResponse`, not in the frontend.
  `ScanRun.started_at`/`finished_at` exist and are rendered per-row in the
  run-history table, but never aggregated.
- `ScanResponse` already returns `rec_area_ids`/`campground_ids`/
  `campsite_ids` — the exact selections made in the wizard — so target
  *counts* are free; resolving them to actual individual campsite counts is
  not (it needs a live RIDB lookup).

## Scope

### In scope
1. Scheduler fires a never-run scan's first check almost immediately.
2. Scheduler propagates `polling_interval` edits to already-scheduled active
   scans.
3. `next_run_at` and `last_run_duration_seconds`, computed and exposed via
   the existing `GET /scans/{id}/stats` endpoint.
4. Frontend: "next run" + "last run duration" on the Overview tab, and a
   target-count summary on the Configuration card.

### Out of scope (rejected, with rationale)
- **API-triggered "run now" endpoint.** Would create a second, unprotected
  caller of `core/runner.run_scan` alongside the scheduler's
  `max_instances=1`/`coalesce=True`-guarded job, risking concurrent runs of
  the same scan, and would pull camply/RIDB execution into the API process
  (currently isolated to the scheduler process). The scheduler stays the
  sole trigger of runs.
- **Predictive duration estimate before a scan has ever run.** No historical
  telemetry exists to base a prediction on (not even "how many
  campgrounds/campsites were queried" per run), and building that
  aggregation is a bigger feature for a number that's only relevant for the
  ~30s until the immediate first run actually completes.
- **Resolving individual campsite counts via a live RIDB lookup at creation
  time.** Extra latency and failure surface on scan creation for a
  secondary number; campground/rec-area/campsite *target* counts (already
  known, zero extra calls) cover the "how big is this scan" question well
  enough.
- **A persisted `next_run_at` column on `Scan`.** Would require the
  scheduler process to write back to a table it doesn't otherwise touch, and
  creates a second source of truth that can drift from what the trigger
  will actually do (e.g., across the interval-edit-propagation bug this spec
  also fixes). `next_run_at` is deterministic from
  `ScanRun.started_at + Scan.polling_interval`, so it's derived on read
  instead.

## Backend changes

All changes live in `core/scheduler.py`, `core/services/history.py`, and
`api/schemas.py`. **No DB migration is needed** — every new value is derived
from existing columns.

### B1. Immediate first run for never-run scans (`core/scheduler.py`)
In the `active_ids - existing_ids` loop (jobs being added because
`sync_jobs` hasn't seen this scan id before), before calling `add_job`,
check whether the scan has any `ScanRun` rows
(`db.query(ScanRun.id).filter(ScanRun.scan_id == scan.id).first() is None`).
If it has none, pass `start_date=<now, UTC>` to `IntervalTrigger`; otherwise
keep the current default (`now + interval`). Steady-state cadence after the
first fire is unaffected — `IntervalTrigger(seconds=interval,
start_date=now)` fires at `now`, `now+interval`, `now+2*interval`, ... same
as today's trigger, just anchored to `now` instead of `now+interval`.

### B2. Propagate `polling_interval` edits to live jobs (`core/scheduler.py`)
Add a third loop over `existing_ids & active_ids` (scans already scheduled
and still active — the set today's diff never revisits). For each, compare
`scan.polling_interval` to the live job's current interval
(`job.trigger.interval.total_seconds()`). If they differ:
`scheduler.remove_job(job_id)` then re-add it using the **same logic as
B1** (i.e., the never-run check still applies — relevant if an interval is
edited before the scan's first fire has happened). An interval edit on a
scan that has already run does *not* force an immediate fire; it only
changes the cadence going forward from `now`.

### B3. Shrink the discovery poll (`core/scheduler.py`, `start_scheduler`)
`__sync_jobs__`'s own `IntervalTrigger(seconds=60)` → `IntervalTrigger(seconds=30)`.
30s was chosen over a more aggressive value (5–10s) to avoid materially
increasing DB polling load; it still cuts the worst-case discovery wait in
half.

### B4. Restart-safety (design constraint, not new code)
Because `BackgroundScheduler`'s job store is in-memory, a process restart
empties `existing_ids`, so every active scan re-enters the "add" branch on
the next `sync_jobs()` call. B1's immediate-fire rule is keyed off
**`ScanRun` existence in the DB**, not APScheduler's in-memory job set —
this is what prevents a routine scheduler restart/deploy from causing a
synchronized burst-run of every active scan. Scans with run history simply
resume normal `now + interval` scheduling after a restart, same as today.

### B5. Expose `next_run_at` and `last_run_duration_seconds`
`core/services/history.py`'s `stats()` already loads the scan via
`get_scan()`; extend it to also compute:
- `next_run_at`:
  - `None` if `scan.status != ScanStatus.active`.
  - Else, if no `ScanRun` exists for the scan: `now` (matches B1 — a
    never-run active scan's real next fire is "now-ish").
  - Else: `max(now, latest_run.started_at + timedelta(seconds=scan.polling_interval))`,
    where `latest_run` is the most recently **started** run (order by
    `started_at desc`, `limit 1`) — clamped to `now` so a delayed/overrun
    run never displays a time in the past.
- `last_run_duration_seconds`:
  - `None` if no `ScanRun` has ever finished.
  - Else `(finished_at - started_at).total_seconds()` of the most recently
    **started** run whose `finished_at` is not null (order by `started_at
    desc`, filter `finished_at IS NOT NULL`, `limit 1`).
- Both use small targeted queries (order + limit 1), not the existing
  `runs = db.query(ScanRun).filter(...).all()` used for `success_rate` —
  no new full-table scans.

`ScanStatsResponse` (`api/schemas.py`) gains:
```python
next_run_at: Optional[datetime]
last_run_duration_seconds: Optional[float]
```
No new route — `GET /scans/{id}/stats` returns the same shape plus these
two fields.

## Frontend changes

### F1. Types (`frontend/src/types/index.ts`)
`ScanStats` gains `next_run_at: string | null` and
`last_run_duration_seconds: number | null`.

### F2. Format helpers (`frontend/src/lib/format.ts`)
- `relativeFuture(iso: string): string` — future-timestamp counterpart to
  `relativeTime`: `<= 0s → "due now"`; else "in Xs" / "in X min" / "in X hr"
  using the same thresholds `relativeTime` uses for the past.
- Extract the shared `sec < 60 ? "${sec}s" : "${min}m ${sec%60}s"` logic out
  of `duration()` into `formatSeconds(seconds: number): string`, and have
  `duration()` call it — needed because `last_run_duration_seconds` arrives
  as a number, not two ISO timestamps to diff.

### F3. OverviewTab (`frontend/src/components/scans/OverviewTab.tsx`)
- Add a "Next run" entry alongside the existing "Last checked" / "Last new
  site found" line, rendering `stats.next_run_at ? relativeFuture(...) : "—"`
  (dash for paused scans).
- Add "Last run took" using
  `stats.last_run_duration_seconds != null ? formatSeconds(...) : "—"`.
- Give `useScanStats`/`useScanRuns` a short `refetchInterval` (e.g. 5s)
  while `stats.total_runs === 0`, so the Overview updates itself once the
  immediate first run (B1) lands, without a manual page refresh. Stop
  polling once `total_runs > 0`.

### F4. ConfigCard (`frontend/src/components/scans/ConfigCard.tsx`)
Add a one-line summary above the existing rows, built purely from lengths
already on `scan` (no new fetch): e.g. "Monitoring 3 campgrounds across 1
recreation area" / "Monitoring 2 campsites", pluralizing and omitting empty
categories; falls back to nothing extra if all three ID lists are empty
(shouldn't happen given creation validation, but don't render a broken
sentence if it does).

## Testing

Backend (mirror existing test locations/conventions — mock external I/O,
in-memory SQLite):
- `sync_jobs()`: a scan with zero `ScanRun` rows gets a job whose
  `next_run_time` is effectively immediate; a scan with existing runs keeps
  today's `now + interval` behavior.
- `sync_jobs()`: editing `polling_interval` on an active, already-scheduled
  scan causes `remove_job` + re-`add_job` with the new interval on the next
  call; an unchanged interval leaves the job untouched (assert no
  remove/add call).
- Restart simulation: rebuilding the scheduler (empty job store) for a scan
  that already has `ScanRun` history does **not** get `start_date=now`.
- `history.stats()`: `next_run_at` is `None` for a paused scan; ~`now` for a
  never-run active scan; `last_run.started_at + polling_interval` (clamped)
  for one with a past completed run. `last_run_duration_seconds` is `None`
  with no finished runs, correct delta once one exists.
- Route test: `GET /scans/{id}/stats` response includes both new fields.

Frontend (Vitest):
- `relativeFuture` / `formatSeconds` unit tests (boundary cases: 0, <1 min,
  ≥1 min, ≥1 hr).
- OverviewTab: renders "Next run: due now" / "in 5 min" and "Last run took
  Xs" / "—" from stats fixtures; polling stops once `total_runs > 0`
  (assert `refetchInterval` becomes disabled/undefined).
- ConfigCard: renders the summary line for various combinations of
  rec_area_ids/campground_ids/campsite_ids, including the all-empty case.

## Notes
- No DB migration in this spec — everything is derived from existing
  `Scan`/`ScanRun` columns.
- The "next run" and "last run duration" numbers are best-effort derivations
  of the scheduler's actual behavior, not a live read of APScheduler
  internals — acceptable because, after B1/B2, the derivation and the real
  trigger behavior are defined by the same rule (never-run → now,
  otherwise → last fire + interval).
