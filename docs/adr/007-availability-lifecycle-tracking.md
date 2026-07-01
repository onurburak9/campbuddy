# ADR 007: Track campsite availability lifecycle (last-seen + availability)

**Date:** 2026-06-30
**Status:** Proposed (deferred — follow-up to the web-UI work)

## Context

`scan_results` is currently **notification-shaped**. Rows are deduplicated by
`(scan_id, campsite_id, booking_date)` (see `ix_scan_results_dedup`) and each row
records only:

- `first_seen_at` — when the site/date combo was first observed available
- `scan_run_id` — the single run that **first** discovered it
- `cart_added` / `notified` flags + timestamps

This is exactly right for the original job: *"alert me once when a new site
appears."* The runner finds matching sites, inserts a row the first time it sees
each, notifies, and never needs to write that row again.

But the web UI implies a second job the data cannot serve: an **availability
dashboard**. With the current schema we **cannot** answer:

- Is this site **still available** right now?
- **When did it stop** being available?
- Which runs (plural) observed it — we keep only the first.

Concretely, in the prod data: scan 5 ("2N Jul 3-6") has 940 runs but only 2
result rows; scan 4 ("Sequoia") has 4,195 runs and 322 result rows, with only
105 runs carrying any results. A run's `sites_found` counter and the stored
result rows diverge for every re-find, because re-finds write nothing.

The web-UI work (see `docs/superpowers/specs/2026-06-30-runs-results-display-design.md`)
ships display improvements against this current data, with honest tooltips
("shows sites first discovered in this run; re-found sites aren't individually
recorded"). This ADR records the **deferred** data-model change that would let
the UI show true availability.

## Decision

When implemented, evolve `scan_results` in place by adding two columns
(**Option A**):

- `last_seen_at: datetime` — updated on every run that re-observes the site/date
  as available.
- `is_available: bool` — set false when a previously-seen site/date is absent
  from a run's matching results (i.e. it dropped out).

Runner change (in the result-persistence path): for each run, after computing the
current set of matching sites, (1) upsert `last_seen_at` for sites still present,
(2) flip `is_available=false` for rows of this scan that were available but are no
longer in the current set. This is a small change localized to the persistence
step; the dedup key is unchanged.

This unlocks, in the UI:
- a live **"Available / Gone"** badge per site
- **"last seen 4h ago"** and an approximate availability window
  (`first_seen_at` → `last_seen_at`)

A migration adds the columns (`is_available` default true, `last_seen_at`
defaulting to `first_seen_at` for existing rows) per `docs/agents/schema-changes.md`.

API: add `last_seen_at` and `is_available` to `ScanResultResponse`.

## Alternatives considered

- **Option B — a `scan_observations` table** (`run_id, campsite_id, booking_date`),
  one row per (run, site) observed. Gives full forensic history — exactly which
  runs saw which sites and precise availability windows. **Rejected for now:**
  it is heavy (scan 4 alone would generate ~112k observation rows) and per-run
  granularity is rarely needed. Option A covers ~90% of the value at a fraction
  of the cost. Revisit only if per-run forensics become a real requirement.

- **Do nothing (status quo).** Keeps the UI unable to show availability; the
  display-only work papers over it with tooltips. Acceptable short-term, which is
  why this is deferred rather than blocking.

## Consequences

- New scans get accurate availability lifecycle; existing rows backfill
  `last_seen_at := first_seen_at`, `is_available := true` (a known approximation
  for historical rows).
- Slightly more write work per run (one UPDATE pass over the scan's current
  results), negligible at SQLite scale.
- The "newly discovered in this run" semantics (via `scan_run_id`) remain; Option A
  is additive and does not change dedup or notification behaviour.
- Until this is built, the web UI's run-detail and results views are limited to
  first-discovery data and must label that limitation explicitly.
