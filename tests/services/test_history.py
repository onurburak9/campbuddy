import pytest
from datetime import datetime, date, timezone
from db.models import Scan, ScanRun, ScanResult, ScanOutcome
from core.services.history import list_runs, list_results, stats
from core.services.exceptions import NotFound
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
    with pytest.raises(NotFound):
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
    with pytest.raises(NotFound):
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


def test_list_runs_raises_not_found_for_missing_scan(db):
    u = make_user(db)
    with pytest.raises(NotFound):
        list_runs(db, 9999, u.id)


def test_list_results_raises_not_found_for_missing_scan(db):
    u = make_user(db)
    with pytest.raises(NotFound):
        list_results(db, 9999, u.id)


def test_stats_returns_zeros_for_new_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["sites_found"] == 0
    assert result["in_cart"] == 0
    assert result["total_runs"] == 0
    assert result["success_rate"] == 0


def test_stats_counts_results_and_runs(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    _make_result(db, scan.id, run.id)
    _make_result(db, scan.id, run.id)
    result = stats(db, scan.id, u.id)
    assert result["sites_found"] == 2
    assert result["total_runs"] == 1


def test_stats_counts_in_cart(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    r1 = _make_result(db, scan.id, run.id)
    r1.cart_added = True
    r2 = _make_result(db, scan.id, run.id)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["in_cart"] == 1
    assert result["sites_found"] == 2


def test_stats_success_rate_counts_success_and_no_results(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run1 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0)
    run2 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.no_results, sites_found=0)
    run3 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.error, sites_found=0)
    run4 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.error, sites_found=0)
    db.add_all([run1, run2, run3, run4])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["total_runs"] == 4
    assert result["success_rate"] == 50


def test_stats_success_rate_rounds_to_int(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run1 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0)
    run2 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.error, sites_found=0)
    run3 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.error, sites_found=0)
    db.add_all([run1, run2, run3])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["success_rate"] == 33


def test_stats_raises_not_found_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(NotFound):
        stats(db, scan.id, u2.id)


def test_stats_raises_not_found_for_missing_scan(db):
    u = make_user(db)
    with pytest.raises(NotFound):
        stats(db, 9999, u.id)
