import pytest
from datetime import datetime, date, timezone
from db.models import Scan, ScanRun, ScanResult, ScanOutcome
from core.services.history import list_runs, list_results
from core.services.exceptions import Forbidden
from tests.services.conftest import make_user

WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def _make_run(db, scan_id):
    run = ScanRun(
        scan_id=scan_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        outcome=ScanOutcome.success,
        sites_found=1,
    )
    db.add(run)
    db.flush()
    return run


def _make_result(db, scan_id, run_id):
    r = ScanResult(
        scan_run_id=run_id,
        scan_id=scan_id,
        campsite_id="1",
        facility_name="F",
        site_name="S",
        campsite_type="T",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://example.com",
        first_seen_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.flush()
    return r


def test_list_runs_returns_runs_for_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    _make_run(db, scan.id)
    _make_run(db, scan.id)
    runs = list_runs(db, scan.id, u.id, page=1, page_size=10)
    assert len(runs) == 2


def test_list_runs_raises_forbidden_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(Forbidden):
        list_runs(db, scan.id, u2.id)


def test_list_runs_paginates(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    for _ in range(5):
        _make_run(db, scan.id)
    page1 = list_runs(db, scan.id, u.id, page=1, page_size=3)
    page2 = list_runs(db, scan.id, u.id, page=2, page_size=3)
    assert len(page1) == 3
    assert len(page2) == 2


def test_list_results_returns_results_for_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    _make_result(db, scan.id, run.id)
    results = list_results(db, scan.id, u.id, page=1, page_size=10)
    assert len(results) == 1


def test_list_results_raises_forbidden_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(Forbidden):
        list_results(db, scan.id, u2.id)


def test_list_results_paginates(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    for i in range(5):
        _make_result(db, scan.id, run.id)
    page1 = list_results(db, scan.id, u.id, page=1, page_size=3)
    page2 = list_results(db, scan.id, u.id, page=2, page_size=3)
    assert len(page1) == 3
    assert len(page2) == 2
