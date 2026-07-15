from datetime import date, datetime, timezone
from db.models import Scan, ScanStatus, User
from core.services.exceptions import NotFound, Forbidden, LimitExceeded, InvalidState, ValidationFailed


def _now():
    return datetime.now(timezone.utc)


_UPDATABLE = {
    "name", "polling_interval", "rec_area_ids", "campground_ids",
    "campsite_ids", "search_windows", "nights", "days_of_week",
    "weekends_only", "notify_via_email", "notify_via_telegram",
    "notify_on_new_only", "auto_book",
}


def _require_creds_for_autobook(user, enabled: bool) -> None:
    if enabled and not (user.recreationgov_email and user.recreationgov_password):
        raise ValidationFailed(
            "auto_book requires Recreation.gov email and password on your profile"
        )


def _require_nights_fit_windows(nights: int, windows: list) -> None:
    spans = [
        (date.fromisoformat(str(w["end_date"])) - date.fromisoformat(str(w["start_date"]))).days
        for w in windows
    ]
    shortest = min(spans, default=None)
    if shortest is not None and nights > shortest:
        raise ValidationFailed(
            f"nights ({nights}) cannot exceed the shortest search window ({shortest} nights)"
        )


def list_scans(db, user_id: int) -> list:
    return (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .order_by(Scan.created_at.desc())
        .all()
    )


def get_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = db.query(Scan).filter(
        Scan.id == scan_id, Scan.user_id == user_id, Scan.deleted_at.is_(None)
    ).first()
    if not scan:
        raise NotFound(f"Scan {scan_id} not found")
    return scan


def create_scan(db, user_id: int, data: dict) -> Scan:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFound(f"User {user_id} not found")
    active_count = (
        db.query(Scan)
        .filter(Scan.user_id == user_id, Scan.deleted_at.is_(None))
        .count()
    )
    if active_count >= user.scan_limit:
        raise LimitExceeded(f"Scan limit of {user.scan_limit} reached")
    _require_creds_for_autobook(user, bool(data.get("auto_book", False)))
    _require_nights_fit_windows(data.get("nights", 1), data["search_windows"])
    scan = Scan(user_id=user_id, **data)
    db.add(scan)
    db.flush()
    return scan


def update_scan(db, scan_id: int, user_id: int, data: dict) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    effective_auto_book = data.get("auto_book", scan.auto_book)
    _require_creds_for_autobook(scan.user, bool(effective_auto_book))
    if "nights" in data or "search_windows" in data:
        effective_nights = data.get("nights", scan.nights)
        effective_windows = data.get("search_windows", scan.search_windows)
        _require_nights_fit_windows(effective_nights, effective_windows)
    for key, value in data.items():
        if key not in _UPDATABLE:
            continue
        setattr(scan, key, value)
    db.flush()
    return scan


def delete_scan(db, scan_id: int, user_id: int) -> None:
    scan = get_scan(db, scan_id, user_id)
    scan.deleted_at = _now()
    db.flush()


def pause_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    if scan.status != ScanStatus.active:
        raise InvalidState(
            f"Cannot pause scan with status '{scan.status.value}'; only active scans can be paused"
        )
    scan.status = ScanStatus.paused
    db.flush()
    return scan


def resume_scan(db, scan_id: int, user_id: int) -> Scan:
    scan = get_scan(db, scan_id, user_id)
    if scan.status != ScanStatus.paused:
        raise InvalidState(
            f"Cannot resume scan with status '{scan.status.value}'; only paused scans can be resumed"
        )
    scan.status = ScanStatus.active
    db.flush()
    return scan
