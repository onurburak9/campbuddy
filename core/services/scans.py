from datetime import datetime, timezone
from db.models import Scan, ScanStatus, User
from core.services.exceptions import NotFound, Forbidden, LimitExceeded


def _now():
    return datetime.now(timezone.utc)


def list_scans(db, user_id: int) -> list:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .order_by(Scan.created_at.desc())
        .all()
    )


def get_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.deleted_at.is_(None)).first()
    if not scan:
        raise NotFound(f"Scan {scan_id} not found")
    if scan.user_id != user_id:
        raise Forbidden(f"Scan {scan_id} belongs to another user")
    return scan


def create_scan(db, user_id: int, data: dict) -> Scan:
    user = db.query(User).filter(User.id == user_id).first()
    active_count = (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )
    if active_count >= user.scan_limit:
        raise LimitExceeded(f"Scan limit of {user.scan_limit} reached")
    scan = Scan(user_id=user_id, **data)
    db.add(scan)
    db.flush()
    return scan


def update_scan(db, scan_id: int, user_id: int, data: dict) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    for key, value in data.items():
        setattr(scan, key, value)
    db.flush()
    return scan


def delete_scan(db, scan_id: int, user_id: int) -> None:
    scan = get_scan(db, scan_id, user_id)
    scan.deleted_at = _now()
    db.flush()


def pause_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    scan.status = ScanStatus.paused
    db.flush()
    return scan


def resume_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    scan.status = ScanStatus.active
    db.flush()
    return scan
