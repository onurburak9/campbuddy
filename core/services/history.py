from datetime import datetime, timezone, timedelta
from db.models import ScanRun, ScanResult, ScanOutcome, ScanStatus
from core.services.scans import get_scan
from core.services.exceptions import NotFound


def _now():
    return datetime.now(timezone.utc)


def _filtered_runs_query(db, scan_id: int, outcome=None, started_after=None):
    q = db.query(ScanRun).filter(ScanRun.scan_id == scan_id)
    if outcome is not None:
        q = q.filter(ScanRun.outcome == outcome)
    if started_after is not None:
        q = q.filter(ScanRun.started_at >= started_after)
    return q


def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20, outcome=None, started_after=None) -> list:
    get_scan(db, scan_id, user_id)
    q = _filtered_runs_query(db, scan_id, outcome, started_after)
    return (
        q.order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def count_runs(db, scan_id: int, user_id: int, outcome=None, started_after=None) -> int:
    get_scan(db, scan_id, user_id)
    return _filtered_runs_query(db, scan_id, outcome, started_after).count()


def list_run_results(db, scan_id: int, run_id: int, user_id: int) -> list:
    get_scan(db, scan_id, user_id)
    run = (
        db.query(ScanRun)
        .filter(ScanRun.id == run_id, ScanRun.scan_id == scan_id)
        .first()
    )
    if run is None:
        raise NotFound(f"Run {run_id} not found for scan {scan_id}")
    return (
        db.query(ScanResult)
        .filter(ScanResult.scan_run_id == run_id)
        .order_by(ScanResult.first_seen_at.desc())
        .all()
    )


def list_results(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20) -> list:
    get_scan(db, scan_id, user_id)
    return (
        db.query(ScanResult)
        .filter(ScanResult.scan_id == scan_id)
        .order_by(ScanResult.first_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def stats(db, scan_id: int, user_id: int) -> dict:
    scan = get_scan(db, scan_id, user_id)
    sites_found = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).count()
    in_cart = (
        db.query(ScanResult)
        .filter(ScanResult.scan_id == scan_id, ScanResult.cart_added.is_(True))
        .count()
    )
    runs = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).all()
    total_runs = len(runs)
    if total_runs == 0:
        success_rate = 0
    else:
        successful = sum(
            1 for r in runs
            if r.outcome in (ScanOutcome.success, ScanOutcome.no_results)
        )
        success_rate = round(successful / total_runs * 100)

    if total_runs == 0:
        hit_rate = 0
    else:
        hits = sum(1 for r in runs if r.sites_found > 0)
        hit_rate = round(hits / total_runs * 100)

    latest_run = max(runs, key=lambda r: r.started_at, default=None)
    if scan.status != ScanStatus.active:
        next_run_at = None
    elif latest_run is None:
        next_run_at = _now()
    else:
        candidate = latest_run.started_at + timedelta(seconds=scan.polling_interval)
        next_run_at = max(_now(), candidate)

    finished_runs = [r for r in runs if r.finished_at is not None]
    last_finished_run = max(finished_runs, key=lambda r: r.started_at, default=None)
    last_run_duration_seconds = (
        (last_finished_run.finished_at - last_finished_run.started_at).total_seconds()
        if last_finished_run else None
    )

    return {
        "sites_found": sites_found,
        "in_cart": in_cart,
        "total_runs": total_runs,
        "success_rate": success_rate,
        "hit_rate": hit_rate,
        "next_run_at": next_run_at,
        "last_run_duration_seconds": last_run_duration_seconds,
    }
