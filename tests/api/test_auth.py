import pytest
from db.models import User
import api.database as api_db
from db.session import get_db
from api.auth import hash_password


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


def test_logout_clears_cookie(client, user_in_db):
    client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200


def test_me_returns_user_info(auth_client):
    client, user_info = auth_client
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["scan_limit"] == 5
    assert data["scans_used"] == 0


def test_me_returns_401_without_cookie(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
