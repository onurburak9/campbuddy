import pytest
from datetime import datetime, date, timezone, timedelta
from db.models import Scan, ScanRun, ScanResult, ScanOutcome
from core.services.history import list_runs, list_results, stats, count_runs
from core.services import history as history_svc
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
        last_seen_at=datetime.now(timezone.utc),
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


def test_count_runs_matches_total_regardless_of_page_size(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    for _ in range(5):
        _make_run(db, scan.id)
    assert count_runs(db, scan.id, u.id) == 5
    page = list_runs(db, scan.id, u.id, page=1, page_size=3)
    assert len(page) == 3


def test_count_runs_respects_outcome_filter(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    _make_run(db, scan.id)
    error_run = ScanRun(
        scan_id=scan.id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        outcome=ScanOutcome.error,
        sites_found=0,
    )
    db.add(error_run)
    db.flush()
    assert count_runs(db, scan.id, u.id, outcome=ScanOutcome.success) == 1
    assert count_runs(db, scan.id, u.id) == 2


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
    assert result["hit_rate"] == 0


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


def test_stats_hit_rate_counts_runs_with_sites_found_regardless_of_outcome(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    # Two runs found sites (one "success", one "error" that still recorded finds
    # before failing); two runs found nothing.
    run1 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=3)
    run2 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.error, sites_found=1)
    run3 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=0)
    run4 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.no_results, sites_found=0)
    db.add_all([run1, run2, run3, run4])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["total_runs"] == 4
    assert result["hit_rate"] == 50


def test_stats_hit_rate_rounds_to_int(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run1 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.success, sites_found=1)
    run2 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.no_results, sites_found=0)
    run3 = ScanRun(scan_id=scan.id, started_at=datetime.now(timezone.utc), outcome=ScanOutcome.no_results, sites_found=0)
    db.add_all([run1, run2, run3])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["hit_rate"] == 33


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


# ---------------------------------------------------------------------------
# Fixtures for outcome-filter and per-run-results tests
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    # one success run, one no_results run
    run1 = ScanRun(
        scan_id=scan.id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        outcome=ScanOutcome.success,
        sites_found=1,
    )
    run2 = ScanRun(
        scan_id=scan.id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        outcome=ScanOutcome.no_results,
        sites_found=0,
    )
    db.add_all([run1, run2])
    db.flush()
    scan.user_id = u.id  # expose user_id for test assertions
    return scan


@pytest.fixture
def seeded_scan_with_results(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    run = _make_run(db, scan.id)
    _make_result(db, scan.id, run.id)
    _make_result(db, scan.id, run.id)
    other_run = _make_run(db, scan.id)
    _make_result(db, scan.id, other_run.id)
    return scan, run, other_run


# ---------------------------------------------------------------------------
# New tests: outcome filter and per-run results
# ---------------------------------------------------------------------------

def test_list_runs_filters_by_outcome(db, seeded_scan):
    success = history_svc.list_runs(db, seeded_scan.id, seeded_scan.user_id, outcome="success")
    assert all(r.outcome.value == "success" for r in success)
    all_runs = history_svc.list_runs(db, seeded_scan.id, seeded_scan.user_id)
    assert len(all_runs) >= len(success)


def test_list_run_results_returns_only_that_runs_sites(db, seeded_scan_with_results):
    scan, run, other_run = seeded_scan_with_results
    rows = history_svc.list_run_results(db, scan.id, run.id, scan.user_id)
    assert {r.scan_run_id for r in rows} == {run.id}
    assert len(rows) == 2


def test_list_run_results_unknown_run_raises(db, seeded_scan):
    with pytest.raises(NotFound):
        history_svc.list_run_results(db, seeded_scan.id, 999999, seeded_scan.user_id)


# ---------------------------------------------------------------------------
# Fixture and test for started_after filter
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_scan_with_runs(db):
    u = make_user(db, "runs@e.com")
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    # one old run (3 days ago) and one recent run (1 hour ago)
    old_run = ScanRun(
        scan_id=scan.id,
        started_at=datetime.now(timezone.utc) - timedelta(days=3),
        finished_at=datetime.now(timezone.utc) - timedelta(days=3),
        outcome=ScanOutcome.success,
        sites_found=0,
    )
    recent_run = ScanRun(
        scan_id=scan.id,
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
        outcome=ScanOutcome.no_results,
        sites_found=0,
    )
    db.add_all([old_run, recent_run])
    db.flush()
    scan.user_id = u.id
    return scan


def test_list_runs_filters_by_started_after(db, seeded_scan_with_runs):
    scan = seeded_scan_with_runs  # has runs across a range of started_at
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recent = history_svc.list_runs(db, scan.id, scan.user_id, started_after=cutoff)
    assert all(r.started_at >= cutoff for r in recent)
    all_runs = history_svc.list_runs(db, scan.id, scan.user_id)
    assert len(recent) <= len(all_runs)


# ---------------------------------------------------------------------------
# New tests: next_run_at and last_run_duration_seconds
# ---------------------------------------------------------------------------

def test_stats_next_run_at_none_for_paused_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status="paused")
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["next_run_at"] is None


def test_stats_next_run_at_now_for_never_run_active_scan(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["next_run_at"] is not None
    assert abs((result["next_run_at"] - datetime.now(timezone.utc)).total_seconds()) < 5


def test_stats_next_run_at_clamped_to_now_when_overdue(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, polling_interval=300)
    db.add(scan)
    db.flush()
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(ScanRun(
        scan_id=scan.id, started_at=started, finished_at=started + timedelta(seconds=5),
        outcome=ScanOutcome.success, sites_found=0,
    ))
    db.flush()
    result = stats(db, scan.id, u.id)
    # last run was an hour ago with a 300s interval — the "real" next fire is long past, clamp to now
    assert abs((result["next_run_at"] - datetime.now(timezone.utc)).total_seconds()) < 5


def test_stats_next_run_at_in_the_future_when_recently_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, polling_interval=300)
    db.add(scan)
    db.flush()
    started = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.add(ScanRun(
        scan_id=scan.id, started_at=started, finished_at=started + timedelta(seconds=2),
        outcome=ScanOutcome.success, sites_found=0,
    ))
    db.flush()
    result = stats(db, scan.id, u.id)
    expected = started + timedelta(seconds=300)
    assert abs((result["next_run_at"] - expected).total_seconds()) < 2


def test_stats_last_run_duration_seconds_none_when_no_finished_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["last_run_duration_seconds"] is None


def test_stats_last_run_duration_seconds_from_most_recently_started_finished_run(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    older_start = datetime.now(timezone.utc) - timedelta(hours=1)
    newer_start = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.add_all([
        ScanRun(scan_id=scan.id, started_at=older_start, finished_at=older_start + timedelta(seconds=20),
                outcome=ScanOutcome.success, sites_found=0),
        ScanRun(scan_id=scan.id, started_at=newer_start, finished_at=newer_start + timedelta(seconds=7),
                outcome=ScanOutcome.success, sites_found=0),
    ])
    db.flush()
    result = stats(db, scan.id, u.id)
    assert result["last_run_duration_seconds"] == 7
