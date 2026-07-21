# Results tab: group by campground/area — design

Date: 2026-07-20
Status: approved, ready for implementation plan

## Problem

The Scan detail page's Results tab (`frontend/src/components/scans/ResultsTab.tsx`) renders a flat list of `ScanResult` rows. A single scan can target multiple recreation areas and campgrounds at once (`Scan.rec_area_ids`/`campground_ids` are lists), so results from different places end up interleaved. Users want results grouped by campground (and, since a scan can span areas too, by recreation area) with campsite-level detail visible on expand.

## Key finding

Camply's `AvailableCampsite` (what `check_availability()` returns in `core/runner.py`) already includes `facility_id`, `facility_name`, `recreation_area_id`, and `recreation_area` on every result — both ID fields are required/always-present on new results. `core/runner.py` currently persists only `facility_name` onto `ScanResult` and discards the rest. This is not a fuzzy-matching or backfill problem: the grouping key already exists at the moment each result is created, it's just not being saved.

## Decisions

- **Grouping depth**: two levels — Recreation Area → Campground → Campsites.
- **Historical data**: no backfill/migration of existing `ScanResult` rows. New nullable columns default to `NULL` on old rows; those rows are simply "ungroupable" going forward. New results (post-deploy) are always fully groupable since camply always supplies the IDs.
- **Views**: two views, **Flat** (today's existing list, unchanged) and **Grouped** (new), selectable via a toggle in `ResultsTab`.
- **Default view**: Grouped, *unless* none of the fetched results have a `facility_id` (nothing groupable) — in that case default to Flat, since an all-"Other" grouped view would be pointless.
- **Mixed groupable/ungroupable results**: groupable rows render under their Area → Campground structure; ungroupable rows are collected into a single trailing bucket labeled **"Other"**, appended after all area groups. If everything is groupable, no "Other" bucket appears at all.
- **Default expand/collapse**: cascades — an area auto-expands only if it's the sole area in the result set; within an expanded area, a campground auto-expands only if it's the sole campground under that area. Any group with siblings starts collapsed, showing a summary (e.g. "7 available · 2 gone").
- **Sort order**: areas and campgrounds ordered by most recent activity (max `last_seen_at` among their contained rows), most-recent first. Campsite rows within an expanded campground keep the existing sort (also most-recent-first) — no change at the leaf level.
- **Filters**: the `facility_name` dropdown filter is removed from Grouped view (grouping supersedes it) but remains in Flat view. Type/availability/text-search filters apply in both views; in Grouped view, groups left with zero matching rows after filtering are hidden.
- **Leaf rendering**: campsite rows inside an expanded campground group reuse the existing `ResultCard` component unchanged (including the Available/Gone badge work from issue #35) — only the grouping container around it is new.

See the approved mockup for the Grouped view layout (collapsed group with count pills, expanded campground showing campsite rows, trailing "Other" bucket): `.superpowers/brainstorm/4450-1784592106/content/grouped-results-view.html` (in the `forgot-password-ui` worktree where the brainstorming session ran).

## Data model & backend changes

- `db/models.py` — add three nullable columns to `ScanResult`: `facility_id: str | None`, `recreation_area_id: str | None`, `recreation_area: str | None`. (Camply's `facility_id`/`recreation_area_id` are `Union[int, str]`; store as `str` for consistency with how `campsite_id` is already handled.) `facility_name` is unchanged and continues to serve as the campground display name.
- `core/runner.py` (~line 78-86, where `ScanResult` is constructed) — additionally set `facility_id=str(site.facility_id)`, `recreation_area_id=str(site.recreation_area_id)`, `recreation_area=site.recreation_area` from the camply result.
- `api/schemas.py` — add the same three optional fields to `ResultResponse`.
- Alembic migration for the new columns, generated and committed alongside the model change per `docs/agents/schema-changes.md`. No data migration/backfill step.
- No new backend endpoint. `ResultsTab` already fetches the full result set client-side via `useAllScanResults` (for existing filtering); grouping is a pure client-side transform over that already-fetched data. (If server-side pagination is introduced later — see the separate Results-pagination design — grouping would need to move server-side too; out of scope here.)

## Frontend changes

- `ResultsTab.tsx`: add a Flat/Grouped view toggle; compute default view per the rule above once results are fetched.
- New grouping transform (pure function, unit-testable in isolation): partitions fetched `ResultResponse[]` into groupable (has `facility_id`) vs. ungroupable, then nests groupable rows by `recreation_area_id` → `facility_id`, sorted by most-recent activity, and appends the "Other" bucket when ungroupable rows exist.
- New presentational components for the Area and Campground group containers (collapsible, count-pill summary, cascade auto-expand logic), rendering existing `ResultCard` for leaf rows.
- Facility filter dropdown conditionally rendered only in Flat view; other filters shared between views and applied pre-grouping.

## Testing

- Backend: unit test on `run_scan` (mocked `check_availability`) asserting `facility_id`/`recreation_area_id`/`recreation_area` are persisted on the created `ScanResult`. Standard `alembic upgrade head` + `alembic check` verification for the migration.
- Frontend: unit tests for the grouping transform covering all-groupable, all-ungroupable (→ defaults to Flat), and mixed (→ "Other" bucket appended); tests for the cascade auto-expand rule (single area, single campground-within-area); tests confirming filters hide empty groups in Grouped view.

## Rollout

New columns are nullable and populated only for new scan runs going forward — no backfill, no feature flag. Existing scan history renders under "Other" until either the scan reruns (producing fresh, groupable rows) or the data ages out naturally.

## Out of scope (this design)

- Server-side pagination and total-page-count for the Results tab (separate design, to be tackled next).
- Any change to how `Scan.campground_ids`/`rec_area_ids` (scan configuration) are displayed — that's tracked in GitHub issue #35, item 3 (resolved names in Overview).
