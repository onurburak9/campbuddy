# ADR 008: Overview time-series analytics (deferred)

**Date:** 2026-07-01
**Status:** Proposed (deferred — follow-up to the results/runs/overview filters work)

## Context

The scan Overview tab currently shows point-in-time aggregates (`GET
/scans/{id}/stats`: total sites found, in cart, total runs, success rate),
a "last checked / last new site found" line, a recent run-health bar, and —
as of the 2026-07-01 work — a **Configuration** card. Users have asked for
breakdowns "per time": how run volume, success rate, and new-site discovery
trend over days.

The current `/stats` endpoint returns a single snapshot; it cannot answer
"how did this change day by day". Delivering trends requires time-bucketed
aggregation the API does not yet provide.

## Decision

When implemented, add a backend aggregate endpoint returning **daily buckets**
over a bounded window (e.g. last 14–30 days), such as:

`GET /api/v1/scans/{scan_id}/stats/daily?days=30` →
```json
[{ "date": "2026-06-24", "runs": 144, "successes": 130, "no_results": 14,
   "errors": 0, "new_sites": 6 }, ...]
```
- `runs` / `successes` / `no_results` / `errors`: `scan_runs` bucketed by
  `date(started_at)`.
- `new_sites`: `scan_results` bucketed by `date(first_seen_at)` — this is
  **newly discovered** sites per day (dedup semantics, see ADR 007), not
  sites available that day.

Render on the Overview with **lightweight div/SVG bars** (the same
dependency-free approach as the existing run-health bar) — one small chart per
metric (run volume/day, success-rate/day, new-sites/day). Do **not** add a
charting library.

## Alternatives considered

- **Charting library (recharts/visx/etc.):** richer interactions, but a new
  runtime dependency for a few simple bar charts. Rejected — div/SVG bars
  suffice at this fidelity.
- **Availability-over-time ("sites available each day"):** not possible
  without the `last_seen_at`/`is_available` model change in ADR 007. Explicitly
  out of scope until that lands; `new_sites`/day (first-discovery) is the
  honest substitute.
- **Client-side bucketing from the paginated runs/results:** would require
  fetching the full run history (thousands of rows for active scans) into the
  browser — rejected in favour of a server aggregate.

## Consequences

- Overview gains trend charts once built; until then it shows the config card +
  point-in-time stats + run-health bar, which is sufficient.
- `new_sites`/day is first-discovery-based and will undercount re-availability
  until ADR 007 is implemented.
- One new read-only aggregate endpoint; no schema change.
