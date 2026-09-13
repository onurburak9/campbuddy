from db.models import Scan, ScanStatus
from db.session import get_db
import api.database as api_db

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _make_scan(user_id, **kwargs):
    with get_db(api_db.get_factory()) as db:
        scan = Scan(user_id=user_id, search_windows=WINDOWS, **kwargs)
        db.add(scan)
        db.flush()
        return scan.id


def test_list_users_requires_admin(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/admin/users")
    assert resp.status_code == 403


def test_list_users_returns_all_users_for_admin(admin_client, user_in_db):
    client, _ = admin_client
    resp = client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert emails == {"admin@example.com", "user@example.com"}


def test_list_users_includes_scan_count(admin_client, user_in_db):
    client, _ = admin_client
    _make_scan(user_in_db["id"])
    resp = client.get("/api/v1/admin/users")
    by_email = {u["email"]: u for u in resp.json()}
    assert by_email["user@example.com"]["scans_used"] == 1
    assert by_email["admin@example.com"]["is_admin"] is True


def test_list_scans_requires_admin(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/admin/scans")
    assert resp.status_code == 403


def test_list_scans_returns_scans_across_users(admin_client, user_in_db):
    client, _ = admin_client
    _make_scan(user_in_db["id"])
    resp = client.get("/api/v1/admin/scans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["user_email"] == "user@example.com"


def test_pause_scan_requires_admin(auth_client, user_in_db):
    client, _ = auth_client
    scan_id = _make_scan(user_in_db["id"])
    resp = client.post(f"/api/v1/admin/scans/{scan_id}/pause")
    assert resp.status_code == 403


def test_resume_scan_requires_admin(auth_client, user_in_db):
    client, _ = auth_client
    scan_id = _make_scan(user_in_db["id"], status=ScanStatus.paused)
    resp = client.post(f"/api/v1/admin/scans/{scan_id}/resume")
    assert resp.status_code == 403


def test_delete_scan_requires_admin(auth_client, user_in_db):
    client, _ = auth_client
    scan_id = _make_scan(user_in_db["id"])
    resp = client.delete(f"/api/v1/admin/scans/{scan_id}")
    assert resp.status_code == 403


def test_pause_scan_pauses_any_users_scan(admin_client, user_in_db):
    client, _ = admin_client
    scan_id = _make_scan(user_in_db["id"], status=ScanStatus.active)
    resp = client.post(f"/api/v1/admin/scans/{scan_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_resume_scan_resumes_any_users_scan(admin_client, user_in_db):
    client, _ = admin_client
    scan_id = _make_scan(user_in_db["id"], status=ScanStatus.paused)
    resp = client.post(f"/api/v1/admin/scans/{scan_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_delete_scan_deletes_any_users_scan(admin_client, user_in_db):
    client, _ = admin_client
    scan_id = _make_scan(user_in_db["id"])
    resp = client.delete(f"/api/v1/admin/scans/{scan_id}")
    assert resp.status_code == 204
    with get_db(api_db.get_factory()) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        assert scan.deleted_at is not None


def test_pause_missing_scan_returns_404(admin_client):
    client, _ = admin_client
    resp = client.post("/api/v1/admin/scans/9999/pause")
    assert resp.status_code == 404


def test_get_scan_detail_requires_admin(auth_client, user_in_db):
    client, _ = auth_client
    scan_id = _make_scan(user_in_db["id"])
    resp = client.get(f"/api/v1/admin/scans/{scan_id}")
    assert resp.status_code == 403


def test_get_scan_detail_returns_full_config_and_owner_email(admin_client, user_in_db):
    client, _ = admin_client
    scan_id = _make_scan(user_in_db["id"], name="Yosemite trip", nights=2)
    resp = client.get(f"/api/v1/admin/scans/{scan_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == scan_id
    assert data["user_email"] == "user@example.com"
    assert data["name"] == "Yosemite trip"
    assert data["nights"] == 2
    assert data["search_windows"] == [{**WINDOWS[0], "expired": True}]


def test_get_scan_detail_returns_404_for_missing_scan(admin_client):
    client, _ = admin_client
    resp = client.get("/api/v1/admin/scans/9999")
    assert resp.status_code == 404


def test_list_scan_runs_requires_admin(auth_client, user_in_db):
    client, _ = auth_client
    scan_id = _make_scan(user_in_db["id"])
    resp = client.get(f"/api/v1/admin/scans/{scan_id}/runs")
    assert resp.status_code == 403


def test_list_scan_runs_returns_runs_for_any_users_scan(admin_client, scan_with_runs):
    client, _ = admin_client
    resp = client.get(f"/api/v1/admin/scans/{scan_with_runs.id}/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_list_scan_runs_respects_page_size(admin_client, scan_with_runs):
    client, _ = admin_client
    resp = client.get(f"/api/v1/admin/scans/{scan_with_runs.id}/runs?page=1&page_size=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_scan_runs_returns_404_for_missing_scan(admin_client):
    client, _ = admin_client
    resp = client.get("/api/v1/admin/scans/9999/runs")
    assert resp.status_code == 404
