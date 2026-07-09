# Campground/Campsite Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scan wizard's raw comma-separated Recreation Area / Campground / Campsite ID text fields with async search-select pickers backed by RIDB (via camply), plus id→name resolution so editing an existing scan shows real names instead of bare numbers.

**Architecture:** A new `core/services/search.py` wraps camply's `RecreationDotGov` provider (already a dependency — the sole external-API boundary per ADR 001) behind cached, pure functions. Six thin authenticated routes under `/api/v1/search` expose them. The frontend gets a new reusable `SearchSelect` combobox component and changes `ScanFormState`'s id fields from comma-separated strings to `{id, name}[]` arrays, with a one-time resolve-on-mount effect to hydrate names for an existing scan's stored ids.

**Tech Stack:** FastAPI + Pydantic v1 + camply 0.34.1 (backend), React + TypeScript + Vite + TanStack Query (frontend), pytest + pytest-mock (backend tests), Vitest + Testing Library + MSW (frontend tests).

## Global Constraints

- Backend: mock all external I/O (never call real camply/RIDB in tests); in-memory SQLite where DB access is involved (`docs/agents/testing.md`).
- Backend: pydantic v1 syntax only (ADR 005).
- `core/services/search.py` is the only module that imports from `camply` for RIDB reference-data lookups (ADR 001 — camply stays the sole external-API boundary).
- No DB schema changes, no migration — `Scan.rec_area_ids`/`campground_ids`/`campsite_ids` stay plain `List[int]` columns.
- All `/api/v1/search/*` routes require `Depends(get_current_user)` (not public).
- No new dependencies (no `cachetools`, no local mirror tables) — caching is `functools.lru_cache`, process-lifetime.
- `find_campgrounds(rec_area_id=..., ...)` and `find_campgrounds(search_string=..., ...)` are mutually exclusive in camply — never pass both.

---

### Task 1: `UpstreamError` exception + 502 handler

**Files:**
- Modify: `core/services/exceptions.py`
- Modify: `api/main.py`
- Test: `tests/api/test_search.py` (created in Task 7 — this task has no standalone test; it's exercised there)

**Interfaces:**
- Produces: `core.services.exceptions.UpstreamError` (subclass of `ServiceError`), mapped to HTTP 502 with `detail: str(exc)`.

- [ ] **Step 1: Add the exception**

In `core/services/exceptions.py`, add after `ValidationFailed`:

```python
class UpstreamError(ServiceError):
    pass
```

- [ ] **Step 2: Register the handler**

In `api/main.py`, update the import line:

```python
from core.services.exceptions import NotFound, Forbidden, LimitExceeded, InvalidState, ValidationFailed, UpstreamError
```

Add after `validation_failed_handler`:

```python
@app.exception_handler(UpstreamError)
async def upstream_error_handler(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})
```

- [ ] **Step 3: Run the full backend test suite to confirm no regression**

Run: `.venv/bin/pytest tests/ -v`
Expected: all passed (this is additive; nothing currently raises `UpstreamError`)

- [ ] **Step 4: Commit**

```bash
git add core/services/exceptions.py api/main.py
git commit -m "feat: add UpstreamError exception mapped to HTTP 502"
```

---

### Task 2: `ridb_api_key` setting

**Files:**
- Modify: `config/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.ridb_api_key: str` (default `""`), read from `.env` var `RIDB_API_KEY`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_settings.py`:

```python
def test_ridb_api_key_defaults_empty(env):
    s = Settings(_env_file=None)
    assert s.ridb_api_key == ""


def test_ridb_api_key_loaded_from_env(env):
    env.setenv("RIDB_API_KEY", "test-ridb-key")
    s = Settings(_env_file=None)
    assert s.ridb_api_key == "test-ridb-key"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_settings.py -v -k ridb_api_key`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'ridb_api_key'`

- [ ] **Step 3: Add the setting**

In `config/settings.py`, add to the `Settings` class (after `registration_enabled: bool = True`, if Task 1 of the self-registration plan already landed — otherwise after `cookie_secure: bool = False`):

```python
    ridb_api_key: str = ""
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_settings.py -v -k ridb_api_key`
Expected: 2 passed

- [ ] **Step 5: Run the full settings test file**

Run: `.venv/bin/pytest tests/test_settings.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat: add RIDB_API_KEY settings flag"
```

(Once this lands, set `RIDB_API_KEY` in your own local `.env` — not committed to the repo.)

---

### Task 3: `core/services/search.py` — recreation area search + resolve

**Files:**
- Create: `core/services/search.py`
- Create: `tests/services/test_search.py`

**Interfaces:**
- Produces: `_get_provider() -> RecreationDotGov` (module-private singleton), `search_recreation_areas(query: str) -> list[dict]`, `resolve_recreation_areas(ids: list[int]) -> list[dict]`. Each dict: `{"id": int|str, "name": str, "state": Optional[str]}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/services/test_search.py`:

```python
import pytest
from unittest.mock import MagicMock
from core.services import search
from core.services.exceptions import UpstreamError


@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    yield


@pytest.fixture
def mock_provider(mocker):
    provider = MagicMock()
    mocker.patch("core.services.search._get_provider", return_value=provider)
    return provider


def test_search_recreation_areas_normalizes_results(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA"}]
    mock_provider.find_recreation_areas.assert_called_once_with(search_string="Yosemite")


def test_search_recreation_areas_skips_malformed_items(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        {"missing": "required fields"},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert len(results) == 1


def test_search_recreation_areas_handles_missing_address(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 5, "RecAreaName": "No Address Area", "RECAREAADDRESS": []},
    ]
    results = search.search_recreation_areas("No Address")
    assert results == [{"id": 5, "name": "No Address Area", "state": None}]


def test_search_recreation_areas_caches_by_query(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    search.search_recreation_areas("Yosemite")
    search.search_recreation_areas("Yosemite")
    assert mock_provider.find_recreation_areas.call_count == 1


def test_search_recreation_areas_wraps_upstream_failure(mock_provider):
    mock_provider.find_recreation_areas.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_recreation_areas("Yosemite-fail")


def test_resolve_recreation_areas_normalizes_results(mock_provider):
    mock_provider.get_ridb_data.return_value = {
        "RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}],
    }
    results = search.resolve_recreation_areas([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA"}]
    mock_provider.get_ridb_data.assert_called_once_with(path="recareas/2991", params={"full": True})


def test_resolve_recreation_areas_skips_failed_ids(mock_provider):
    mock_provider.get_ridb_data.side_effect = [
        {"RecAreaID": 1, "RecAreaName": "Area One", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        ConnectionError("not found"),
    ]
    results = search.resolve_recreation_areas([1, 999])
    assert results == [{"id": 1, "name": "Area One", "state": "CA"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.services.search'`

- [ ] **Step 3: Implement the module**

Create `core/services/search.py`:

```python
from functools import lru_cache

from camply import RecreationDotGov
from camply.config import RIDBConfig
from camply.containers.api_responses import RecreationAreaResponse

from config.settings import get_settings
from core.services.exceptions import UpstreamError


@lru_cache(maxsize=1)
def _get_provider() -> RecreationDotGov:
    settings = get_settings()
    return RecreationDotGov(api_key=settings.ridb_api_key or None)


def _normalize_recreation_area(response: RecreationAreaResponse) -> dict:
    state = response.RECAREAADDRESS[0].AddressStateCode if response.RECAREAADDRESS else None
    return {"id": response.RecAreaID, "name": response.RecAreaName, "state": state}


@lru_cache(maxsize=128)
def search_recreation_areas(query: str) -> list:
    provider = _get_provider()
    try:
        raw = provider.find_recreation_areas(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    results = []
    for item in raw:
        try:
            results.append(_normalize_recreation_area(RecreationAreaResponse(**item)))
        except Exception:
            continue
    return results


def resolve_recreation_areas(ids: list) -> list:
    provider = _get_provider()
    results = []
    for rec_area_id in ids:
        try:
            data = provider.get_ridb_data(
                path=f"{RIDBConfig.REC_AREA_API_PATH}/{rec_area_id}",
                params={"full": True},
            )
            results.append(_normalize_recreation_area(RecreationAreaResponse(**data)))
        except Exception:
            continue
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add core/services/search.py tests/services/test_search.py
git commit -m "feat: add recreation area search and resolve via camply/RIDB"
```

---

### Task 4: `core/services/search.py` — campground search + resolve

**Files:**
- Modify: `core/services/search.py`
- Modify: `tests/services/test_search.py`

**Interfaces:**
- Consumes: `_get_provider()` (Task 3).
- Produces: `search_campgrounds(query: Optional[str], rec_area_ids: Optional[list[int]] = None) -> list[dict]`, `resolve_campgrounds(ids: list[int]) -> list[dict]`. Each dict: `{"id": int|str, "name": str, "recreation_area": str, "recreation_area_id": int|str}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/test_search.py`, and extend the `clear_caches` fixture:

```python
@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    search._search_campgrounds_cached.cache_clear()
    yield
```

(replacing the existing `clear_caches` fixture from Task 3)

```python
def make_facility(**overrides):
    facility = MagicMock()
    facility.facility_id = overrides.get("facility_id", 232447)
    facility.facility_name = overrides.get("facility_name", "Upper Pines")
    facility.recreation_area = overrides.get("recreation_area", "Yosemite National Park")
    facility.recreation_area_id = overrides.get("recreation_area_id", 2991)
    return facility


def test_search_campgrounds_by_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.search_campgrounds("Upper Pines", None)
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(search_string="Upper Pines")


def test_search_campgrounds_by_rec_area_ignores_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds("ignored text", [2991])
    mock_provider.find_campgrounds.assert_called_once_with(rec_area_id=[2991])


def test_search_campgrounds_caches_by_query_and_rec_area_ids(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds(None, [2991, 2992])
    search.search_campgrounds(None, [2992, 2991])  # same set, different order
    assert mock_provider.find_campgrounds.call_count == 1


def test_search_campgrounds_wraps_upstream_failure(mock_provider):
    mock_provider.find_campgrounds.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_campgrounds("fail-query", None)


def test_resolve_campgrounds_normalizes_results(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.resolve_campgrounds([232447])
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(campground_id=[232447])


def test_resolve_campgrounds_skips_failed_ids(mock_provider):
    mock_provider.find_campgrounds.side_effect = [
        [make_facility(facility_id=1, facility_name="Found")],
        ConnectionError("not found"),
    ]
    results = search.resolve_campgrounds([1, 999])
    assert len(results) == 1
    assert results[0]["id"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_search.py -v -k campground`
Expected: FAIL — `search_campgrounds`/`resolve_campgrounds` don't exist

- [ ] **Step 3: Implement**

Add to `core/services/search.py`, after `resolve_recreation_areas`:

```python
def _normalize_campground(facility) -> dict:
    return {
        "id": facility.facility_id,
        "name": facility.facility_name,
        "recreation_area": facility.recreation_area,
        "recreation_area_id": facility.recreation_area_id,
    }


def search_campgrounds(query, rec_area_ids=None) -> list:
    key = tuple(sorted(rec_area_ids)) if rec_area_ids else None
    return _search_campgrounds_cached(query, key)


@lru_cache(maxsize=128)
def _search_campgrounds_cached(query, rec_area_ids):
    provider = _get_provider()
    try:
        if rec_area_ids:
            facilities = provider.find_campgrounds(rec_area_id=list(rec_area_ids))
        else:
            facilities = provider.find_campgrounds(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return [_normalize_campground(f) for f in facilities]


def resolve_campgrounds(ids: list) -> list:
    provider = _get_provider()
    results = []
    for campground_id in ids:
        try:
            facilities = provider.find_campgrounds(campground_id=[campground_id])
        except Exception:
            continue
        if facilities:
            results.append(_normalize_campground(facilities[0]))
    return results
```

Add `from typing import Optional` to the top of `core/services/search.py` and change the `search_campgrounds` signature to `def search_campgrounds(query: Optional[str], rec_area_ids: Optional[list] = None) -> list:` for clarity.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_search.py -v -k campground`
Expected: 6 passed

- [ ] **Step 5: Run the full search test file to check for regressions**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add core/services/search.py tests/services/test_search.py
git commit -m "feat: add campground search and resolve via camply/RIDB"
```

---

### Task 5: `core/services/search.py` — campsite listing + resolve

**Files:**
- Modify: `core/services/search.py`
- Modify: `tests/services/test_search.py`

**Interfaces:**
- Consumes: `_get_provider()` (Task 3).
- Produces: `list_campsites(campground_ids: list[int]) -> list[dict]`, `resolve_campsites(ids: list[int]) -> list[dict]`. Each dict: `{"id": int|str, "name": str, "loop": str, "campground_id": int|str}`.

- [ ] **Step 1: Write the failing tests**

Update the `clear_caches` fixture in `tests/services/test_search.py` one more time:

```python
@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    search._search_campgrounds_cached.cache_clear()
    search._list_campsites_cached.cache_clear()
    yield
```

Add the tests:

```python
def make_campsite(**overrides):
    site = MagicMock()
    site.campsite_id = overrides.get("campsite_id", 12345)
    site.name = overrides.get("name", "Site A1")
    site.loop = overrides.get("loop", "Loop A")
    return site


def test_list_campsites_normalizes_results(mock_provider):
    mock_provider.paginate_recdotgov_campsites.return_value = [make_campsite()]
    results = search.list_campsites([232447])
    assert results == [{"id": 12345, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]
    mock_provider.paginate_recdotgov_campsites.assert_called_once_with(facility_id=232447)


def test_list_campsites_flattens_multiple_campgrounds(mock_provider):
    mock_provider.paginate_recdotgov_campsites.side_effect = [
        [make_campsite(campsite_id=1)],
        [make_campsite(campsite_id=2)],
    ]
    results = search.list_campsites([111, 222])
    assert [r["id"] for r in results] == [1, 2]


def test_list_campsites_caches_by_campground_ids(mock_provider):
    mock_provider.paginate_recdotgov_campsites.return_value = [make_campsite()]
    search.list_campsites([232447])
    search.list_campsites([232447])
    assert mock_provider.paginate_recdotgov_campsites.call_count == 1


def test_list_campsites_wraps_upstream_failure(mock_provider):
    mock_provider.paginate_recdotgov_campsites.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.list_campsites([999])


def test_resolve_campsites_normalizes_results(mock_provider):
    response = MagicMock(CampsiteID=12345, CampsiteName="Site A1", Loop="Loop A", FacilityID=232447)
    mock_provider.get_campsite_by_id.return_value = response
    results = search.resolve_campsites([12345])
    assert results == [{"id": 12345, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]
    mock_provider.get_campsite_by_id.assert_called_once_with(campsite_id=12345)


def test_resolve_campsites_skips_failed_ids(mock_provider):
    found = MagicMock(CampsiteID=1, CampsiteName="Found", Loop="Loop A", FacilityID=111)
    mock_provider.get_campsite_by_id.side_effect = [found, Exception("not found")]
    results = search.resolve_campsites([1, 999])
    assert len(results) == 1
    assert results[0]["id"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/services/test_search.py -v -k campsite`
Expected: FAIL — `list_campsites`/`resolve_campsites` don't exist

- [ ] **Step 3: Implement**

Add to `core/services/search.py`, at the end:

```python
def list_campsites(campground_ids: list) -> list:
    return _list_campsites_cached(tuple(sorted(campground_ids)))


@lru_cache(maxsize=128)
def _list_campsites_cached(campground_ids):
    provider = _get_provider()
    results = []
    try:
        for facility_id in campground_ids:
            for site in provider.paginate_recdotgov_campsites(facility_id=facility_id):
                results.append({
                    "id": site.campsite_id,
                    "name": site.name,
                    "loop": site.loop,
                    "campground_id": facility_id,
                })
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return results


def resolve_campsites(ids: list) -> list:
    provider = _get_provider()
    results = []
    for campsite_id in ids:
        try:
            response = provider.get_campsite_by_id(campsite_id=campsite_id)
        except Exception:
            continue
        results.append({
            "id": response.CampsiteID,
            "name": response.CampsiteName,
            "loop": response.Loop,
            "campground_id": response.FacilityID,
        })
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/services/test_search.py -v -k campsite`
Expected: 6 passed

- [ ] **Step 5: Run the full search test file**

Run: `.venv/bin/pytest tests/services/test_search.py -v`
Expected: all passed (20 tests total across Tasks 3-5)

- [ ] **Step 6: Commit**

```bash
git add core/services/search.py tests/services/test_search.py
git commit -m "feat: add campsite listing and resolve via camply/RIDB"
```

---

### Task 6: Response schemas

**Files:**
- Modify: `api/schemas.py`

**Interfaces:**
- Produces: `RecreationAreaResult`, `CampgroundResult`, `CampsiteResult` Pydantic models (plain response shapes, not ORM-backed — no `orm_mode`).

No dedicated test for this task — exercised end-to-end by the API tests in Task 7.

- [ ] **Step 1: Add the schemas**

In `api/schemas.py`, add near the end of the file:

```python
class RecreationAreaResult(BaseModel):
    id: int
    name: str
    state: Optional[str] = None


class CampgroundResult(BaseModel):
    id: int
    name: str
    recreation_area: str
    recreation_area_id: int


class CampsiteResult(BaseModel):
    id: int
    name: str
    loop: str
    campground_id: int
```

- [ ] **Step 2: Commit**

```bash
git add api/schemas.py
git commit -m "feat: add search result response schemas"
```

---

### Task 7: `/api/v1/search/*` routes

**Files:**
- Create: `api/routes/search.py`
- Modify: `api/main.py`
- Create: `tests/api/test_search.py`

**Interfaces:**
- Consumes: `core.services.search.*` (Tasks 3-5), `RecreationAreaResult`/`CampgroundResult`/`CampsiteResult` (Task 6), `get_current_user`/`get_db_dep` (existing `api/deps.py` — note: these routes don't touch the DB, but `get_current_user` requires `db` to look up the session user, so `get_db_dep` is still needed as a dependency of `get_current_user`).
- Produces: `GET /api/v1/search/recreation-areas`, `GET /api/v1/search/recreation-areas/resolve`, `GET /api/v1/search/campgrounds`, `GET /api/v1/search/campgrounds/resolve`, `GET /api/v1/search/campsites`, `GET /api/v1/search/campsites/resolve`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_search.py`:

```python
from unittest.mock import patch


def test_recreation_areas_requires_auth(client):
    resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 401


def test_recreation_areas_requires_min_query_length(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/recreation-areas", params={"q": "y"})
    assert resp.status_code == 422


def test_recreation_areas_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_recreation_areas", return_value=[{"id": 2991, "name": "Yosemite", "state": "CA"}]):
        resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 2991, "name": "Yosemite", "state": "CA"}]


def test_recreation_areas_upstream_failure_returns_502(auth_client):
    from core.services.exceptions import UpstreamError
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_recreation_areas", side_effect=UpstreamError("RIDB down")):
        resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 502


def test_recreation_areas_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_recreation_areas", return_value=[{"id": 2991, "name": "Yosemite", "state": "CA"}]):
        resp = client.get("/api/v1/search/recreation-areas/resolve", params={"ids": [2991]})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 2991, "name": "Yosemite", "state": "CA"}]


def test_campgrounds_requires_query_or_rec_area_ids(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/campgrounds")
    assert resp.status_code == 422


def test_campgrounds_by_query(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_campgrounds", return_value=[{"id": 1, "name": "Upper Pines", "recreation_area": "Yosemite", "recreation_area_id": 2991}]) as mock_search:
        resp = client.get("/api/v1/search/campgrounds", params={"q": "Upper Pines"})
    assert resp.status_code == 200
    mock_search.assert_called_once_with("Upper Pines", None)


def test_campgrounds_by_rec_area_ids(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_campgrounds", return_value=[]) as mock_search:
        resp = client.get("/api/v1/search/campgrounds", params={"rec_area_ids": [2991, 2992]})
    assert resp.status_code == 200
    mock_search.assert_called_once_with(None, [2991, 2992])


def test_campgrounds_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_campgrounds", return_value=[{"id": 1, "name": "Upper Pines", "recreation_area": "Yosemite", "recreation_area_id": 2991}]):
        resp = client.get("/api/v1/search/campgrounds/resolve", params={"ids": [1]})
    assert resp.status_code == 200


def test_campsites_requires_campground_ids(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/campsites")
    assert resp.status_code == 422


def test_campsites_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.list_campsites", return_value=[{"id": 1, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]) as mock_list:
        resp = client.get("/api/v1/search/campsites", params={"campground_ids": [232447]})
    assert resp.status_code == 200
    mock_list.assert_called_once_with([232447])


def test_campsites_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_campsites", return_value=[{"id": 1, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]):
        resp = client.get("/api/v1/search/campsites/resolve", params={"ids": [1]})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/api/test_search.py -v`
Expected: FAIL with 404s (no such router mounted yet)

- [ ] **Step 3: Implement the routes**

Create `api/routes/search.py`:

```python
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.deps import get_current_user
from api.schemas import RecreationAreaResult, CampgroundResult, CampsiteResult
from core.services import search as search_svc

router = APIRouter()


@router.get("/recreation-areas", response_model=List[RecreationAreaResult])
def search_recreation_areas(
    q: str = Query(..., min_length=2),
    user=Depends(get_current_user),
):
    return search_svc.search_recreation_areas(q)


@router.get("/recreation-areas/resolve", response_model=List[RecreationAreaResult])
def resolve_recreation_areas(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_recreation_areas(ids)


@router.get("/campgrounds", response_model=List[CampgroundResult])
def search_campgrounds(
    q: Optional[str] = Query(default=None),
    rec_area_ids: Optional[List[int]] = Query(default=None),
    user=Depends(get_current_user),
):
    if not q and not rec_area_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide q or rec_area_ids")
    return search_svc.search_campgrounds(q, rec_area_ids)


@router.get("/campgrounds/resolve", response_model=List[CampgroundResult])
def resolve_campgrounds(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_campgrounds(ids)


@router.get("/campsites", response_model=List[CampsiteResult])
def list_campsites(
    campground_ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.list_campsites(campground_ids)


@router.get("/campsites/resolve", response_model=List[CampsiteResult])
def resolve_campsites(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_campsites(ids)
```

- [ ] **Step 4: Mount the router and the 502 handler dependency**

In `api/main.py`, update the router import line:

```python
from api.routes import auth, scans, users, search
```

Add after the `users.router` include:

```python
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])
```

(The `UpstreamError` → 502 handler was already added in Task 1.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/api/test_search.py -v`
Expected: 13 passed

- [ ] **Step 6: Run the full backend test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add api/routes/search.py api/main.py tests/api/test_search.py
git commit -m "feat: add /api/v1/search routes for recreation areas, campgrounds, campsites"
```

---

### Task 8: `SearchSelect` reusable frontend component

**Files:**
- Create: `frontend/src/components/ui/SearchSelect.tsx`
- Create: `frontend/src/components/ui/SearchSelect.test.tsx`

**Interfaces:**
- Produces: `SearchSelect<T extends { id: number; name: string }>` component:
  ```ts
  interface SearchSelectProps<T extends { id: number; name: string }> {
    label: string;
    selected: T[];
    onChange: (items: T[]) => void;
    search: (query: string) => Promise<T[]>;
    disabled?: boolean;
    placeholder?: string;
  }
  ```
  Debounces input 300ms, fires `search()` only at ≥2 characters, shows a loading spinner while pending, shows an error message if `search()` rejects, renders `selected` as removable chips, and includes an "Add by ID" numeric input + button that appends `{ id, name: \`ID ${id}\` } as T` without calling `search()`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ui/SearchSelect.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchSelect } from "./SearchSelect";

describe("SearchSelect", () => {
  it("does not search below 2 characters", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "y");
    await new Promise((r) => setTimeout(r, 350));
    expect(search).not.toHaveBeenCalled();
  });

  it("searches (debounced) at 2+ characters and shows results", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(search).toHaveBeenCalledWith("yo"), { timeout: 1000 });
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
  });

  it("selects a result and calls onChange with it appended", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    const onChange = vi.fn();
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={onChange} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => screen.getByText("Yosemite National Park"));
    await userEvent.click(screen.getByText("Yosemite National Park"));
    expect(onChange).toHaveBeenCalledWith([{ id: 2991, name: "Yosemite National Park" }]);
  });

  it("removes a selected chip", async () => {
    const onChange = vi.fn();
    render(
      <SearchSelect
        label="Recreation Areas"
        selected={[{ id: 2991, name: "Yosemite National Park" }]}
        onChange={onChange}
        search={vi.fn().mockResolvedValue([])}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /remove yosemite national park/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows an error message when search rejects", async () => {
    const search = vi.fn().mockRejectedValue(new Error("Search temporarily unavailable"));
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(screen.getByText(/search temporarily unavailable/i)).toBeInTheDocument());
  });

  it("adds a chip by raw id via the fallback input", async () => {
    const onChange = vi.fn();
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={onChange} search={vi.fn().mockResolvedValue([])} />);
    await userEvent.type(screen.getByLabelText(/add by id/i), "1074");
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(onChange).toHaveBeenCalledWith([{ id: 1074, name: "ID 1074" }]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/ui/SearchSelect.test.tsx`
Expected: FAIL — cannot find module `./SearchSelect`

- [ ] **Step 3: Implement `SearchSelect`**

Create `frontend/src/components/ui/SearchSelect.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Input } from "./Input";
import { Button } from "./Button";
import { Spinner } from "./Spinner";

interface Item {
  id: number;
  name: string;
}

interface SearchSelectProps<T extends Item> {
  label: string;
  selected: T[];
  onChange: (items: T[]) => void;
  search: (query: string) => Promise<T[]>;
  disabled?: boolean;
  placeholder?: string;
}

export function SearchSelect<T extends Item>({
  label,
  selected,
  onChange,
  search,
  disabled,
  placeholder,
}: SearchSelectProps<T>) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addById, setAddById] = useState("");

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setError(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      search(query)
        .then((items) => {
          if (!cancelled) setResults(items);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Search failed");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, search]);

  function select(item: T) {
    if (!selected.some((s) => s.id === item.id)) onChange([...selected, item]);
    setQuery("");
    setResults([]);
  }

  function remove(id: number) {
    onChange(selected.filter((s) => s.id !== id));
  }

  function addRawId() {
    const id = Number(addById.trim());
    if (!Number.isFinite(id) || id <= 0) return;
    if (!selected.some((s) => s.id === id)) {
      onChange([...selected, { id, name: `ID ${id}` } as T]);
    }
    setAddById("");
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {selected.map((item) => (
          <span key={item.id} className="inline-flex items-center gap-1 rounded-full bg-forest-100 px-2.5 py-1 text-sm text-forest-800 dark:bg-[#222] dark:text-[#EEE]">
            {item.name}
            <button type="button" aria-label={`Remove ${item.name}`} onClick={() => remove(item.id)}>
              ×
            </button>
          </span>
        ))}
      </div>
      <Input
        label={label}
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <Spinner className="h-4 w-4" />}
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
        <p className="text-sm text-stone-500 dark:text-[#888]">No matches — try a different search or add by ID.</p>
      )}
      {results.length > 0 && (
        <ul className="max-h-48 overflow-y-auto rounded-md border border-sand-200 dark:border-[#222]">
          {results.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-sm hover:bg-sand-100 dark:hover:bg-[#222]"
                onClick={() => select(item)}
              >
                {item.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <Input
          label="Add by ID"
          value={addById}
          onChange={(e) => setAddById(e.target.value)}
          placeholder="e.g. 1074"
        />
        <Button type="button" variant="secondary" size="sm" onClick={addRawId}>
          Add
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/ui/SearchSelect.test.tsx`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/SearchSelect.tsx frontend/src/components/ui/SearchSelect.test.tsx
git commit -m "feat: add reusable SearchSelect combobox component"
```

---

### Task 9: `api/search.ts` client

**Files:**
- Create: `frontend/src/api/search.ts`

**Interfaces:**
- Produces:
  ```ts
  export interface RecreationAreaResult { id: number; name: string; state: string | null }
  export interface CampgroundResult { id: number; name: string; recreation_area: string; recreation_area_id: number }
  export interface CampsiteResult { id: number; name: string; loop: string; campground_id: number }

  export const search: {
    recreationAreas(q: string): Promise<RecreationAreaResult[]>;
    resolveRecreationAreas(ids: number[]): Promise<RecreationAreaResult[]>;
    campgrounds(q: string | null, recAreaIds: number[] | null): Promise<CampgroundResult[]>;
    resolveCampgrounds(ids: number[]): Promise<CampgroundResult[]>;
    campsites(campgroundIds: number[]): Promise<CampsiteResult[]>;
    resolveCampsites(ids: number[]): Promise<CampsiteResult[]>;
  };
  ```

No dedicated unit test for this thin client — it's exercised through `SearchSelect` integration in Task 10 and through the manual browser check.

- [ ] **Step 1: Implement**

Create `frontend/src/api/search.ts`:

```ts
import { fetchApi } from "./client";

export interface RecreationAreaResult {
  id: number;
  name: string;
  state: string | null;
}

export interface CampgroundResult {
  id: number;
  name: string;
  recreation_area: string;
  recreation_area_id: number;
}

export interface CampsiteResult {
  id: number;
  name: string;
  loop: string;
  campground_id: number;
}

function toParams(params: Record<string, string | number[] | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null) continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, String(v)));
    else qs.append(key, String(value));
  }
  return qs.toString();
}

export const search = {
  recreationAreas: (q: string) =>
    fetchApi<RecreationAreaResult[]>(`/search/recreation-areas?${toParams({ q })}`),
  resolveRecreationAreas: (ids: number[]) =>
    fetchApi<RecreationAreaResult[]>(`/search/recreation-areas/resolve?${toParams({ ids })}`),
  campgrounds: (q: string | null, recAreaIds: number[] | null) =>
    fetchApi<CampgroundResult[]>(`/search/campgrounds?${toParams({ q, rec_area_ids: recAreaIds })}`),
  resolveCampgrounds: (ids: number[]) =>
    fetchApi<CampgroundResult[]>(`/search/campgrounds/resolve?${toParams({ ids })}`),
  campsites: (campgroundIds: number[]) =>
    fetchApi<CampsiteResult[]>(`/search/campsites?${toParams({ campground_ids: campgroundIds })}`),
  resolveCampsites: (ids: number[]) =>
    fetchApi<CampsiteResult[]>(`/search/campsites/resolve?${toParams({ ids })}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/search.ts
git commit -m "feat: add search API client"
```

---

### Task 10: Replace raw ID inputs with `SearchSelect` in the scan wizard

**Files:**
- Modify: `frontend/src/components/scans/useScanFormState.ts`
- Modify: `frontend/src/components/scans/useScanFormState.test.ts`
- Modify: `frontend/src/components/scans/ScanForm.tsx`
- Modify: `frontend/src/components/scans/ScanForm.test.tsx`
- Modify: `frontend/src/components/wizard/ScanWizardPanel.tsx`

**Interfaces:**
- Consumes: `SearchSelect` (Task 8), `search` API client (Task 9).
- Produces: `SelectedItem { id: number; name: string }` (exported from `useScanFormState.ts`); `ScanFormState.recAreaIds/campgroundIds/campsiteIds: SelectedItem[]` (previously `string`); `ProviderSitesFields` now renders three `SearchSelect` fields instead of three `Input` fields, resolving any pre-filled (fallback-labeled) ids to real names once on mount.

This is one task, not two — the state-shape change and its two consumers (`ScanForm.tsx`, `ScanWizardPanel.tsx`) must land together, since splitting them would leave the frontend in a non-type-checking, non-compiling state between commits.

- [ ] **Step 1: Write the failing test**

Replace the contents of `frontend/src/components/scans/useScanFormState.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useScanFormState } from "./useScanFormState";
import type { Scan } from "../../types";

describe("useScanFormState", () => {
  it("builds a create payload from selected id items", () => {
    const { result } = renderHook(() => useScanFormState());
    act(() => {
      result.current.set("provider", "RecreationDotGov");
      result.current.set("recAreaIds", [{ id: 2991, name: "Yosemite" }, { id: 2992, name: "Sequoia" }]);
      result.current.set("windows", [{ start_date: "2026-07-01", end_date: "2026-07-03" }]);
      result.current.set("nights", 2);
    });
    const payload = result.current.toScanCreatePayload();
    expect(payload.rec_area_ids).toEqual([2991, 2992]);
    expect(payload.search_windows).toHaveLength(1);
    expect(payload.nights).toBe(2);
  });

  it("omits empty id fields as null", () => {
    const { result } = renderHook(() => useScanFormState());
    const payload = result.current.toScanCreatePayload();
    expect(payload.campground_ids).toBeNull();
    expect(payload.campsite_ids).toBeNull();
  });

  it("pre-fills id fields from an existing scan with a fallback 'ID {n}' label", () => {
    const scan = {
      rec_area_ids: [2991],
      campground_ids: [232447],
      campsite_ids: null,
    } as unknown as Scan;
    const { result } = renderHook(() => useScanFormState(scan));
    expect(result.current.state.recAreaIds).toEqual([{ id: 2991, name: "ID 2991" }]);
    expect(result.current.state.campgroundIds).toEqual([{ id: 232447, name: "ID 232447" }]);
    expect(result.current.state.campsiteIds).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/scans/useScanFormState.test.ts`
Expected: FAIL — `recAreaIds` is a string, not comparable to the array shape; type errors at compile time too

- [ ] **Step 3: Update `useScanFormState.ts`**

Replace the contents of `frontend/src/components/scans/useScanFormState.ts`:

```ts
import { useState, useCallback } from "react";
import type { Scan, ScanCreatePayload, ScanUpdatePayload, SearchWindow } from "../../types";

export interface SelectedItem {
  id: number;
  name: string;
}

export interface ScanFormState {
  name: string;
  provider: string;
  recAreaIds: SelectedItem[];
  campgroundIds: SelectedItem[];
  campsiteIds: SelectedItem[];
  windows: SearchWindow[];
  nights: number;
  daysOfWeek: number[];
  weekendsOnly: boolean;
  pollingInterval: number;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyNewOnly: boolean;
}

function idsAsFallbackItems(ids: number[] | null | undefined): SelectedItem[] {
  return (ids ?? []).map((id) => ({ id, name: `ID ${id}` }));
}

function fromScan(scan?: Scan): ScanFormState {
  return {
    name: scan?.name ?? "",
    provider: scan?.provider ?? "RecreationDotGov",
    recAreaIds: idsAsFallbackItems(scan?.rec_area_ids),
    campgroundIds: idsAsFallbackItems(scan?.campground_ids),
    campsiteIds: idsAsFallbackItems(scan?.campsite_ids),
    windows: scan?.search_windows ?? [],
    nights: scan?.nights ?? 1,
    daysOfWeek: scan?.days_of_week ?? [],
    weekendsOnly: scan?.weekends_only ?? false,
    pollingInterval: scan?.polling_interval ?? 300,
    notifyEmail: scan?.notify_via_email ?? true,
    notifyTelegram: scan?.notify_via_telegram ?? false,
    notifyNewOnly: scan?.notify_on_new_only ?? true,
  };
}

export function useScanFormState(scan?: Scan) {
  const [state, setState] = useState<ScanFormState>(() => fromScan(scan));

  const set = useCallback(<K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toScanCreatePayload = (): ScanCreatePayload => ({
    provider: state.provider,
    name: state.name.trim() || null,
    polling_interval: state.pollingInterval,
    rec_area_ids: state.recAreaIds.length ? state.recAreaIds.map((i) => i.id) : null,
    campground_ids: state.campgroundIds.length ? state.campgroundIds.map((i) => i.id) : null,
    campsite_ids: state.campsiteIds.length ? state.campsiteIds.map((i) => i.id) : null,
    search_windows: state.windows,
    nights: state.nights,
    days_of_week: state.daysOfWeek.length ? state.daysOfWeek : null,
    weekends_only: state.weekendsOnly,
    notify_via_email: state.notifyEmail,
    notify_via_telegram: state.notifyTelegram,
    notify_on_new_only: state.notifyNewOnly,
  });

  const toScanUpdatePayload = (): ScanUpdatePayload => {
    const { provider: _omit, ...rest } = toScanCreatePayload();
    return rest;
  };

  return { state, set, toScanCreatePayload, toScanUpdatePayload };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/scans/useScanFormState.test.ts`
Expected: 3 passed

- [ ] **Step 5: Write the failing test for `ProviderSitesFields`**

`ScanForm.test.tsx` currently only tests `NotificationsFields` (per the file read during planning) and builds a `ScanFormState` via a local `makeState` helper with `recAreaIds: ""` etc. Update that helper to the new shape — replace:

```ts
    recAreaIds: "",
    campgroundIds: "",
    campsiteIds: "",
```

with:

```ts
    recAreaIds: [],
    campgroundIds: [],
    campsiteIds: [],
```

in `frontend/src/components/scans/ScanForm.test.tsx`'s `makeState` function. This alone doesn't need a new failing-test step since `NotificationsFields` doesn't touch these fields — it's a type-correctness fix. Add a new test for `ProviderSitesFields` in the same file:

```tsx
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { ProviderSitesFields } from "./ScanForm";

vi.mock("../../api/search", () => ({
  search: {
    recreationAreas: vi.fn().mockResolvedValue([]),
    resolveRecreationAreas: vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]),
    campgrounds: vi.fn().mockResolvedValue([]),
    resolveCampgrounds: vi.fn().mockResolvedValue([]),
    campsites: vi.fn().mockResolvedValue([]),
    resolveCampsites: vi.fn().mockResolvedValue([]),
  },
}));

function wrapWithQueryClient(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("ProviderSitesFields — id resolution", () => {
  it("resolves a fallback 'ID {n}' label to the real name on mount", async () => {
    const state = makeState(300);
    state.recAreaIds = [{ id: 2991, name: "ID 2991" }];
    render(wrapWithQueryClient(<ProviderSitesFields state={state} set={() => {}} />));
    expect(screen.getByText("ID 2991")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
  });
});
```

(Add `import { render, screen, waitFor } from "@testing-library/react";` and `import { vi } from "vitest";` to the existing import block at the top of the file if not already present — the file already imports `render`/`screen` from the earlier read; add `waitFor` and `vi` alongside them.)

- [ ] **Step 6: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/scans/ScanForm.test.tsx`
Expected: FAIL — `ProviderSitesFields` still renders plain `Input`s with `.trim()`-based logic that no longer type-checks against the array shape

- [ ] **Step 7: Rewrite `ProviderSitesFields`**

In `frontend/src/components/scans/ScanForm.tsx`, replace the imports at the top:

```ts
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import { PROVIDERS } from "../../types";
import type { ScanFormState } from "./useScanFormState";
import type { SearchWindow } from "../../types";
import { formatInterval } from "../../lib/format";
```

with:

```ts
import { useQuery } from "@tanstack/react-query";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { SearchSelect } from "../ui/SearchSelect";
import { Toggle } from "../ui/Toggle";
import { Button } from "../ui/Button";
import { PROVIDERS } from "../../types";
import { search } from "../../api/search";
import type { ScanFormState, SelectedItem } from "./useScanFormState";
import type { SearchWindow } from "../../types";
import { formatInterval } from "../../lib/format";
```

Replace the `ProviderSitesFields` function body:

```tsx
export function ProviderSitesFields({ state, set }: { state: ScanFormState; set: Setter }) {
  const recAreaIds = state.recAreaIds.map((i) => i.id);
  const campgroundIds = state.campgroundIds.map((i) => i.id);

  useResolveFallbackLabels(state.recAreaIds, search.resolveRecreationAreas, (items) => set("recAreaIds", items));
  useResolveFallbackLabels(state.campgroundIds, search.resolveCampgrounds, (items) => set("campgroundIds", items));
  useResolveFallbackLabels(state.campsiteIds, search.resolveCampsites, (items) => set("campsiteIds", items));

  return (
    <div className="space-y-4">
      <Input label="Scan name (optional)" value={state.name}
        onChange={(e) => set("name", e.target.value)} placeholder="Yosemite summer trip" />
      <Select label="Provider" value={state.provider} onChange={(v) => set("provider", v)}
        options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
      <SearchSelect
        label="Recreation Areas"
        selected={state.recAreaIds}
        onChange={(items) => set("recAreaIds", items)}
        search={(q) => search.recreationAreas(q)}
        placeholder="Search by name, e.g. Yosemite"
      />
      <SearchSelect
        label="Campgrounds (optional)"
        selected={state.campgroundIds}
        onChange={(items) => set("campgroundIds", items)}
        search={(q) => search.campgrounds(q, recAreaIds.length ? recAreaIds : null)}
        placeholder="Search by name"
      />
      <SearchSelect
        label="Campsites (optional)"
        selected={state.campsiteIds}
        onChange={(items) => set("campsiteIds", items)}
        search={() => (campgroundIds.length ? search.campsites(campgroundIds) : Promise.resolve([]))}
        disabled={campgroundIds.length === 0}
        placeholder={campgroundIds.length ? "Search by site name" : "Select a campground first"}
      />
    </div>
  );
}

function useResolveFallbackLabels(
  items: SelectedItem[],
  resolve: (ids: number[]) => Promise<SelectedItem[]>,
  apply: (items: SelectedItem[]) => void,
) {
  const fallbackIds = items.filter((i) => i.name === `ID ${i.id}`).map((i) => i.id);
  const { data } = useQuery({
    queryKey: ["resolve-ids", resolve.name, fallbackIds],
    queryFn: () => resolve(fallbackIds),
    enabled: fallbackIds.length > 0,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (!data || data.length === 0) return;
    const byId = new Map(data.map((d) => [d.id, d] as const));
    const updated = items.map((i) => byId.get(i.id) ?? i);
    if (updated.some((u, idx) => u !== items[idx])) apply(updated);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
}
```

Add `import { useEffect } from "react";` to the top of the file alongside the other imports.

- [ ] **Step 8: Fix `ScanWizardPanel.tsx`'s `hasAnyIds` check**

In `frontend/src/components/wizard/ScanWizardPanel.tsx`, replace:

```ts
  const hasAnyIds = !!(form.state.recAreaIds.trim() || form.state.campgroundIds.trim() || form.state.campsiteIds.trim());
```

with:

```ts
  const hasAnyIds = form.state.recAreaIds.length > 0 || form.state.campgroundIds.length > 0 || form.state.campsiteIds.length > 0;
```

- [ ] **Step 9: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/scans/ScanForm.test.tsx`
Expected: all passed (existing `NotificationsFields` tests + new `ProviderSitesFields` resolution test)

- [ ] **Step 10: Run the full frontend test suite and type-check**

Run (from `frontend/`): `npx vitest run`
Expected: all passed

Run (from `frontend/`): `npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 11: Manually verify in the browser**

Run: `cd frontend && npm run dev`. Log in, open "New Scan," on step 1 type "Yosemite" into Recreation Areas and confirm a dropdown of matches appears; select one; confirm a chip appears. Type a campground name and confirm campgrounds are scoped to the selected rec area. Select a campground and confirm the Campsites field becomes enabled and lists that campground's sites. Create the scan, then open its Settings tab and confirm the same three fields show real names (not bare IDs) for the values you just picked.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/scans/useScanFormState.ts frontend/src/components/scans/useScanFormState.test.ts frontend/src/components/scans/ScanForm.tsx frontend/src/components/scans/ScanForm.test.tsx frontend/src/components/wizard/ScanWizardPanel.tsx
git commit -m "feat: replace raw ID inputs with SearchSelect in the scan wizard"
```
