import os

os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-unit-tests-32ch")
os.environ.setdefault("ENCRYPTION_KEY", "1JeJa5uwBWlgLvtYCSfhs5v6MCccwuoxqTd03VOVEeQ=")
os.environ.setdefault("SMTP_USER", "t@e.com")
os.environ.setdefault("SMTP_PASSWORD", "pw")
os.environ.setdefault("SMTP_FROM", "t@e.com")

import pytest
from datetime import datetime, date, timezone, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from db.models import Base, User, Scan, ScanRun, ScanResult, ScanOutcome
from db.session import make_session_factory, get_db
from api.main import app
import api.database as api_db
from api.auth import hash_password

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


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


@pytest.fixture
def scan_with_runs(user_in_db):
    """Return a Scan with one recent success run, one recent no_results run, and one old run."""
    with get_db(api_db.get_factory()) as db:
        scan = Scan(user_id=user_in_db["id"], search_windows=WINDOWS)
        db.add(scan)
        db.flush()
        run_success = ScanRun(
            scan_id=scan.id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            outcome=ScanOutcome.success,
            sites_found=1,
        )
        run_no_results = ScanRun(
            scan_id=scan.id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            outcome=ScanOutcome.no_results,
            sites_found=0,
        )
        run_old = ScanRun(
            scan_id=scan.id,
            started_at=datetime.now(timezone.utc) - timedelta(days=3),
            finished_at=datetime.now(timezone.utc) - timedelta(days=3),
            outcome=ScanOutcome.success,
            sites_found=0,
        )
        db.add_all([run_success, run_no_results, run_old])
        db.flush()
        # Capture id before session closes
        class _Scan:
            pass
        s = _Scan()
        s.id = scan.id
        return s


@pytest.fixture
def scan_with_results(user_in_db):
    """Return (scan, run) where run has 2 results."""
    with get_db(api_db.get_factory()) as db:
        scan = Scan(user_id=user_in_db["id"], search_windows=WINDOWS)
        db.add(scan)
        db.flush()
        run = ScanRun(
            scan_id=scan.id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            outcome=ScanOutcome.success,
            sites_found=2,
        )
        db.add(run)
        db.flush()
        for _ in range(2):
            result = ScanResult(
                scan_run_id=run.id,
                scan_id=scan.id,
                campsite_id="1",
                facility_name="F",
                site_name="S",
                campsite_type="T",
                booking_date=date(2026, 7, 3),
                booking_end_date=date(2026, 7, 6),
                booking_url="https://example.com",
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
            )
            db.add(result)
        db.flush()

        class _Scan:
            pass

        class _Run:
            pass

        s = _Scan()
        s.id = scan.id
        r = _Run()
        r.id = run.id
        return s, r
