# Runs & Results Display Enhancements — Design Spec

**Date:** 2026-06-30
**Status:** Approved
**Branch:** spec/web-ui-design

## Overview

Improve how the web UI surfaces a scan's **runs** (the operational poll log) and
**results** (the distinct sites found), based on feedback from testing against
the prod DB. All work here uses the **current** data model. The deeper
availability-lifecycle change (`last_seen_at` / `is_available`) is deferred to
**ADR 007** and is explicitly out of scope.

## Data semantics (the constraint that shapes everything)

`scan_results` is deduplicated by `(scan_id, campsite_id, booking_date)`. Each row
stores `first_seen_at` and `scan_run_id` = the run that **first** discovered it.
Re-finds in later runs write nothing. Therefore:

- A run can be linked (via `scan_run_id`) only to the sites it **newly
  discovered**, not everything available at run time.
- A run's `sites_found` counter and its linked result rows diverge for re-finds.
- We surface per-run sites as **"newly discovered in this run"** and label the
  limitation in-UI (pointing at ADR 007). We do **not** claim to show current
  availability.

Prod reference: scan 5 = 940 runs / 2 results; scan 4 = 4,195 runs / 322 results
(only 105 runs carry any results).

## Scope

### In scope
- Backend: per-run results endpoint, `scan_run_id` on the results response, an
  `outcome` filter on the runs endpoint.
- Run History: page-size selector, "found sites only" filter, expandable run →
  newly-discovered sites (+ limitation tooltip).
- Results: page-size selector, denser card with more fields (campsite_id,
  first-seen, notified badge, discovered-in-run link).
- Scan detail header: scan ID, campground IDs, human-readable polling interval,
  notification summary.
- Overview: "Last checked" and "Last new site found" lines.

### Out of scope (→ ADR 007 follow-up)
- "Available / Gone / last seen" badges and availability windows.
- Per-run forensic history (`scan_observations` table — Option B, rejected).
- Group-by-facility in Results (possible later polish; flat paginated list now).

## Backend changes

All in the existing FastAPI app; follow `api/routes/scans.py`,
`core/services/history.py`, `api/schemas.py` conventions (pydantic v1,
ownership checks, service layer). Add tests mirroring `tests/`.

### B1. `scan_run_id` on `ScanResultResponse`
Add `scan_run_id: int` to `ScanResultResponse` in `api/schemas.py`. It already
exists on the model; just expose it. Consumed by the Results "discovered in run
#X" link.

### B2. Per-run results endpoint
`GET /api/v1/scans/{scan_id}/runs/{run_id}/results` → `List[ScanResultResponse]`.
- Ownership: same check as other scan routes (404 if scan not owned/missing).
- `run_id` must belong to `scan_id` (else 404).
- Returns the `scan_results` rows where `scan_run_id == run_id`, ordered by
  `first_seen_at` desc. No pagination (a single run's discoveries are bounded;
  prod max observed ≈ 194).
- Service fn in `core/services/history.py`, e.g.
  `list_run_results(db, scan_id, run_id, user_id) -> list[ScanResult]`.

### B3. `outcome` filter on the runs endpoint
Extend `GET /api/v1/scans/{scan_id}/runs` with an optional
`outcome: Optional[ScanOutcome] = None` query param. When provided, filter runs
by that outcome (e.g. `?outcome=success`). Keep existing `page`/`page_size`.
Service `history.list_runs` gains an `outcome` kwarg.

## Frontend changes

### Types (`src/types/index.ts`)
- Add `scan_run_id: number` to `ScanResult`.

### API client + hooks
- `src/api/runs.ts`: `list(scanId, page, pageSize, outcome?)` — append
  `&outcome=` when set. Add `runResults(scanId, runId): Promise<ScanResult[]>`
  hitting B2.
- `src/hooks/useRuns.ts`: `useScanRuns(scanId, page, pageSize, outcome?)`;
  add `useRunResults(scanId, runId, enabled)` (query key
  `['scans', scanId, 'runs', runId, 'results']`, `enabled` so it only fetches
  when a row is expanded).
- `src/hooks/useResults.ts`: `useScanResults(scanId, page, pageSize)` — accept a
  caller-supplied page size (default `RESULTS_PAGE_SIZE`).
- Query keys updated to include pageSize/outcome where they affect the result set.

### Shared UI: `PageSizeSelect`
New `src/components/ui/PageSizeSelect.tsx`: `{ value: number; onChange(n:number):void }`,
options 20 / 50 / 100. Reused by Results and Run History. Built on the existing
`Select` primitive.

### Run History tab (`RunHistoryTab` + `RunRow`)
- State: `page`, `pageSize` (default 20), `foundOnly` (bool).
- A toolbar row: `PageSizeSelect` + a "Found sites only" toggle. When `foundOnly`
  is on, pass `outcome="success"` to `useScanRuns`; `page` resets to 1 on change.
- `hasNext = runs.length === pageSize`.
- `RunRow` becomes expandable (a chevron / clickable row). Expanding calls
  `useRunResults(scanId, run.id, enabled=expanded)` and renders the returned
  sites as compact lines (site · facility · type · dates · Book →). States:
  - loading → small spinner
  - has rows → the discovered-sites list + a one-line tooltip/footnote:
    *"Sites first discovered in this run. Re-found sites aren't individually
    recorded (see ADR 007)."*
  - empty but `sites_found > 0` → *"{sites_found} sites found (all previously
    seen)."*
  - empty and `sites_found === 0` → no expand affordance.
- Keep the existing error `<details>`.

### Results tab (`ResultsTab` + `ResultCard`)
- State: `page`, `pageSize` (default 20) with `PageSizeSelect`.
- `ResultCard` gains: `campsite_id` (small mono label), `first_seen` via
  `relativeTime(first_seen_at)`, a **Notified** badge (tone `info` when
  `notified`, else neutral) next to the existing cart badge, and a subtle
  **"run #{scan_run_id}"** affordance. Layout stays one compact card per site.

### Scan detail header (`ScanDetailHeader`)
- Title shows `#{scan.id}` (e.g. small muted `#5` after the name/title).
- Metadata line adds campground IDs when present:
  `RecreationDotGov · areas 1074 · campgrounds 232447 · 2 nights`.
- A compact secondary line/chips: polling interval via a `formatInterval`
  helper (reuse the one added in `ScanForm.tsx` — extract to `lib/format.ts` so
  both share it), and notification summary (e.g. badges: `Email`, `Telegram`,
  `New only` — show only the enabled ones).

### Overview tab (`OverviewTab`)
- Add a small two-item info line under the stats:
  - **Last checked:** `relativeTime(latestRun.started_at)` from
    `useScanRuns(scan.id, 1)[0]` (already fetched for the health bar).
  - **Last new site found:** `relativeTime(latestResult.first_seen_at)` from
    `useScanResults(scan.id, 1)[0]`; "—" when none.

## DRY / shared helpers
- `formatInterval(seconds)` currently lives in `ScanForm.tsx`; move it to
  `src/lib/format.ts` and import in both places (header + form).
- `PageSizeSelect` is the single source for page-size UI.
- The discovered-sites line item reuses the same presentation as `ResultCard`'s
  core (site · facility · type · dates · Book) — factor a small shared
  `ResultLine`/subcomponent if it reduces duplication; otherwise keep `ResultCard`
  and a lighter inline row.

## Testing
- Backend: tests for B2 (per-run results, ownership/404, ordering), B3 (outcome
  filter), B1 (field present). Mock external I/O, in-memory SQLite.
- Frontend (Vitest + MSW):
  - `PageSizeSelect` renders options and fires onChange.
  - Run History: page-size + found-only filter pass the right params; expanding a
    row fetches and renders discovered sites; the "all previously seen" message
    shows when results are empty but `sites_found > 0`.
  - Results: card renders the new fields (campsite_id, first-seen, notified
    badge, run link); page-size selector changes the query.
  - Header: scan ID + campground IDs + notification summary render.
  - Overview: last-checked / last-found lines render from mocked runs/results.

## Notes
- This is additive to the existing web-UI branch; no behavior is removed.
- The deferred availability model (ADR 007) will later add `last_seen_at` /
  `is_available`; the Results card layout should leave room for an availability
  badge so that follow-up is a small insert, not a redesign.
