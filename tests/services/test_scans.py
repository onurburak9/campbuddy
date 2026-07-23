import pytest
from datetime import datetime, timezone
from db.models import Scan, ScanStatus
from core.services import scans as scans_svc
from core.services.scans import (
    list_scans,
    get_scan,
    create_scan,
    update_scan,
    delete_scan,
    pause_scan,
    resume_scan,
)
from core.services.exceptions import NotFound, Forbidden, LimitExceeded, InvalidState, ValidationFailed
from tests.services.conftest import make_user


WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def test_list_scans_returns_only_owners_scans(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    assert len(list_scans(db, u1.id)) == 1
    assert len(list_scans(db, u2.id)) == 0


def test_list_scans_excludes_soft_deleted(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    scan.deleted_at = datetime.now(timezone.utc)
    db.flush()
    assert list_scans(db, u.id) == []


def test_get_scan_raises_not_found_for_missing(db):
    u = make_user(db)
    with pytest.raises(NotFound):
        get_scan(db, 9999, u.id)


def test_get_scan_raises_not_found_for_wrong_owner(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    with pytest.raises(NotFound):
        get_scan(db, scan.id, u2.id)


def test_get_scan_raises_not_found_for_soft_deleted(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    scan.deleted_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(NotFound):
        get_scan(db, scan.id, u.id)


def test_create_scan_returns_scan(db):
    u = make_user(db, scan_limit=5)
    data = {"search_windows": WINDOWS, "nights": 2}
    scan = create_scan(db, u.id, data)
    assert scan.id is not None
    assert scan.user_id == u.id
    assert scan.nights == 2


def test_create_scan_raises_limit_exceeded(db):
    u = make_user(db, scan_limit=2)
    for _ in range(2):
        s = Scan(user_id=u.id, search_windows=WINDOWS)
        db.add(s)
    db.flush()
    with pytest.raises(LimitExceeded):
        create_scan(db, u.id, {"search_windows": WINDOWS})


def test_create_scan_raises_not_found_for_missing_user(db):
    with pytest.raises(NotFound):
        create_scan(db, 9999, {"search_windows": WINDOWS})


def test_create_scan_soft_deleted_not_counted_against_limit(db):
    u = make_user(db, scan_limit=1)
    s = Scan(user_id=u.id, search_windows=WINDOWS,
             deleted_at=datetime.now(timezone.utc))
    db.add(s)
    db.flush()
    scan = create_scan(db, u.id, {"search_windows": WINDOWS})
    assert scan.id is not None


def test_update_scan_changes_fields(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, nights=1)
    db.add(scan)
    db.flush()
    updated = update_scan(db, scan.id, u.id, {"nights": 3, "name": "Yosemite"})
    assert updated.nights == 3
    assert updated.name == "Yosemite"


def test_update_scan_ignores_disallowed_fields(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    original_user_id = scan.user_id
    update_scan(db, scan.id, u.id, {"user_id": 9999, "deleted_at": None, "status": "completed"})
    assert scan.user_id == original_user_id
    assert scan.deleted_at is None
    assert scan.status == ScanStatus.active


def test_delete_scan_soft_deletes(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    delete_scan(db, scan.id, u.id)
    db.flush()
    assert scan.deleted_at is not None


def test_pause_scan_sets_status(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.active)
    db.add(scan)
    db.flush()
    result = pause_scan(db, scan.id, u.id)
    assert result.status == ScanStatus.paused


def test_pause_already_paused_raises_invalid_state(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.paused)
    db.add(scan)
    db.flush()
    with pytest.raises(InvalidState):
        pause_scan(db, scan.id, u.id)


def test_pause_completed_scan_raises_invalid_state(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.completed)
    db.add(scan)
    db.flush()
    with pytest.raises(InvalidState):
        pause_scan(db, scan.id, u.id)


def test_resume_scan_sets_status(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.paused)
    db.add(scan)
    db.flush()
    result = resume_scan(db, scan.id, u.id)
    assert result.status == ScanStatus.active


def test_resume_active_scan_raises_invalid_state(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.active)
    db.add(scan)
    db.flush()
    with pytest.raises(InvalidState):
        resume_scan(db, scan.id, u.id)


def test_resume_completed_scan_raises_invalid_state(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.completed)
    db.add(scan)
    db.flush()
    with pytest.raises(InvalidState):
        resume_scan(db, scan.id, u.id)


def test_create_scan_autobook_without_creds_rejected(db):
    u = make_user(db)  # no rec.gov creds
    with pytest.raises(ValidationFailed):
        scans_svc.create_scan(db, u.id, {"search_windows": WINDOWS, "auto_book": True})


def test_create_scan_autobook_with_creds_ok(db):
    u = make_user(db)
    u.recreationgov_email = "rg@e.com"
    u.recreationgov_password = "enc"
    db.flush()
    scan = scans_svc.create_scan(db, u.id, {"search_windows": WINDOWS, "auto_book": True})
    assert scan.auto_book is True


def test_update_scan_enable_autobook_without_creds_rejected(db):
    u = make_user(db)
    scan = scans_svc.create_scan(db, u.id, {"search_windows": WINDOWS})
    with pytest.raises(ValidationFailed):
        scans_svc.update_scan(db, scan.id, u.id, {"auto_book": True})


def test_create_scan_rejects_nights_longer_than_window(db):
    u = make_user(db)
    with pytest.raises(ValidationFailed):
        create_scan(db, u.id, {"search_windows": WINDOWS, "nights": 10})


def test_create_scan_rejects_nights_longer_than_shortest_of_multiple_windows(db):
    u = make_user(db)
    windows = [
        {"start_date": "2026-07-03", "end_date": "2026-07-10"},  # 7 nights
        {"start_date": "2026-08-01", "end_date": "2026-08-03"},  # 2 nights
    ]
    with pytest.raises(ValidationFailed):
        create_scan(db, u.id, {"search_windows": windows, "nights": 3})


def test_create_scan_allows_nights_equal_to_window(db):
    u = make_user(db)
    scan = create_scan(db, u.id, {"search_windows": WINDOWS, "nights": 3})
    assert scan.nights == 3


def test_update_scan_rejects_nights_longer_than_existing_window(db):
    u = make_user(db)
    scan = create_scan(db, u.id, {"search_windows": WINDOWS, "nights": 1})
    with pytest.raises(ValidationFailed):
        update_scan(db, scan.id, u.id, {"nights": 10})


def test_update_scan_rejects_new_window_shorter_than_existing_nights(db):
    u = make_user(db)
    scan = create_scan(db, u.id, {"search_windows": WINDOWS, "nights": 3})
    shorter = [{"start_date": "2026-09-01", "end_date": "2026-09-02"}]
    with pytest.raises(ValidationFailed):
        update_scan(db, scan.id, u.id, {"search_windows": shorter})


def test_update_scan_allows_unrelated_field_on_legacy_over_limit_scan(db):
    """A scan created before this validation existed may already have nights >
    its window. Editing a field that isn't nights/search_windows must not
    retroactively re-validate and lock the scan out of edits."""
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, nights=10)
    db.add(scan)
    db.flush()
    updated = update_scan(db, scan.id, u.id, {"name": "Legacy scan"})
    assert updated.name == "Legacy scan"
    assert updated.nights == 10


def test_get_scan_admin_scope_ignores_owner(db):
    u1 = make_user(db, "a@e.com")
    scan = Scan(user_id=u1.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = get_scan(db, scan.id, None)
    assert result.id == scan.id


def test_pause_scan_admin_scope(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.active)
    db.add(scan)
    db.flush()
    result = pause_scan(db, scan.id)
    assert result.status == ScanStatus.paused


def test_resume_scan_admin_scope(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, status=ScanStatus.paused)
    db.add(scan)
    db.flush()
    result = resume_scan(db, scan.id)
    assert result.status == ScanStatus.active


def test_delete_scan_admin_scope(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    delete_scan(db, scan.id)
    assert scan.deleted_at is not None


def test_list_all_scans_returns_scans_across_users(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    db.add_all([
        Scan(user_id=u1.id, search_windows=WINDOWS),
        Scan(user_id=u2.id, search_windows=WINDOWS),
    ])
    db.flush()
    assert len(scans_svc.list_all_scans(db)) == 2


def test_list_all_scans_excludes_soft_deleted(db):
    u = make_user(db)
    scan = Scan(user_id=u.id, search_windows=WINDOWS, deleted_at=datetime.now(timezone.utc))
    db.add(scan)
    db.flush()
    assert scans_svc.list_all_scans(db) == []


def test_list_all_scans_eager_loads_owner_email(db):
    u = make_user(db, "owner@e.com")
    scan = Scan(user_id=u.id, search_windows=WINDOWS)
    db.add(scan)
    db.flush()
    result = scans_svc.list_all_scans(db)
    assert result[0].user.email == "owner@e.com"
