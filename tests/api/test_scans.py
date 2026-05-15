import pytest
from db.models import Scan, User
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


def test_get_scan_returns_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"])
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id


def test_get_scan_returns_403_for_wrong_owner(auth_client):
    client, _ = auth_client
    with get_db(api_db.get_factory()) as db:
        other = User(email="other@e.com", hashed_password=hash_password("pw"), scan_limit=5)
        db.add(other)
        db.flush()
        other_id = other.id
    scan_id = _make_scan(other_id)
    resp = client.get(f"/api/v1/scans/{scan_id}")
    assert resp.status_code == 403


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


def test_resume_scan(auth_client):
    client, info = auth_client
    scan_id = _make_scan(info["id"], status="paused")
    resp = client.post(f"/api/v1/scans/{scan_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


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


def test_all_scan_routes_require_auth(client):
    for method, path in [
        ("GET", "/api/v1/scans"),
        ("POST", "/api/v1/scans"),
        ("GET", "/api/v1/scans/1"),
        ("PATCH", "/api/v1/scans/1"),
        ("DELETE", "/api/v1/scans/1"),
    ]:
        fn = getattr(client, method.lower())
        resp = fn(path, json={}) if method in ("POST", "PATCH") else fn(path)
        assert resp.status_code == 401, f"{method} {path} should return 401"
