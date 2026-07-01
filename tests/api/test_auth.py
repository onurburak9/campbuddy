import pytest
from datetime import datetime, timedelta, timezone
from db.models import User
import api.database as api_db
from db.session import get_db
from api.auth import hash_password, COOKIE_NAME, ALGORITHM
from jose import jwt


def test_login_sets_cookie(client, user_in_db):
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies


def test_login_wrong_password_returns_401(client, user_in_db):
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "pw"})
    assert resp.status_code == 401


def test_login_user_with_no_password_returns_401(client):
    with get_db(api_db.get_factory()) as db:
        user = User(email="nopass@example.com")
        db.add(user)
    resp = client.post("/api/v1/auth/login", json={"email": "nopass@example.com", "password": "anything"})
    assert resp.status_code == 401


def test_login_empty_password_returns_422(client, user_in_db):
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": ""})
    assert resp.status_code == 422


def test_logout_clears_cookie(client, user_in_db):
    client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert "campbuddy_session" in client.cookies
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert "campbuddy_session" not in client.cookies


def test_me_returns_user_info(auth_client):
    client, user_info = auth_client
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["scan_limit"] == 5
    assert data["scans_used"] == 0
    assert data["has_telegram"] is False


def test_me_has_telegram_true_when_telegram_chat_id_set(auth_client):
    client, info = auth_client
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == info["id"]).first()
        user.telegram_chat_id = "123456789"
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["has_telegram"] is True


def test_me_has_telegram_false_when_telegram_chat_id_empty_string(auth_client):
    client, info = auth_client
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == info["id"]).first()
        user.telegram_chat_id = ""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["has_telegram"] is False


def test_me_returns_401_without_cookie(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_login_unknown_email_runs_password_check(client):
    """Defensive: unknown emails should still go through password verification to avoid timing oracle."""
    import time
    # warm up
    client.post("/api/v1/auth/login", json={"email": "x@e.com", "password": "p"})
    start = time.perf_counter()
    resp = client.post("/api/v1/auth/login", json={"email": "still-unknown@e.com", "password": "anything"})
    elapsed = time.perf_counter() - start
    assert resp.status_code == 401
    # bcrypt verify is intentionally slow (~50ms+). If <5ms, we're short-circuiting and leaking timing.
    assert elapsed > 0.005, f"Login was too fast ({elapsed*1000:.1f}ms) — possible timing leak"


def test_expired_jwt_returns_401(client, user_in_db):
    """A token with exp in the past must be rejected."""
    from config.settings import get_settings
    settings = get_settings()
    expired_token = jwt.encode(
        {"sub": str(user_in_db["id"]), "exp": datetime.now(timezone.utc) - timedelta(hours=1), "iat": datetime.now(timezone.utc)},
        settings.api_secret_key,
        algorithm=ALGORITHM,
    )
    client.cookies.set(COOKIE_NAME, expired_token)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_malformed_jwt_returns_401(client):
    """Garbage cookie value must return 401, not 500."""
    client.cookies.set(COOKIE_NAME, "not-a-jwt")
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_tampered_jwt_returns_401(client, user_in_db):
    """A token signed with the wrong key must be rejected."""
    tampered_token = jwt.encode(
        {"sub": str(user_in_db["id"]), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-secret-key",
        algorithm=ALGORITHM,
    )
    client.cookies.set(COOKIE_NAME, tampered_token)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_soft_deleted_user_with_valid_jwt_returns_401(client, user_in_db):
    """A valid token for a soft-deleted user must be rejected."""
    client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.id == user_in_db["id"]).first()
        user.deleted_at = datetime.now(timezone.utc)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
