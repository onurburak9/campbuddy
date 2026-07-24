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
