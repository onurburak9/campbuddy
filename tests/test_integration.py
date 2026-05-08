"""End-to-end: real SQLite, all external I/O mocked."""
import pytest
from datetime import datetime, date, timezone
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet
from db.models import Base, User, Scan, ScanRun, ScanResult
from core.runner import run_scan
from core.crypto import encrypt_password


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def settings(fernet_key):
    s = MagicMock()
    s.encryption_key = fernet_key
    s.playwright_service_url = "http://playwright:8001"
    return s


def seed(factory, fernet_key):
    with factory() as db:
        user = User(
            email="test@example.com",
            recreationgov_email="rg@example.com",
            recreationgov_password=encrypt_password("secret123", fernet_key),
        )
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            rec_area_ids=[1076],
            nights=3,
            polling_interval=300,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status="active",
        )
        db.add(scan)
        db.commit()
        return scan.id


def make_site():
    s = MagicMock()
    s.campsite_id = "10357088"
    s.facility_name = "Union West"
    s.campsite_site_name = "1"
    s.campsite_type = "STANDARD NONELECTRIC"
    s.booking_date = datetime(2026, 7, 3)
    s.booking_end_date = datetime(2026, 7, 6)
    s.booking_url = "https://www.recreation.gov/camping/campsites/10357088"
    s.booking_nights = 3
    return s


def test_full_scan_cycle(factory, settings, fernet_key, mocker):
    scan_id = seed(factory, fernet_key)
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mocker.patch("core.runner.notify")

    run_scan(scan_id, factory, settings)

    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "success"
        assert run.sites_found == 1
        assert run.finished_at is not None

        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.campsite_id == "10357088"
        assert result.cart_added is True
        assert result.notified is True
        assert result.booking_url == "https://www.recreation.gov/camping/campsites/10357088"


def test_full_scan_error_still_writes_run(factory, settings, fernet_key, mocker):
    scan_id = seed(factory, fernet_key)
    mocker.patch("core.runner.check_availability", side_effect=Exception("network error"))

    run_scan(scan_id, factory, settings)

    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "error"
        assert "network error" in run.error_message
        assert run.finished_at is not None
        assert db.query(ScanResult).filter(ScanResult.scan_id == scan_id).count() == 0
