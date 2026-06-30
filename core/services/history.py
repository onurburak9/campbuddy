from db.models import ScanRun, ScanResult, ScanOutcome
from core.services.scans import get_scan
from core.services.exceptions import NotFound


def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20, outcome=None) -> list:
    get_scan(db, scan_id, user_id)
    q = db.query(ScanRun).filter(ScanRun.scan_id == scan_id)
    if outcome is not None:
        q = q.filter(ScanRun.outcome == outcome)
    return (
        q.order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


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
    get_scan(db, scan_id, user_id)
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
    return {
        "sites_found": sites_found,
        "in_cart": in_cart,
        "total_runs": total_runs,
        "success_rate": success_rate,
    }
