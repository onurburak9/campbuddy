# Results Search, Run-History Time Filter & Overview Config Card — Design Spec

**Date:** 2026-07-01
**Status:** Approved
**Branch:** spec/web-ui-design

## Overview

Three enhancements to the scan detail tabs, driven by prod-data testing:
1. **Results** — client-side search + Facility/Type filters.
2. **Run History** — server-side time-range filter (`started_after`).
3. **Overview** — a prominent Configuration card (the tab is mostly empty today).

Time-series analytics for the Overview are **out of scope** and documented as
deferred work in **ADR 008**.

## Data facts that shape the design

- `scan_results` carry `facility_name` (the campground) and `campsite_type`,
  but **no area** (rec-area is a scan-level setting, not recorded per result).
  So per-result filters are **Facility** and **Type** only.
- Distinct results per scan are bounded (max observed ≈ 322; Rec.gov scans are
  finite). Fetching them all client-side is cheap.
- The results endpoint caps `page_size` at 100, so "fetch all" pages through
  until a short page (≤4 requests at observed sizes).
- Runs are numerous (up to ~4,195) and stay server-paginated; time filtering is
  server-side.

## Scope

### In scope
- Results: fetch-all hook, name search, Facility + Type dropdowns, client-side
  pagination over the filtered set.
- Run History: `started_after` backend param + a range dropdown (6h/24h/7d/30d/All).
- Overview: Configuration card (folds in the existing search-windows list).

### Out of scope (→ ADR 008 / ADR 007)
- Overview time-series charts (ADR 008).
- Availability-over-time / "sites available per day" (ADR 007).
- Server-side result search/filter and an "area" result filter.

## Backend changes

Single change, following existing conventions (pydantic v1, `get_scan`
ownership, service layer in `core/services/history.py`, routes in
`api/routes/scans.py`; tests mock I/O + in-memory SQLite).

### B1. `started_after` filter on the runs endpoint
Extend `GET /api/v1/scans/{scan_id}/runs` with an optional
`started_after: Optional[datetime] = None` query param. When provided, filter
`ScanRun.started_at >= started_after`. Compose with the existing `outcome`
filter and `page`/`page_size`. `history.list_runs` gains a `started_after`
kwarg applied as an additional `.filter(...)`.

## Frontend changes

### Results tab (client-side filtering)

**Hook — `useAllScanResults(scanId)`** (`src/hooks/useResults.ts`):
- `useQuery` whose `queryFn` loops: fetch page 1 (size 100), 2, 3 … via the
  existing `results.list(scanId, page, 100)` until a returned page has
  `< 100` rows; concatenate and return the full `ScanResult[]`.
- Query key `queryKeys.allResults(scanId)` = `["scans", id, "results", "all"]`.
- `enabled: scanId != null`.

**`ResultsTab.tsx`** is reworked to consume `useAllScanResults`:
- Local state: `search` (string), `facility` (string | "all"), `type`
  (string | "all"), `page`, `pageSize`.
- Derive `facilities` = sorted distinct `facility_name`; `types` = sorted
  distinct `campsite_type` from the loaded results.
- `filtered` = results where (facility === "all" || r.facility_name === facility)
  && (type === "all" || r.campsite_type === type) && (search empty ||
  `${site_name} ${facility_name}`.toLowerCase().includes(search.toLowerCase())).
- Reset `page` to 1 whenever search/facility/type/pageSize changes.
- Paginate client-side: `filtered.slice((page-1)*pageSize, page*pageSize)`;
  `hasNext = page * pageSize < filtered.length`.
- Toolbar row: search `Input`, Facility `Select`, Type `Select`, `PageSizeSelect`.
- States: loading → Spinner; no results at all → "No results yet"; results but
  filter matches none → "No results match your filters".
- `ResultCard` is unchanged.

**Filter UI:** Facility/Type `Select` options are `[{value:"all",label:"All
campgrounds"|"All types"}, ...distinct]`. Search is a debounce-free controlled
`Input` (filtering is in-memory, instant).

### Run History tab (time-range filter)

- `runs.list(scanId, page, pageSize, outcome?, startedAfter?)` — append
  `&started_after=<ISO>` when set (`src/api/runs.ts`).
- `useScanRuns(scanId, page, pageSize?, outcome?, startedAfter?)` +
  `queryKeys.runs(id, page, pageSize, outcome?, startedAfter?)` include the new
  arg (OverviewTab's `useScanRuns(scan.id, 1)` still works via defaults).
- `RunHistoryTab`: add a **range** `Select` with options
  `all` / `6h` / `24h` / `7d` / `30d` (labels "All time", "Last 6 hours", "Last
  24 hours", "Last 7 days", "Last 30 days"; default `all`). A helper maps a
  range to an ISO cutoff: `all → undefined`, else `new Date(Date.now() -
  RANGE_MS[range]).toISOString()`. Pass as `startedAfter`. Sits in the toolbar
  with "Found sites only" + `PageSizeSelect`; changing it resets `page` to 1.

### Overview tab (Configuration card)

- New `src/components/scans/ConfigCard.tsx`, props `{ scan: Scan }`. Renders a
  bordered card titled "Configuration" with labelled rows:
  - Provider; Recreation Area IDs / Campground IDs / Campsite IDs (join with
    ", ", show "—" when null/empty);
  - **Search windows** (date-range chips, via `dateRange`) — this replaces the
    standalone `SearchWindowsList` on the Overview;
  - Nights; Days of week (chips Mon–Sun, highlighting selected; "Any" when
    null/empty); Weekends only (Yes/No);
  - Polling interval (`formatInterval`); Notifications (Email / Telegram / New
    only — show enabled ones, or "None").
- `OverviewTab.tsx`: keep `StatsRow`, the last-checked/last-found line, and
  `RunHealthBar`; **replace** the standalone `<SearchWindowsList>` usage with
  `<ConfigCard scan={scan} />`. **Remove `SearchWindowsList.tsx`** (its only
  consumer was the Overview) and render the search-window chips inside
  ConfigCard using `dateRange`.

## DRY / reuse
- `formatInterval`, `dateRange` from `lib/format.ts`; `Select`, `Input`,
  `PageSizeSelect`, `Pagination`, `Badge`, `Spinner` primitives.
- The days-of-week chip rendering in ConfigCard mirrors the wizard's
  `DatesFiltersFields` DAYS list (read-only here) — keep a local `DAYS`
  constant; do not couple to the form component.

## Testing
- Backend: `list_runs` `started_after` filter (service test) + a route test
  (`?started_after=...` returns only runs at/after the cutoff). Reuse existing
  fixtures.
- Frontend (Vitest + MSW):
  - `useAllScanResults`: MSW returns a full page (100) then a short page →
    hook concatenates both; a single short page → one request.
  - ResultsTab: search narrows the list; Facility/Type dropdowns filter;
    "No results match your filters" shows when nothing matches; existing
    render assertions still pass.
  - RunHistoryTab: selecting a range passes `started_after` (assert the request
    query param) and resets page.
  - ConfigCard: renders provider, campground IDs, search windows, polling
    interval, notifications, days-of-week from a scan fixture.
  - OverviewTab: ConfigCard present; standalone SearchWindowsList no longer
    rendered.

## Notes
- Additive to the web-UI branch; no existing behavior removed except the
  standalone SearchWindowsList on Overview (folded into ConfigCard).
- Overview analytics remain deferred (ADR 008).
