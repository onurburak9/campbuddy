import os

os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-unit-tests-32ch")
os.environ.setdefault("ENCRYPTION_KEY", "1JeJa5uwBWlgLvtYCSfhs5v6MCccwuoxqTd03VOVEeQ=")
os.environ.setdefault("SMTP_USER", "t@e.com")
os.environ.setdefault("SMTP_PASSWORD", "pw")
os.environ.setdefault("SMTP_FROM", "t@e.com")

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from db.models import Base, User
from db.session import make_session_factory, get_db
from api.main import app
import api.database as api_db
from api.auth import hash_password


@pytest.fixture(autouse=True)
def setup_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    api_db._factory = make_session_factory(engine)
    # Prevent lifespan from overwriting our in-memory factory
    with patch("api.database.init", lambda *a, **kw: None):
        yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def user_in_db():
    with get_db(api_db.get_factory()) as db:
        user = User(
            email="user@example.com",
            hashed_password=hash_password("password123"),
            scan_limit=5,
        )
        db.add(user)
        db.flush()
        return {"id": user.id, "email": user.email}


@pytest.fixture
def auth_client(client, user_in_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    return client, user_in_db
