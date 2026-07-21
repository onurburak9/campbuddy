import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Scan
from core.scheduler import sync_jobs


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def add_scan(factory, status="active", interval=300):
    with factory() as db:
        user = User(email="t@e.com")
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            rec_area_ids=[1076],
            nights=1,
            polling_interval=interval,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status=status,
        )
        db.add(scan)
        db.commit()
        return scan.id


def test_sync_adds_active_scan(factory):
    scan_id = add_scan(factory, status="active", interval=300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.add_job.assert_called_once()
    assert scheduler.add_job.call_args[1]["id"] == f"scan_{scan_id}"
    trigger = scheduler.add_job.call_args[1]["trigger"]
    assert trigger.interval.total_seconds() == 300


def test_sync_skips_paused_scan(factory):
    add_scan(factory, status="paused")
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.add_job.assert_not_called()


def test_sync_skips_deleted_scan(factory):
    from datetime import datetime, timezone
    scan_id = add_scan(factory, status="active", interval=300)
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update(
            {"deleted_at": datetime.now(timezone.utc)}
        )
        db.commit()
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.add_job.assert_not_called()


def test_sync_removes_stale_job(factory):
    add_scan(factory, status="active")
    stale_job = MagicMock()
    stale_job.id = "scan_9999"
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [stale_job]
    sync_jobs(scheduler, factory, MagicMock())
    scheduler.remove_job.assert_called_once_with("scan_9999")


def test_sync_sets_immediate_next_run_time_for_never_run_scan(factory):
    scan_id = add_scan(factory, status="active", interval=300)
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    kwargs = scheduler.add_job.call_args[1]
    assert kwargs["id"] == f"scan_{scan_id}"
    assert "next_run_time" in kwargs
    assert kwargs["next_run_time"] is not None


def test_sync_does_not_set_next_run_time_for_scan_with_run_history(factory):
    from datetime import datetime, timezone
    from db.models import ScanRun, ScanOutcome
    scan_id = add_scan(factory, status="active", interval=300)
    with factory() as db:
        db.add(ScanRun(
            scan_id=scan_id, started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0,
        ))
        db.commit()
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    sync_jobs(scheduler, factory, MagicMock())
    kwargs = scheduler.add_job.call_args[1]
    assert "next_run_time" not in kwargs


def test_start_scheduler_syncs_every_30_seconds(factory):
    from core.scheduler import start_scheduler
    scheduler = start_scheduler(factory, MagicMock())
    try:
        job = scheduler.get_job("__sync_jobs__")
        assert job.trigger.interval.total_seconds() == 30
    finally:
        scheduler.shutdown(wait=False)
