# Campground/campsite search (RIDB-backed)

**Date:** 2026-07-09
**Status:** Approved (design)
**Branch:** `feat/campground-campsite-search`

## Problem

Creating or editing a scan today requires already knowing the numeric
Recreation.gov `rec_area_id`/`campground_id`/`campsite_id` values — the wizard
(`frontend/src/components/scans/ScanForm.tsx`) is a plain comma-separated text input
("Recreation Area IDs (comma-separated)", placeholder `"2991, 2992"`). Deferred from
Phase 1 of the web UI ([#17](https://github.com/onurburak9/campbuddy/issues/17)), tracked
as one item in [#22](https://github.com/onurburak9/campbuddy/issues/22).

Recreation.gov's RIDB API (https://ridb.recreation.gov/docs) exposes rec areas,
facilities (campgrounds), and campsites as searchable reference data. camply
0.34.1 — already a dependency, per
[ADR 001](../adr/001-camply-as-engine.md) the sole external-API boundary in this
codebase — wraps RIDB directly via `camply.RecreationDotGov`, independent of the
availability-polling class (`SearchRecreationDotGov`) used in `core/availability.py`.

## Goals

1. Search-select UI for picking recreation areas, campgrounds, and campsites by name
   instead of raw IDs, in the scan creation/edit wizard.
2. Thin authenticated backend endpoints proxying camply's RIDB wrapper, so the frontend
   never talks to RIDB directly.
3. When editing an existing scan (IDs stored with no names — from CLI seeding or the
   current text-input flow), resolve those IDs back to display names.
4. Keep a manual "add by ID" fallback for cases search doesn't surface (e.g. a very
   recently added campground).

## Non-goals (deliberately out of scope)

- **Local mirror of RIDB data.** No new tables/migration/refresh job. Search hits RIDB
  live (via camply) with an in-process cache — appropriate for this app's scale (few
  users, infrequent scan setup), not enough traffic to justify a persistent cache layer.
- **Full-text/fuzzy search.** We pass the user's query straight to RIDB's own `query`
  param; no local ranking or fuzzy matching.
- **Map visualization.** Split into a separate followup issue
  ([#28](https://github.com/onurburak9/campbuddy/issues/28)).
- **Changing the `Scan` model or `ScanCreate`/`ScanUpdate` schemas.** They already store
  `rec_area_ids`/`campground_ids`/`campsite_ids: List[int]` with no name fields — this
  feature is purely a better way to populate those same lists. No migration.

---

## Design

### 1. Settings

`config/settings.py` — add:

```python
ridb_api_key: str = ""
```

Read from `.env` (`RIDB_API_KEY`). If unset, `camply.RecreationDotGov(api_key=None)`
falls back to camply's bundled service-account token — functional but shared across all
camply users, so a dedicated key is recommended for real usage. (Not committed anywhere
in this repo or spec — set directly in the operator's local `.env`.)

### 2. Service layer — `core/services/search.py` (new)

```python
@lru_cache(maxsize=1)
def _get_provider() -> RecreationDotGov:
    settings = get_settings()
    return RecreationDotGov(api_key=settings.ridb_api_key or None)
```

A process-lifetime singleton reusing camply's underlying `requests.Session`. Search
functions below are wrapped with `functools.lru_cache` — RIDB reference data (names,
locations) changes rarely, and a self-hosted deploy restarts the process on every code
update anyway, which naturally clears the cache. No TTL/invalidation logic needed.

**`search_recreation_areas(query: str) -> list[dict]`**
`_get_provider().find_recreation_areas(search_string=query)` returns raw RIDB dicts.
Normalize each via camply's own `RecreationAreaResponse` container
(`camply.containers.api_responses.RecreationAreaResponse`) to
`{"id": ..., "name": ..., "state": ...}` (state from `RECAREAADDRESS[0].AddressStateCode`
when present, else `None`). Cached on `query`.

**`search_campgrounds(query: Optional[str], rec_area_ids: Optional[list[int]]) -> list[dict]`**
camply's `find_campgrounds` treats `search_string` and `rec_area_id` as **mutually
exclusive** branches (confirmed in `recdotgov_provider.py`) — passing both ignores
`search_string`. So:
- If `rec_area_ids` given: `find_campgrounds(rec_area_id=rec_area_ids)` — returns *all*
  campgrounds under those rec areas (no further server-side text filter).
- Else: `find_campgrounds(search_string=query)`.

Both return `List[CampgroundFacility]` already (camply's own container — no extra
normalization needed): `{"id": facility_id, "name": facility_name, "recreation_area":
recreation_area, "recreation_area_id": recreation_area_id}`. Cached on
`(query, tuple(sorted(rec_area_ids or [])))`.

**`list_campsites(campground_ids: list[int]) -> list[dict]`**
For each id: `_get_provider().paginate_recdotgov_campsites(facility_id=id)` →
`List[RecDotGovCampsite]`. Flatten and normalize to `{"id": campsite_id, "name": name,
"loop": loop, "campground_id": facility_id}`. Cached on `tuple(sorted(campground_ids))`.

**Resolve-by-id (for hydrating an existing scan's chip labels):**
- `resolve_campgrounds(ids: list[int]) -> list[dict]` — `find_campgrounds(campground_id=ids)`,
  same normalization as `search_campgrounds`.
- `resolve_campsites(ids: list[int]) -> list[dict]` — `get_campsite_by_id(id)` per id
  (camply raises `ProviderSearchError` for an unknown id — caught per-id, skipped, so one
  stale id doesn't break resolving the rest).
- `resolve_recreation_areas(ids: list[int]) -> list[dict]` — camply has no by-id rec-area
  helper, so call `_get_provider().get_ridb_data(path=f"{RIDBConfig.REC_AREA_API_PATH}/{id}")`
  directly per id (a documented RIDB endpoint: `GET /recareas/{id}`), same normalization
  as `search_recreation_areas`. 404s from RIDB are caught per-id and skipped.

**Error handling.** All camply/RIDB exceptions (network errors, RIDB 5xx, camply's own
`RuntimeError`/`ProviderSearchError` for malformed calls) are caught in the service layer
and re-raised as a new `UpstreamError(ServiceError)` (`core/services/exceptions.py`),
mapped to HTTP 502 in `api/main.py` (same pattern as the existing `NotFound`/`Forbidden`
handlers) — so a RIDB outage surfaces as a clean "search temporarily unavailable"
response, not a raw 500. Per-id resolve failures are the exception: those are caught
per-item (see above) so one bad id doesn't 502 the whole batch.

### 3. Routes — `api/routes/search.py` (new), mounted at `/api/v1/search`

All routes require `Depends(get_current_user)` — not public, so an internet-reachable
deployment can't be used as an anonymous RIDB scraping proxy.

| Route | Params | Notes |
|---|---|---|
| `GET /recreation-areas` | `q: str` (`min_length=2`, required) | |
| `GET /recreation-areas/resolve` | `ids: List[int]` (required, query-repeated `?ids=1&ids=2`) | |
| `GET /campgrounds` | `q: Optional[str]`, `rec_area_ids: Optional[List[int]]` | At least one of `q`/`rec_area_ids` required (422 if neither) |
| `GET /campgrounds/resolve` | `ids: List[int]` (required) | |
| `GET /campsites` | `campground_ids: List[int]` (required) | |
| `GET /campsites/resolve` | `ids: List[int]` (required) | |

Routes stay thin: parse/validate query params, call the matching `core/services/search.py`
function, return the list directly (Pydantic response models in `api/schemas.py`:
`RecreationAreaResult`, `CampgroundResult`, `CampsiteResult`).

### 4. Frontend

**New reusable component** `frontend/src/components/ui/SearchSelect.tsx` (no combobox
pattern exists yet in `components/ui/`): async multi-select — 300ms debounce, fires only
at ≥2 characters, shows loading/error states, renders selected items as removable chips,
and includes an "Add by ID" affordance (small input + button) as a manual fallback that
appends a bare `{id, name: "ID {id}"}` chip without hitting search.

**`ScanForm.tsx` / `useScanFormState.ts`** — replace the three raw comma-separated text
inputs with three `SearchSelect` instances:
1. **Recreation Areas** — always async, hits `GET /search/recreation-areas?q=`.
2. **Campgrounds** — async hitting `GET /search/campgrounds?q=` while no recreation areas
   are selected; once one or more are selected, fetches once via
   `GET /search/campgrounds?rec_area_ids=` and filters the returned list client-side as
   the user types (per the mutual-exclusivity constraint above).
3. **Campsites** — disabled/hidden until at least one campground is selected; fetches
   once via `GET /search/campsites?campground_ids=` and filters client-side.

Each `SearchSelect` instance tracks `{id, name}` pairs locally for chip display, but the
wizard still submits plain `rec_area_ids`/`campground_ids`/`campsite_ids: number[]` to
`ScanCreate`/`ScanUpdate` — no change to the API payload shape.

**Editing an existing scan:** on wizard open, if the scan already has non-empty
`rec_area_ids`/`campground_ids`/`campsite_ids`, call the corresponding `/resolve`
endpoints once to hydrate `{id, name}` pairs for the initial chips, instead of showing
bare numbers.

## Data flow (creating a scan, happy path)

```
Type "Yosemite" in Recreation Areas field
  → debounce 300ms → GET /search/recreation-areas?q=Yosemite
  → core/services/search.search_recreation_areas("Yosemite") [cached]
  → camply RecreationDotGov.find_recreation_areas(search_string="Yosemite")
  → normalize → [{id, name, state}, ...] → dropdown
Select "Yosemite National Park" → chip added, rec_area_ids=[id]

Type in Campgrounds field (rec_area_ids non-empty)
  → GET /search/campgrounds?rec_area_ids=id (once)
  → camply find_campgrounds(rec_area_id=[id]) → all campgrounds in that rec area
  → client-side filter as user types → dropdown
Select a campground → chip added, campground_ids=[id]

Campsites field enabled → GET /search/campsites?campground_ids=id (once)
  → camply paginate_recdotgov_campsites(facility_id=id) → all sites in that campground
  → client-side filter → optional chip selection → campsite_ids=[...]

Submit → POST /api/v1/scans {rec_area_ids, campground_ids, campsite_ids, ...} (unchanged schema)
```

## Error handling

| Failure | Behavior |
|---|---|
| RIDB/camply network error or 5xx | Service raises `UpstreamError` → 502; dropdown shows "Search temporarily unavailable, try again." |
| `q` missing/too short on rec-area or free-text campground search | 422; frontend just doesn't fire the request below 2 chars, so this is a defense-in-depth guard. |
| Neither `q` nor `rec_area_ids` on campgrounds search | 422. |
| Unresolvable id in a `/resolve` call (deleted/renamed upstream) | That id is skipped (not included in the response); frontend falls back to showing `ID {id}` as the chip label for anything not returned. |
| Not authenticated | 401 (existing `get_current_user` behavior). |
| RIDB search returns zero results | Empty list, 200; dropdown shows "No matches — try a different search or add by ID." |

## Testing

Mock all external I/O (the camply provider, never real HTTP to RIDB); in-memory SQLite
where DB access is involved (`docs/agents/testing.md`).

- **`tests/services/test_search.py` (new):** each search/resolve function against a
  mocked `RecreationDotGov` instance — correct camply method/kwargs called per branch
  (rec_area_ids present vs. absent for campgrounds), normalization shape, `lru_cache`
  hit on repeated identical calls (mock call count doesn't increase), camply exception →
  `UpstreamError`, per-id resolve failure skips that id without raising.
- **`tests/api/test_search.py` (new):** 401 without auth cookie; 422 on missing/short `q`
  and on campgrounds search with neither `q` nor `rec_area_ids`; 502 passthrough when the
  service raises `UpstreamError`; happy-path shape matches the response schema.
- **Frontend:** `SearchSelect` unit tests (debounce timing, min-char gate, chip add/
  remove, "Add by ID" fallback, loading/error states) and updated `ScanForm`/
  `useScanFormState` tests covering the three-field flow and edit-mode id resolution.

## Follow-up (separate ticket)

Map visualization of campgrounds/rec areas — tracked in
[onurburak9/campbuddy#28](https://github.com/onurburak9/campbuddy/issues/28).
