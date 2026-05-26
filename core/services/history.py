from db.models import ScanRun, ScanResult
from core.services.scans import get_scan


def list_runs(db, scan_id: int, user_id: int, page: int = 1, page_size: int = 20) -> list:
    get_scan(db, scan_id, user_id)
    return (
        db.query(ScanRun)
        .filter(ScanRun.scan_id == scan_id)
        .order_by(ScanRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
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
