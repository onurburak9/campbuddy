import pytest
from db.models import User, Scan
from core.services.users import get_user_by_email, update_profile, scans_used, register_user
from core.services import scans as scans_svc
from core.services.exceptions import NotFound, InvalidState
from core.crypto import encrypt_password
from tests.services.conftest import make_user

ENCRYPTION_KEY = "1JeJa5uwBWlgLvtYCSfhs5v6MCccwuoxqTd03VOVEeQ="
WINDOWS = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]


def test_get_user_by_email_returns_user(db):
    u = make_user(db, "find@e.com")
    result = get_user_by_email(db, "find@e.com")
    assert result.id == u.id


def test_get_user_by_email_raises_not_found(db):
    with pytest.raises(NotFound):
        get_user_by_email(db, "ghost@e.com")


def test_update_profile_changes_email(db):
    u = make_user(db, "old@e.com")
    result = update_profile(db, u.id, {"email": "new@e.com"}, ENCRYPTION_KEY)
    assert result.email == "new@e.com"


def test_update_profile_encrypts_recreationgov_password(db):
    u = make_user(db)
    result = update_profile(db, u.id, {"recreationgov_password": "s3cr3t"}, ENCRYPTION_KEY)
    assert result.recreationgov_password is not None
    assert result.recreationgov_password != "s3cr3t"


def test_scans_used_counts_only_active(db):
    from datetime import datetime, timezone
    u = make_user(db)
    s1 = Scan(user_id=u.id, search_windows=WINDOWS)
    s2 = Scan(user_id=u.id, search_windows=WINDOWS)
    s3 = Scan(user_id=u.id, search_windows=WINDOWS,
              deleted_at=datetime.now(timezone.utc))
    db.add_all([s1, s2, s3])
    db.flush()
    assert scans_used(db, u.id) == 2


def test_update_profile_raises_not_found_for_missing_user(db):
    with pytest.raises(NotFound):
        update_profile(db, 9999, {"email": "x@e.com"}, ENCRYPTION_KEY)


def test_update_profile_ignores_disallowed_fields(db):
    u = make_user(db, scan_limit=5)
    result = update_profile(db, u.id, {"scan_limit": 99, "id": 9999, "email": "new@e.com"}, ENCRYPTION_KEY)
    assert result.email == "new@e.com"
    assert result.scan_limit == 5
    assert result.id == u.id


def test_get_user_by_email_excludes_soft_deleted(db):
    from datetime import datetime, timezone
    u = make_user(db, "softdel@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(NotFound):
        get_user_by_email(db, "softdel@e.com")


def test_clearing_recgov_email_disables_autobook(db):
    u = make_user(db)
    u.recreationgov_email = "rg@e.com"
    u.recreationgov_password = "enc"
    db.flush()
    scan = scans_svc.create_scan(db, u.id, {"search_windows": WINDOWS, "auto_book": True})
    assert scan.auto_book is True

    update_profile(db, u.id, {"recreationgov_email": ""}, ENCRYPTION_KEY)

    refreshed = db.query(Scan).filter(Scan.id == scan.id).first()
    assert refreshed.auto_book is False


def test_clearing_recgov_password_disables_autobook(db):
    u = make_user(db)
    u.recreationgov_email = "rg@e.com"
    u.recreationgov_password = encrypt_password("s3cr3t", ENCRYPTION_KEY)
    db.flush()
    scan = scans_svc.create_scan(db, u.id, {"search_windows": WINDOWS, "auto_book": True})
    assert scan.auto_book is True

    update_profile(db, u.id, {"recreationgov_password": ""}, ENCRYPTION_KEY)

    refreshed = db.query(Scan).filter(Scan.id == scan.id).first()
    assert refreshed.auto_book is False


def test_register_user_creates_user_with_hashed_password(db):
    user = register_user(db, "new@e.com", "already-hashed-value")
    assert user.id is not None
    assert user.email == "new@e.com"
    assert user.hashed_password == "already-hashed-value"


def test_register_user_defaults_scan_limit_to_five(db):
    user = register_user(db, "new@e.com", "hashed")
    assert user.scan_limit == 5


def test_register_user_leaves_recreationgov_fields_unset(db):
    user = register_user(db, "new@e.com", "hashed")
    assert user.recreationgov_email is None
    assert user.recreationgov_password is None


def test_register_user_raises_invalid_state_for_duplicate_email(db):
    make_user(db, "dup@e.com")
    with pytest.raises(InvalidState):
        register_user(db, "dup@e.com", "hashed")


def test_register_user_allows_email_reused_after_soft_delete(db):
    existing = make_user(db, "gone@e.com")
    existing.deleted_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.flush()
    user = register_user(db, "gone@e.com", "hashed")
    assert user.id != existing.id
