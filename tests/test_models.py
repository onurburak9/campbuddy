import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Base, User, Scan, ScanRun, ScanResult


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_user_created_with_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.created_at is not None
    assert user.telegram_chat_id is None


def test_scan_created_with_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.commit()
    assert scan.id is not None
    assert scan.status == "active"
    assert scan.nights == 1
    assert scan.provider == "RecreationDotGov"


def test_scan_run_always_writable(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.flush()
    for outcome in ["success", "no_results", "error"]:
        run = ScanRun(
            scan_id=scan.id,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            outcome=outcome,
            sites_found=0,
        )
        db.add(run)
    db.commit()
    runs = db.query(ScanRun).filter(ScanRun.scan_id == scan.id).all()
    assert len(runs) == 3


def test_scan_result_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = Scan(
        user_id=user.id,
        search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
        polling_interval=300,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
    )
    db.add(scan)
    db.flush()
    run = ScanRun(
        scan_id=scan.id,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        outcome="success",
        sites_found=1,
    )
    db.add(run)
    db.flush()
    result = ScanResult(
        scan_run_id=run.id,
        scan_id=scan.id,
        campsite_id="10357088",
        facility_name="Union West",
        site_name="1",
        campsite_type="STANDARD NONELECTRIC",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://www.recreation.gov/camping/campsites/10357088",
        first_seen_at=datetime.utcnow(),
    )
    db.add(result)
    db.commit()
    assert result.id is not None
    assert result.cart_added is False
    assert result.notified is False
    assert result.cart_added_at is None


def test_session_factory_get_db():
    from db.session import make_engine, create_tables, make_session_factory, get_db
    engine = make_engine("sqlite:///:memory:")
    create_tables(engine)
    factory = make_session_factory(engine)
    with get_db(factory) as db:
        user = User(email="session_test@example.com")
        db.add(user)
    with get_db(factory) as db:
        found = db.query(User).filter(User.email == "session_test@example.com").first()
        assert found is not None
