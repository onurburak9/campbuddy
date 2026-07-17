import pytest
from datetime import datetime, timedelta, timezone
from db.models import User, PasswordResetToken
import api.database as api_db
from db.session import get_db
from api.auth import hash_password, COOKIE_NAME, ALGORITHM
from jose import jwt
from core.services.users import create_password_reset_token


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


def test_register_creates_user_and_sets_cookie(client):
    resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies
    with get_db(api_db.get_factory()) as db:
        user = db.query(User).filter(User.email == "brand-new@e.com").first()
        assert user is not None
        assert user.scan_limit == 5


def test_register_then_me_returns_new_user(client):
    client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "brand-new@e.com"


def test_register_duplicate_email_returns_409(client, user_in_db):
    resp = client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "longenough"})
    assert resp.status_code == 409


def test_register_short_password_returns_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "short"})
    assert resp.status_code == 422


def test_register_malformed_email_returns_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "longenough"})
    assert resp.status_code == 422


def test_register_email_with_trailing_newline_returns_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "a@b.c\n", "password": "longenough"})
    assert resp.status_code == 422


def test_register_disabled_returns_403(client, monkeypatch):
    from config.settings import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    try:
        resp = client.post("/api/v1/auth/register", json={"email": "brand-new@e.com", "password": "longenough"})
        assert resp.status_code == 403
    finally:
        get_settings.cache_clear()


def test_forgot_password_returns_ok_for_known_email(client, user_in_db, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_send.assert_called_once()


def test_forgot_password_returns_ok_for_unknown_email_without_sending(client, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_send.assert_not_called()


def test_forgot_password_creates_reset_token_for_known_email(client, user_in_db, mocker):
    mocker.patch("api.routes.auth.send_password_reset_email")
    client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    with get_db(api_db.get_factory()) as db:
        token = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_in_db["id"]).first()
        assert token is not None
        assert token.used_at is None


def test_forgot_password_reset_url_contains_token_and_base_url(client, user_in_db, mocker):
    mock_send = mocker.patch("api.routes.auth.send_password_reset_email")
    client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    to, reset_url, _settings = mock_send.call_args[0]
    assert to == "user@example.com"
    assert reset_url.startswith("http://localhost:5173/reset-password?token=")


def test_forgot_password_malformed_email_returns_422(client):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_forgot_password_email_send_failure_still_returns_ok(client, user_in_db, mocker):
    mocker.patch("api.routes.auth.send_password_reset_email", side_effect=Exception("smtp down"))
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_reset_password_sets_cookie_and_updates_password(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "newlongpassword"})
    assert resp.status_code == 200
    assert "campbuddy_session" in resp.cookies
    login_resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "newlongpassword"})
    assert login_resp.status_code == 200


def test_reset_password_old_password_no_longer_works(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    client.post("/api/v1/auth/reset-password", json={"token": token, "password": "newlongpassword"})
    resp = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_reset_password_invalid_token_returns_400(client):
    resp = client.post("/api/v1/auth/reset-password", json={"token": "bogus", "password": "newlongpassword"})
    assert resp.status_code == 400


def test_reset_password_reused_token_returns_400(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    client.post("/api/v1/auth/reset-password", json={"token": token, "password": "firstnewpw"})
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "secondnewpw"})
    assert resp.status_code == 400


def test_reset_password_short_password_returns_422(client, user_in_db):
    with get_db(api_db.get_factory()) as db:
        token = create_password_reset_token(db, "user@example.com")
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "short"})
    assert resp.status_code == 422
