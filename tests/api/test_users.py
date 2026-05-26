from db.models import User
from db.session import get_db
import api.database as api_db
from api.auth import hash_password


def test_patch_profile_updates_email(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"email": "updated@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "updated@example.com"


def test_patch_profile_updates_telegram(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"telegram_chat_id": "999888"})
    assert resp.status_code == 200
    assert resp.json()["telegram_chat_id"] == "999888"


def test_patch_profile_encrypts_recreationgov_password(auth_client):
    client, _ = auth_client
    resp = client.patch("/api/v1/users/me", json={"recreationgov_password": "s3cr3t"})
    assert resp.status_code == 200
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.email == "user@example.com").first()
        assert user.recreationgov_password is not None
        assert user.recreationgov_password != "s3cr3t"


def test_patch_profile_requires_auth(client):
    resp = client.patch("/api/v1/users/me", json={"email": "x@e.com"})
    assert resp.status_code == 401


def test_patch_profile_does_not_expose_password_in_response(auth_client):
    """Defensive: response must NOT include recreationgov_password or hashed_password."""
    client, _ = auth_client
    client.patch("/api/v1/users/me", json={"recreationgov_password": "secret"})
    resp = client.patch("/api/v1/users/me", json={"email": "user@example.com"})
    body = resp.json()
    assert "recreationgov_password" not in body
    assert "hashed_password" not in body


def test_patch_profile_ignores_scan_limit(auth_client):
    """scan_limit is admin-only, must not be writable via API."""
    client, info = auth_client
    resp = client.patch("/api/v1/users/me", json={"scan_limit": 999, "email": "new@e.com"})
    assert resp.status_code == 200
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == info["id"]).first()
        assert user.scan_limit == 5


def test_patch_profile_returns_404_when_service_raises_notfound(auth_client, monkeypatch):
    """Defensive: if update_profile raises NotFound (unreachable today due to
    get_current_user filtering, but a future hard-delete codepath would trigger it),
    the route returns 404, not 500."""
    from core.services.exceptions import NotFound
    from api.routes import users as users_route
    client, _ = auth_client
    monkeypatch.setattr(
        users_route,
        "update_profile",
        lambda *a, **kw: (_ for _ in ()).throw(NotFound("forced for test")),
    )
    resp = client.patch("/api/v1/users/me", json={"email": "x@e.com"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_patch_profile_duplicate_email_returns_409(auth_client):
    """Changing email to one already in use must return 409, not 500."""
    client, _ = auth_client
    with get_db(api_db.get_factory()) as db:
        other = User(email="taken@e.com", hashed_password=hash_password("pw"), scan_limit=5)
        db.add(other)
    resp = client.patch("/api/v1/users/me", json={"email": "taken@e.com"})
    assert resp.status_code == 409
    assert "already in use" in resp.json()["detail"]
