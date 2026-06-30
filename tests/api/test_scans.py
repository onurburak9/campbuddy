import pytest
from db.models import Scan, ScanStatus, User
from db.session import get_db
import api.database as api_db
from api.auth import hash_password

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _make_scan(user_id, **kwargs):
    with get_db(api_db.get_factory()) as db:
        scan = Scan(user_id=user_id, search_windows=WINDOWS, **kwargs)
        db.add(scan)
        db.flush()
        return scan.id


def test_list_scans_returns_empty_for_new_user(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/scans")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_scan_returns_201(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "nights": 2})
    assert resp.status_code == 201
    data = resp.json()
    assert data["nights"] == 2
    assert data["status"] == "active"


def test_create_scan_enforces_limit(auth_client):
    client, info = auth_client
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == info["id"]).first()
        user.scan_limit = 1
    client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert resp.status_code == 409


def test_create_scan_includes_defaults(auth_client):
    """Create with only search_windows — defaults for polling_interval, nights, etc. are included."""
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert resp.status_code == 201
    data = resp.json()
    assert data["polling_interval"] == 300
    assert data["nights"] == 1
    assert data["provider"] == "RecreationDotGov"


def test_create_scan_rejects_invalid_provider(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "provider": "FakeProvider"})
    assert resp.status_code == 422


def test_create_scan_rejects_low_polling_interval(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "polling_interval": 10})
    assert resp.status_code == 422


def test_create_scan_rejects_zero_nights(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "nights": 0})
    assert resp.status_code == 422


def test_create_scan_rejects_invalid_search_window(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": [{"start_date": "2026-07-06", "end_date": "2026-07-03"}]})
    assert resp.status_code == 422


def test_create_scan_rejects_empty_search_windows(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": []})
    assert resp.status_code == 422


def test_create_scan_rejects_invalid_day_of_week(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/scans", json={"search_windows": WINDOWS, "days_of_week": [0, 7]})
    assert resp.status_code == 422


def test_get_scan_returns_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id


def test_get_scan_returns_404_for_wrong_owner(auth_client):
    client, _ = auth_client
    with get_db(api_db.get_factory()) as db:
        other = User(email="other@e.com", hashed_password=hash_password("pw"), scan_limit=5)
        db.add(other)
        db.flush()
        other_id = other.id
    scan_id = _make_scan(other_id)
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 404


def test_get_scan_returns_404_for_missing(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/scans/9999")
    assert resp.status_code == 404


def test_update_scan_changes_nights(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.patch(f"/api/v1/scans/{scan_id}", json={"nights": 4})
    assert resp.status_code == 200
    assert resp.json()["nights"] == 4


def test_patch_scan_ignores_status_field(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.patch(f"/api/v1/scans/{scan_id}", json={"status": "paused", "nights": 5})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert resp.json()["nights"] == 5


def test_delete_scan_soft_deletes(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.delete(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 204
    resp2 = client.get(f"/api/v1/scans/{scan_id}")
    assert resp2.status_code == 404


def test_pause_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.post(f"/api/v1/scans/{scan_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_pause_already_paused_scan_returns_409(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"], status=ScanStatus.paused)
    resp = client.post(f"/api/v1/scans/{scan_id}/pause")
    assert resp.status_code == 409


def test_resume_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"], status=ScanStatus.paused)
    resp = client.post(f"/api/v1/scans/{scan_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_resume_active_scan_returns_409(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.post(f"/api/v1/scans/{scan_id}/resume")
    assert resp.status_code == 409


def test_list_runs_returns_empty(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_results_returns_empty(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}/results")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_stats_returns_zeros_for_new_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sites_found"] == 0
    assert data["in_cart"] == 0
    assert data["total_runs"] == 0
    assert data["success_rate"] == 0


def test_get_stats_returns_404_for_wrong_owner(auth_client):
    client, _ = auth_client
    with get_db(api_db.get_factory()) as db:
        other = User(email="other2@e.com", hashed_password=hash_password("pw"), scan_limit=5)
        db.add(other)
        db.flush()
        other_id = other.id
    scan_id = _make_scan(other_id)
    resp = client.get(f"/api/v1/scans/{scan_id}/stats")
    assert resp.status_code == 404


def test_get_stats_returns_404_for_missing_scan(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/scans/9999/stats")
    assert resp.status_code == 404


def test_get_stats_requires_auth(client):
    resp = client.get("/api/v1/scans/1/stats")
    assert resp.status_code == 401


def test_all_scan_routes_require_auth(client):
    for path in [
        "/api/v1/scans",
        "/api/v1/scans/1",
        "/api/v1/scans/1/runs",
        "/api/v1/scans/1/results",
        "/api/v1/scans/1/stats",
    ]:
        resp = client.get(path)
        assert resp.status_code == 401, f"GET {path} should return 401"
    for path in ["/api/v1/scans"]:
        resp = client.post(path, json={"search_windows": WINDOWS})
        assert resp.status_code == 401, f"POST {path} should return 401"
    for path in [
        "/api/v1/scans/1/pause",
        "/api/v1/scans/1/resume",
    ]:
        resp = client.post(path)
        assert resp.status_code == 401, f"POST {path} should return 401"
    resp = client.patch("/api/v1/scans/1", json={"nights": 2})
    assert resp.status_code == 401, "PATCH /api/v1/scans/1 should return 401"
    resp = client.delete("/api/v1/scans/1")
    assert resp.status_code == 401, "DELETE /api/v1/scans/1 should return 401"


def test_runs_outcome_filter(auth_client, scan_with_runs):
    client, _ = auth_client
    r = client.get(f"/api/v1/scans/{scan_with_runs.id}/runs?outcome=success")
    assert r.status_code == 200
    assert all(item["outcome"] == "success" for item in r.json())


def test_run_results_endpoint(auth_client, scan_with_results):
    client, _ = auth_client
    scan, run = scan_with_results
    r = client.get(f"/api/v1/scans/{scan.id}/runs/{run.id}/results")
    assert r.status_code == 200
    body = r.json()
    assert body and all(item["scan_run_id"] == run.id for item in body)


def test_run_results_404_for_unknown_run(auth_client, scan_with_results):
    client, _ = auth_client
    scan, _ = scan_with_results
    r = client.get(f"/api/v1/scans/{scan.id}/runs/999999/results")
    assert r.status_code == 404
