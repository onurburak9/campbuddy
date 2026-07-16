# RIDB Assets Substring Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scan wizard's recreation-area and campground search match on substrings (e.g. "stan" → "Stanislaus") instead of requiring a full word, by using RIDB's undocumented `public/assets` endpoint for the candidate lookup while keeping today's documented-endpoint enrichment and fallback behavior intact.

**Architecture:** Add a small, isolated `core/services/ridb_assets.py` module that calls RIDB's undocumented `public/assets` endpoint for fast substring search. `core/services/search.py`'s two public search functions try that path first to get real `RecAreaID`/`FacilityID` values (confirmed identical to the documented API's IDs), then feed those IDs into the already-existing, already-tested `resolve_recreation_areas`/`resolve_campgrounds` functions for full enrichment — no new normalization or schema code needed. If the assets call fails for any reason, both functions fall back to today's exact camply-based query behavior, logging a warning for observability.

**Tech Stack:** httpx (already a dependency, 0.27.0) for the new outbound call, matching the existing `core/booking.py` pattern. respx (already a dependency, 0.21.1) for mocking it in tests, matching `tests/test_booking.py`.

## Global Constraints

- New HTTP-calling code follows `core/booking.py`'s exact pattern: module-level `logger = logging.getLogger(__name__)`, direct `httpx.get(...)` calls with a `timeout=` kwarg, `except httpx.HTTPError as e:`.
- Tests for any new httpx-calling code use the `respx_mock` fixture (respx pytest plugin) — never `mocker.patch("httpx.get")` directly. See `tests/test_booking.py` for the reference pattern.
- Public function signatures in `core/services/search.py` do not change: `search_recreation_areas(query)`, `search_campgrounds(query, rec_area_ids)`, `resolve_recreation_areas(ids)`, `resolve_campgrounds(ids)`. `api/routes/search.py`, `frontend/src/api/search.ts`, and `api/schemas.py` are untouched — response shape stays identical.
- No new pip dependencies.
- Any failure of the new endpoint must be invisible to callers beyond a log line — same return shape as before, via fallback to the pre-existing camply-based code path. Never let `AssetsSearchError` escape `core/services/search.py`.
- RIDB's `asset_types[]=campground` value is silently ignored server-side (verified) — the campground path must request `asset_types[]=facility` and filter client-side on `type == "Campground"`.
- Request `limit=15` from the assets endpoint (verified working up to `limit=50` with no error) to satisfy "return at least 10 results."

---

## File Structure

- **Create** `core/services/ridb_assets.py` — thin, isolated httpx client for the undocumented endpoint. Isolated so it's trivial to delete/replace if RIDB breaks or removes it without notice.
- **Create** `tests/services/test_ridb_assets.py` — respx-based tests for the new module.
- **Modify** `core/services/search.py` — `search_recreation_areas` and `_search_campgrounds_cached` gain an assets-first path with fallback to the existing camply-based logic (extracted into `_search_recreation_areas_fallback` / `_search_campgrounds_fallback` / `_search_campgrounds_by_rec_area`).
- **Modify** `tests/services/test_search.py` — rewrite the recreation-area and campground search tests around the new primary/fallback split; `resolve_*`/`list_campsites`/`resolve_campsites` tests are untouched since those functions don't change.

---

### Task 1: `core/services/ridb_assets.py` — RIDB assets client

**Files:**
- Create: `core/services/ridb_assets.py`
- Test: `tests/services/test_ridb_assets.py`

**Interfaces:**
- Produces: `search_assets(terms: str, asset_type: str, limit: int = 15, timeout: float = 5.0) -> list[dict]` — raises `AssetsSearchError` on any failure (non-2xx, transport error, invalid JSON, missing `data` key). Each dict has at least `id: str`, `name: str`, `type: str`.
- Produces: `AssetsSearchError(Exception)`.
- Produces: `assets_endpoint_healthy(timeout: float = 5.0) -> bool` — manual/ops health check, mirrors `core.booking.sidecar_healthy`.

- [ ] **Step 1: Write the failing tests**

Create `tests/services/test_ridb_assets.py`:

```python
import httpx
import pytest

from core.services.ridb_assets import AssetsSearchError, assets_endpoint_healthy, search_assets

ASSETS_URL = "https://ridb.recreation.gov/api/v1/public/assets"


def test_search_assets_returns_data_list(respx_mock):
    respx_mock.get(ASSETS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}], "total_results": 1},
        )
    )
    results = search_assets("yosemite", "recarea")
    assert results == [{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}]


def test_search_assets_raises_on_http_500(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_connection_error(respx_mock):
    respx_mock.get(ASSETS_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_non_json_body(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, content=b"<html>Bad Gateway</html>"))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_missing_data_key(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, json={"oops": []}))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_assets_endpoint_healthy_true(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, json={"data": [], "total_results": 0}))
    assert assets_endpoint_healthy() is True


def test_assets_endpoint_healthy_false_on_error(respx_mock):
    respx_mock.get(ASSETS_URL).mock(side_effect=httpx.ConnectError("refused"))
    assert assets_endpoint_healthy() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_ridb_assets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.services.ridb_assets'`

- [ ] **Step 3: Write the implementation**

Create `core/services/ridb_assets.py`:

```python
import logging

import httpx

logger = logging.getLogger(__name__)

ASSETS_URL = "https://ridb.recreation.gov/api/v1/public/assets"


class AssetsSearchError(Exception):
    pass


def search_assets(terms: str, asset_type: str, limit: int = 15, timeout: float = 5.0) -> list:
    try:
        resp = httpx.get(
            ASSETS_URL,
            params={"terms": terms, "asset_types[]": asset_type, "limit": limit, "page": 0, "sort": "name"},
            timeout=timeout,
        )
        if not resp.is_success:
            raise AssetsSearchError(f"HTTP {resp.status_code}")
        data = resp.json()
    except httpx.HTTPError as e:
        raise AssetsSearchError(str(e)) from e
    except ValueError as e:
        raise AssetsSearchError(f"invalid JSON response: {e}") from e
    if "data" not in data:
        raise AssetsSearchError("response missing 'data' key")
    return data["data"]


def assets_endpoint_healthy(timeout: float = 5.0) -> bool:
    try:
        search_assets("yosemite", "recarea", limit=1, timeout=timeout)
        return True
    except AssetsSearchError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_ridb_assets.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add core/services/ridb_assets.py tests/services/test_ridb_assets.py
git commit -m "feat: add RIDB assets endpoint client for substring search"
```

---

### Task 2: Wire recreation-area search through assets + fallback

**Files:**
- Modify: `core/services/search.py:1-41` (imports, `_normalize_recreation_area`, `search_recreation_areas`)
- Modify: `tests/services/test_search.py:1-73` (recreation-area search tests)

**Interfaces:**
- Consumes: `search_assets(terms, asset_type, limit=15, timeout=5.0)`, `AssetsSearchError` from Task 1.
- Consumes: `resolve_recreation_areas(ids: list) -> list` (existing, unchanged, at `core/services/search.py:44`).
- Produces: `_extract_asset_ids(assets: list, expected_type: Optional[str] = None) -> list[int]` — used again in Task 3.
- Produces: `_search_recreation_areas_fallback(query: str) -> list` — the old `search_recreation_areas` body, callable directly by tests and by Task 3's sibling code for symmetry.

- [ ] **Step 1: Write the failing tests**

In `tests/services/test_search.py`, replace lines 1-73 (everything from the top through `test_resolve_recreation_areas_skips_failed_ids`, i.e. up to but not including `def make_facility`) with:

```python
import pytest
from unittest.mock import MagicMock
from core.services import search
from core.services.exceptions import UpstreamError
from core.services.ridb_assets import AssetsSearchError


@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    search._search_campgrounds_cached.cache_clear()
    search._list_campsites_cached.cache_clear()
    yield


@pytest.fixture
def mock_provider(mocker):
    provider = MagicMock()
    mocker.patch("core.services.search._get_provider", return_value=provider)
    return provider


def test_search_recreation_areas_uses_assets_search(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"},
    ])
    resolve_mock = mocker.patch(
        "core.services.search.resolve_recreation_areas",
        return_value=[{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}],
    )
    results = search.search_recreation_areas("Yosemite")
    resolve_mock.assert_called_once_with([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}]


def test_search_recreation_areas_skips_non_numeric_asset_ids(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "AP26168", "name": "Some Activity Pass", "type": "Activity Pass"},
        {"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"},
    ])
    resolve_mock = mocker.patch("core.services.search.resolve_recreation_areas", return_value=[])
    search.search_recreation_areas("Yosemite")
    resolve_mock.assert_called_once_with([2991])


def test_search_recreation_areas_caches_by_query(mocker, mock_provider):
    assets_mock = mocker.patch(
        "core.services.search.search_assets",
        return_value=[{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}],
    )
    mocker.patch("core.services.search.resolve_recreation_areas", return_value=[])
    search.search_recreation_areas("Yosemite")
    search.search_recreation_areas("Yosemite")
    assert assets_mock.call_count == 1


def test_search_recreation_areas_falls_back_when_assets_unavailable(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": None}]
    mock_provider.find_recreation_areas.assert_called_once_with(search_string="Yosemite")


def test_search_recreation_areas_fallback_skips_malformed_items(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        {"missing": "required fields"},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert len(results) == 1


def test_search_recreation_areas_fallback_wraps_upstream_failure(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_recreation_areas("Yosemite-fail")


def test_resolve_recreation_areas_normalizes_results(mock_provider):
    mock_provider.get_ridb_data.return_value = {
        "RecAreaID": 2991, "RecAreaName": "Yosemite National Park",
        "RECAREAADDRESS": [{"AddressStateCode": "CA"}],
        "ORGANIZATION": [{"OrgName": "National Park Service"}],
    }
    results = search.resolve_recreation_areas([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}]
    mock_provider.get_ridb_data.assert_called_once_with(path="recareas/2991", params={"full": True})


def test_resolve_recreation_areas_skips_failed_ids(mock_provider):
    mock_provider.get_ridb_data.side_effect = [
        {"RecAreaID": 1, "RecAreaName": "Area One", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        ConnectionError("not found"),
    ]
    results = search.resolve_recreation_areas([1, 999])
    assert results == [{"id": 1, "name": "Area One", "state": "CA", "type": None}]
```

Note: `test_search_recreation_areas_handles_missing_address` and `test_search_recreation_areas_handles_missing_organization` (old lines 44-57) are removed — that behavior belongs to `_normalize_recreation_area`, already exercised through `resolve_recreation_areas`, which isn't changing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: FAIL — `AttributeError` / `ImportError` (`search.search_assets` doesn't exist yet on the `search` module, and behavior doesn't match).

- [ ] **Step 3: Write the implementation**

In `core/services/search.py`, replace lines 1-41 with:

```python
import logging
from functools import lru_cache
from typing import Optional

from camply import RecreationDotGov
from camply.config import RIDBConfig
from camply.containers.api_responses import RecreationAreaResponse

from config.settings import get_settings
from core.services.exceptions import UpstreamError
from core.services.ridb_assets import AssetsSearchError, search_assets

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_provider() -> RecreationDotGov:
    settings = get_settings()
    return RecreationDotGov(api_key=settings.ridb_api_key or None)


def _normalize_recreation_area(response: RecreationAreaResponse, raw: dict) -> dict:
    state = response.RECAREAADDRESS[0].AddressStateCode if response.RECAREAADDRESS else None
    # Managing agency (e.g. "National Park Service", "US Army Corps of Engineers") is the
    # closest RIDB gets to a "type" for a rec area — it isn't modeled by camply's
    # RecreationAreaResponse, so it's read straight off the raw RIDB payload.
    orgs = raw.get("ORGANIZATION") or []
    org_type = orgs[0].get("OrgName") if orgs else None
    return {"id": response.RecAreaID, "name": response.RecAreaName, "state": state, "type": org_type}


def _extract_asset_ids(assets: list, expected_type: Optional[str] = None) -> list:
    ids = []
    for item in assets:
        if expected_type and item.get("type") != expected_type:
            continue
        try:
            ids.append(int(item["id"]))
        except (KeyError, ValueError, TypeError):
            continue
    return ids


@lru_cache(maxsize=128)
def search_recreation_areas(query: str) -> list:
    try:
        assets = search_assets(query, "recarea")
    except AssetsSearchError as e:
        logger.warning("RIDB assets search unavailable (%s), falling back to recareas query search", e)
        return _search_recreation_areas_fallback(query)
    return resolve_recreation_areas(_extract_asset_ids(assets))


def _search_recreation_areas_fallback(query: str) -> list:
    provider = _get_provider()
    try:
        raw = provider.find_recreation_areas(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    results = []
    for item in raw:
        try:
            results.append(_normalize_recreation_area(RecreationAreaResponse(**item), item))
        except Exception:
            continue
    return results
```

Leave `resolve_recreation_areas` (old lines 44-56) and everything below it untouched for this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: all recreation-area and `resolve_recreation_areas` tests pass. (Campground/campsite tests below `make_facility` still reference the pre-Task-3 behavior and will be addressed in Task 3 — run `.venv/bin/pytest tests/services/test_search.py -v -k "recreation_area"` to confirm just this task's slice is green.)

- [ ] **Step 5: Commit**

```bash
git add core/services/search.py tests/services/test_search.py
git commit -m "feat: search recreation areas via RIDB assets substring search with fallback"
```

---

### Task 3: Wire campground search through assets + fallback

**Files:**
- Modify: `core/services/search.py` (post-Task-2 line numbers: `search_campgrounds`/`_search_campgrounds_cached`, roughly old lines 68-83)
- Modify: `tests/services/test_search.py` (campground search tests, roughly old lines 104-131 — `make_facility` at old line 95 and everything from `test_resolve_campgrounds_normalizes_results` onward, old lines 133+, are untouched)

**Interfaces:**
- Consumes: `search_assets`, `AssetsSearchError`, `_extract_asset_ids` (from Tasks 1-2).
- Consumes: `resolve_campgrounds(ids: list) -> list` (existing, unchanged).
- Produces: `_search_campgrounds_by_rec_area(rec_area_ids) -> list`, `_search_campgrounds_fallback(query) -> list` — extracted from the old `_search_campgrounds_cached` body.

- [ ] **Step 1: Write the failing tests**

In `tests/services/test_search.py`, replace the block from `def test_search_campgrounds_by_query` through `def test_search_campgrounds_wraps_upstream_failure` (inclusive; old lines 104-131) with:

```python
def test_search_campgrounds_filters_to_campground_type(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "232447", "name": "Upper Pines Campground", "type": "Campground"},
        {"id": "245093", "name": "Boardstand /Military Road", "type": "Facility"},
    ])
    resolve_mock = mocker.patch(
        "core.services.search.resolve_campgrounds",
        return_value=[{
            "id": 232447, "name": "Upper Pines",
            "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
        }],
    )
    results = search.search_campgrounds("Upper Pines", None)
    resolve_mock.assert_called_once_with([232447])
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]


def test_search_campgrounds_by_rec_area_ignores_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds("ignored text", [2991])
    mock_provider.find_campgrounds.assert_called_once_with(rec_area_id=[2991])


def test_search_campgrounds_caches_by_query_and_rec_area_ids(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds(None, [2991, 2992])
    search.search_campgrounds(None, [2992, 2991])  # same set, different order
    assert mock_provider.find_campgrounds.call_count == 1


def test_search_campgrounds_falls_back_when_assets_unavailable(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("down"))
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.search_campgrounds("Upper Pines", None)
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(search_string="Upper Pines")


def test_search_campgrounds_fallback_wraps_upstream_failure(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("down"))
    mock_provider.find_campgrounds.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_campgrounds("fail-query", None)
```

Note: `make_facility` (old line 95) stays exactly where it is, immediately above this block — it's still used by `test_search_campgrounds_by_rec_area_ignores_query`, `test_search_campgrounds_caches_by_query_and_rec_area_ids`, and `test_search_campgrounds_falls_back_when_assets_unavailable`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_search.py -v -k campground`
Expected: FAIL — `test_search_campgrounds_filters_to_campground_type` and the fallback tests don't match current behavior yet.

- [ ] **Step 3: Write the implementation**

In `core/services/search.py`, replace the `search_campgrounds`/`_search_campgrounds_cached` block with:

```python
def search_campgrounds(query: Optional[str], rec_area_ids: Optional[list] = None) -> list:
    key = tuple(sorted(rec_area_ids)) if rec_area_ids else None
    return _search_campgrounds_cached(query, key)


@lru_cache(maxsize=128)
def _search_campgrounds_cached(query, rec_area_ids):
    if rec_area_ids:
        return _search_campgrounds_by_rec_area(rec_area_ids)
    try:
        assets = search_assets(query, "facility")
    except AssetsSearchError as e:
        logger.warning("RIDB assets search unavailable (%s), falling back to facilities query search", e)
        return _search_campgrounds_fallback(query)
    return resolve_campgrounds(_extract_asset_ids(assets, expected_type="Campground"))


def _search_campgrounds_by_rec_area(rec_area_ids) -> list:
    provider = _get_provider()
    try:
        facilities = provider.find_campgrounds(rec_area_id=list(rec_area_ids))
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return [_normalize_campground(f) for f in facilities]


def _search_campgrounds_fallback(query) -> list:
    provider = _get_provider()
    try:
        facilities = provider.find_campgrounds(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return [_normalize_campground(f) for f in facilities]
```

`_normalize_campground` and `resolve_campgrounds` stay unchanged immediately above/below this block.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: all tests pass (full file, including Task 2's recreation-area tests, campsite tests, and resolve_* tests).

- [ ] **Step 5: Commit**

```bash
git add core/services/search.py tests/services/test_search.py
git commit -m "feat: search campgrounds via RIDB assets substring search with fallback"
```

---

### Task 4: Manual verification against live RIDB

No mocks — confirms the real endpoint integration end-to-end, including the original complaint ("stan" returning nothing).

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass, no regressions in `tests/api/test_search.py` or elsewhere.

- [ ] **Step 2: Confirm substring matching works against the real RIDB API**

Run:

```bash
.venv/bin/python -c "
from core.services import search
results = search.search_recreation_areas('stan')
print(len(results), 'results')
for r in results:
    print(r)
"
```

Expected: a non-empty list including `Stanislaus National Forest` / `Stanislaus River Parks` (previously this returned `0` results, which is what started this investigation).

- [ ] **Step 3: Confirm campground search returns only `Campground`-typed results**

Run:

```bash
.venv/bin/python -c "
from core.services import search
results = search.search_campgrounds('stan', None)
print(len(results), 'results')
for r in results:
    print(r)
"
```

Expected: non-empty list, e.g. `Big Meadow (Stanislaus National Forest)`, each with a populated `recreation_area`/`recreation_area_id` (proving the resolve-based enrichment worked), and none of the non-campground `Facility`-typed noise (e.g. "Boardstand /Military Road", "Mt. Stanton Trailhead").

- [ ] **Step 4: Confirm the fallback path still works if the assets endpoint is unreachable**

Run:

```bash
.venv/bin/python -c "
from unittest.mock import patch
from core.services import search
from core.services.ridb_assets import AssetsSearchError
with patch('core.services.search.search_assets', side_effect=AssetsSearchError('simulated outage')):
    results = search.search_recreation_areas('Yosemite')
    print(len(results), 'results via fallback')
"
```

Expected: non-empty list (same as today's pre-change behavior — full-word match via camply), proving the fallback still reaches RIDB's documented `recareas` endpoint correctly.

- [ ] **Step 5: Manually exercise the scan wizard in the browser**

Start the backend (`.venv/bin/python -m uvicorn api.main:app --reload`) and frontend dev server, open the scan-creation wizard, type `stan` into the Recreation Areas field, and confirm Stanislaus-related results now appear. Repeat for the Campgrounds field.

---

## Self-Review

**Spec coverage:**
- Substring matching for both rec-area and campground search → Tasks 2 & 3.
- Detecting whether the endpoint is up/down → `AssetsSearchError` + per-call try/except fallback in Tasks 2 & 3, plus `assets_endpoint_healthy()` in Task 1 for manual/ops checks.
- Return at least 10 results → `search_assets` defaults to `limit=15` (Task 1).
- Type filtering (Rec Area only / Campground only) → `_extract_asset_ids(assets, expected_type=...)`, used with `"recarea"`/`"Rec Area"` in Task 2 and `"facility"`/`"Campground"` in Task 3.

**Placeholder scan:** none found — every step has complete, runnable code.

**Type consistency:** `search_assets(terms, asset_type, limit, timeout) -> list[dict]` is used identically in Tasks 2 and 3. `_extract_asset_ids(assets, expected_type=None) -> list[int]` signature matches both call sites (no `expected_type` for rec areas, `"Campground"` for campgrounds). `AssetsSearchError` is imported and caught the same way in both `search_recreation_areas` and `_search_campgrounds_cached`.

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-15-ridb-assets-substring-search.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
