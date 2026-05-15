"""End-to-end API integration tests.

Each test exercises a complete user-facing scenario spanning multiple endpoints.
These complement the per-route unit tests in test_auth.py, test_scans.py, test_users.py
by catching regressions in how routes compose together.
"""
import pytest
from db.models import User
from db.session import get_db
import api.database as api_db
from api.auth import hash_password


WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _seed_user(email, password="password123", scan_limit=5):
    with get_db(api_db.get_factory()) as db:
        user = User(email=email, hashed_password=hash_password(password), scan_limit=scan_limit)
        db.add(user)
        db.flush()
        return user.id


def _login(client, email="user@example.com", password="password123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp


# -----------------------------------------------------------------------------
# Scenario 1: Full scan lifecycle (the happy path most users will hit daily)
# -----------------------------------------------------------------------------

def test_full_scan_lifecycle(client):
    """Login → create scan → list → get → patch → pause → resume → delete → list (empty)."""
    _seed_user("u@e.com")
    _login(client, "u@e.com")

    # Empty dashboard
    resp = client.get("/api/v1/scans")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create
    create = client.post("/api/v1/scans", json={
        "search_windows": WINDOWS, "nights": 2, "name": "Yosemite July",
    })
    assert create.status_code == 201
    scan = create.json()
    sid = scan["id"]
    assert scan["nights"] == 2
    assert scan["name"] == "Yosemite July"
    assert scan["status"] == "active"

    # List shows new scan
    resp = client.get("/api/v1/scans")
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == sid

    # Get one
    resp = client.get(f"/api/v1/scans/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sid

    # Patch nights
    resp = client.patch(f"/api/v1/scans/{sid}", json={"nights": 3})
    assert resp.status_code == 200
    assert resp.json()["nights"] == 3

    # Pause
    resp = client.post(f"/api/v1/scans/{sid}/pause")
    assert resp.json()["status"] == "paused"

    # Resume
    resp = client.post(f"/api/v1/scans/{sid}/resume")
    assert resp.json()["status"] == "active"

    # Delete
    resp = client.delete(f"/api/v1/scans/{sid}")
    assert resp.status_code == 204

    # Gone
    resp = client.get(f"/api/v1/scans/{sid}")
    assert resp.status_code == 404

    # Dashboard empty again
    resp = client.get("/api/v1/scans")
    assert resp.json() == []


# -----------------------------------------------------------------------------
# Scenario 2: Profile update flow (settings page)
# -----------------------------------------------------------------------------

def test_profile_update_flow(client):
    """Login → /me shows defaults → patch profile → /me reflects changes."""
    _seed_user("profile@e.com")
    _login(client, "profile@e.com")

    me = client.get("/api/v1/auth/me").json()
    assert me["email"] == "profile@e.com"
    assert me["scan_limit"] == 5
    assert me["scans_used"] == 0

    # Update email + telegram
    resp = client.patch("/api/v1/users/me", json={
        "email": "newemail@e.com",
        "telegram_chat_id": "123456",
        "recreationgov_email": "rec@e.com",
        "recreationgov_password": "myseekrit",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "newemail@e.com"
    assert body["telegram_chat_id"] == "123456"
    assert body["recreationgov_email"] == "rec@e.com"
    # Secrets must NOT be in response
    assert "recreationgov_password" not in body
    assert "hashed_password" not in body

    # /me reflects the email change
    me_after = client.get("/api/v1/auth/me").json()
    assert me_after["email"] == "newemail@e.com"


# -----------------------------------------------------------------------------
# Scenario 3: Multi-user isolation (per-user scan visibility)
# -----------------------------------------------------------------------------

def test_multi_user_scans_isolated(client):
    """User A's scans are invisible to User B; B cannot mutate A's scans."""
    a_id = _seed_user("alice@e.com")
    b_id = _seed_user("bob@e.com")

    # Alice logs in and creates a scan
    _login(client, "alice@e.com")
    a_scan = client.post("/api/v1/scans", json={"search_windows": WINDOWS}).json()
    a_sid = a_scan["id"]

    # Alice logs out
    client.post("/api/v1/auth/logout")

    # Bob logs in
    _login(client, "bob@e.com")

    # Bob sees empty list (alice's scan is not his)
    resp = client.get("/api/v1/scans")
    assert resp.json() == []

    # Bob cannot read Alice's scan
    assert client.get(f"/api/v1/scans/{a_sid}").status_code == 403
    assert client.patch(f"/api/v1/scans/{a_sid}", json={"nights": 9}).status_code == 403
    assert client.delete(f"/api/v1/scans/{a_sid}").status_code == 403
    assert client.post(f"/api/v1/scans/{a_sid}/pause").status_code == 403
    assert client.get(f"/api/v1/scans/{a_sid}/runs").status_code == 403


# -----------------------------------------------------------------------------
# Scenario 4: Scan limit enforcement under realistic usage
# -----------------------------------------------------------------------------

def test_scan_limit_blocks_creation(client):
    """User at scan_limit cannot create more, but can delete and create again."""
    uid = _seed_user("limited@e.com", scan_limit=2)
    _login(client, "limited@e.com")

    # Create 2 scans — both succeed
    r1 = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert r2.status_code == 201

    # /me shows 2 used
    me = client.get("/api/v1/auth/me").json()
    assert me["scans_used"] == 2

    # Third hits 409
    r3 = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert r3.status_code == 409

    # Delete one
    client.delete(f"/api/v1/scans/{r1.json()['id']}")

    # /me shows 1 used (soft-delete excluded)
    assert client.get("/api/v1/auth/me").json()["scans_used"] == 1

    # Can create again
    r4 = client.post("/api/v1/scans", json={"search_windows": WINDOWS})
    assert r4.status_code == 201


# -----------------------------------------------------------------------------
# Scenario 5: Logout + re-login (session continuity)
# -----------------------------------------------------------------------------

def test_logout_then_login_again(client):
    """After logout, protected routes 401 until re-login."""
    _seed_user("session@e.com")
    _login(client, "session@e.com")

    # Authenticated
    assert client.get("/api/v1/auth/me").status_code == 200

    # Logout
    client.post("/api/v1/auth/logout")

    # /me now 401
    assert client.get("/api/v1/auth/me").status_code == 401

    # Login again
    _login(client, "session@e.com")
    assert client.get("/api/v1/auth/me").status_code == 200


# -----------------------------------------------------------------------------
# Scenario 6: Login with no password set (admin created user but hasn't set password yet)
# -----------------------------------------------------------------------------

def test_user_without_password_cannot_login(client):
    """User exists but admin hasn't run `update-user --password` yet — must 401."""
    with get_db(api_db.get_factory()) as db:
        user = User(email="nopass@e.com")  # no hashed_password
        db.add(user)
    resp = client.post("/api/v1/auth/login", json={"email": "nopass@e.com", "password": "anything"})
    assert resp.status_code == 401
