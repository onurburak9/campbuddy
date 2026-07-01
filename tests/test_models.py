from datetime import datetime, date, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.models import (
    Base,
    Scan,
    ScanOutcome,
    ScanResult,
    ScanRun,
    ScanStatus,
    User,
)
from db.session import (
    create_tables,
    get_db,
    make_engine,
    make_session_factory,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_scan(db: Session, user: User) -> Scan:
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
    return scan


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
    scan = _make_scan(db, user)
    db.commit()
    assert scan.id is not None
    assert scan.status == ScanStatus.active
    assert scan.nights == 1
    assert scan.provider == "RecreationDotGov"


def test_scan_run_always_writable(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    for outcome in [ScanOutcome.success, ScanOutcome.no_results, ScanOutcome.error]:
        run = ScanRun(
            scan_id=scan.id,
            started_at=_now(),
            finished_at=_now(),
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
    scan = _make_scan(db, user)
    run = ScanRun(
        scan_id=scan.id,
        started_at=_now(),
        finished_at=_now(),
        outcome=ScanOutcome.success,
        sites_found=1,
    )
    db.add(run)
    db.flush()
    now = _now()
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
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(result)
    db.commit()
    assert result.id is not None
    assert result.cart_added is False
    assert result.notified is False
    assert result.cart_added_at is None
    assert result.last_seen_at.replace(tzinfo=timezone.utc) == now
    assert result.is_available is True  # column default applied on insert


def test_user_delete_cascades_to_scans_runs_results(db):
    user = User(email="cascade@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    run = ScanRun(
        scan_id=scan.id, started_at=_now(), finished_at=_now(),
        outcome=ScanOutcome.success, sites_found=1,
    )
    db.add(run)
    db.flush()
    result = ScanResult(
        scan_run_id=run.id, scan_id=scan.id, campsite_id="1",
        facility_name="F", site_name="1", campsite_type="T",
        booking_date=date(2026, 7, 3), booking_end_date=date(2026, 7, 6),
        booking_url="u", first_seen_at=_now(), last_seen_at=_now(),
    )
    db.add(result)
    db.commit()

    db.delete(user)
    db.commit()

    assert db.query(Scan).filter_by(user_id=user.id).count() == 0
    assert db.query(ScanRun).filter_by(scan_id=scan.id).count() == 0
    assert db.query(ScanResult).filter_by(scan_id=scan.id).count() == 0


def test_session_factory_get_db_commits_on_success():
    engine = make_engine("sqlite:///:memory:")
    create_tables(engine)
    factory = make_session_factory(engine)
    with get_db(factory) as db:
        db.add(User(email="commit@example.com"))
    with get_db(factory) as db:
        assert db.query(User).filter_by(email="commit@example.com").first() is not None


def test_user_deleted_at_defaults_to_none(db):
    user = User(email="softuser@example.com")
    db.add(user)
    db.commit()
    assert user.deleted_at is None


def test_user_soft_delete_preserves_scans_runs_results(db):
    user = User(email="softcascade@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    run = ScanRun(
        scan_id=scan.id, started_at=_now(), finished_at=_now(),
        outcome=ScanOutcome.success, sites_found=1,
    )
    db.add(run)
    db.flush()
    result = ScanResult(
        scan_run_id=run.id, scan_id=scan.id, campsite_id="1",
        facility_name="F", site_name="1", campsite_type="T",
        booking_date=date(2026, 7, 3), booking_end_date=date(2026, 7, 6),
        booking_url="u", first_seen_at=_now(), last_seen_at=_now(),
    )
    db.add(result)
    db.commit()

    user.deleted_at = _now()
    db.commit()

    assert db.query(User).filter(User.id == user.id).first() is not None
    assert db.query(Scan).filter(Scan.user_id == user.id).count() == 1
    assert db.query(ScanRun).filter(ScanRun.scan_id == scan.id).count() == 1
    assert db.query(ScanResult).filter(ScanResult.scan_id == scan.id).count() == 1
    assert db.query(User).filter(User.deleted_at.is_(None)).count() == 0


def test_scan_name_is_optional(db):
    user = User(email="name@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    db.commit()
    assert scan.name is None
    scan.name = "Yosemite July"
    db.commit()
    assert scan.name == "Yosemite July"


def test_scan_soft_delete_preserves_history(db):
    user = User(email="soft@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    run = ScanRun(
        scan_id=scan.id, started_at=_now(), finished_at=_now(),
        outcome=ScanOutcome.success, sites_found=1,
    )
    db.add(run)
    db.flush()
    result = ScanResult(
        scan_run_id=run.id, scan_id=scan.id, campsite_id="1",
        facility_name="F", site_name="1", campsite_type="T",
        booking_date=date(2026, 7, 3), booking_end_date=date(2026, 7, 6),
        booking_url="u", first_seen_at=_now(), last_seen_at=_now(),
    )
    db.add(result)
    db.commit()

    scan.deleted_at = _now()
    db.commit()

    assert db.query(Scan).filter(Scan.id == scan.id).first() is not None
    assert db.query(ScanRun).filter(ScanRun.scan_id == scan.id).count() == 1
    assert db.query(ScanResult).filter(ScanResult.scan_id == scan.id).count() == 1
    assert db.query(Scan).filter(Scan.deleted_at.is_(None)).count() == 0


def test_session_factory_get_db_rolls_back_on_exception():
    engine = make_engine("sqlite:///:memory:")
    create_tables(engine)
    factory = make_session_factory(engine)
    with pytest.raises(RuntimeError):
        with get_db(factory) as db:
            db.add(User(email="rollback@example.com"))
            db.flush()
            raise RuntimeError("simulated failure")
    with get_db(factory) as db:
        assert db.query(User).filter_by(email="rollback@example.com").first() is None


def test_user_has_hashed_password_and_scan_limit(db):
    user = User(email="authuser@example.com", hashed_password="somehash", scan_limit=3)
    db.add(user)
    db.commit()
    assert user.hashed_password == "somehash"
    assert user.scan_limit == 3


def test_user_scan_limit_defaults_to_five(db):
    user = User(email="defaultlimit@example.com")
    db.add(user)
    db.commit()
    assert user.scan_limit == 5


def test_user_hashed_password_nullable(db):
    user = User(email="nopassword@example.com")
    db.add(user)
    db.commit()
    assert user.hashed_password is None
