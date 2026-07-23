import pytest
import hashlib
from datetime import datetime, timezone, timedelta
from db.models import User, Scan, PasswordResetToken
from core.services.users import get_user_by_email, update_profile, scans_used, register_user, create_password_reset_token, reset_password_with_token, set_admin, list_users_with_scan_counts
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


def test_create_password_reset_token_returns_token_for_existing_user(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    assert token is not None
    assert len(token) > 20


def test_create_password_reset_token_persists_hashed_token_with_expiry(db):
    u = make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    row = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == u.id).first()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.used_at is None
    assert row.expires_at > datetime.now(timezone.utc) + timedelta(minutes=29)
    assert row.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=30)


def test_create_password_reset_token_invalidates_prior_unused_token(db):
    make_user(db, "reset@e.com")
    first_token = create_password_reset_token(db, "reset@e.com")
    create_password_reset_token(db, "reset@e.com")
    first_row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hashlib.sha256(first_token.encode()).hexdigest()
    ).first()
    assert first_row.used_at is not None


def test_create_password_reset_token_returns_none_for_unknown_email(db):
    assert create_password_reset_token(db, "ghost@e.com") is None


def test_create_password_reset_token_returns_none_for_soft_deleted_user(db):
    u = make_user(db, "gone@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    assert create_password_reset_token(db, "gone@e.com") is None


def test_reset_password_with_token_updates_password_and_marks_used(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    user = reset_password_with_token(db, token, "new-hashed-value")
    assert user.hashed_password == "new-hashed-value"
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hashlib.sha256(token.encode()).hexdigest()
    ).first()
    assert row.used_at is not None


def test_reset_password_with_token_raises_not_found_for_unknown_token(db):
    with pytest.raises(NotFound):
        reset_password_with_token(db, "not-a-real-token", "hashed")


def test_reset_password_with_token_raises_not_found_for_expired_token(db):
    u = make_user(db, "reset@e.com")
    token = PasswordResetToken(
        user_id=u.id,
        token_hash=hashlib.sha256("expired-token".encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(token)
    db.flush()
    with pytest.raises(NotFound):
        reset_password_with_token(db, "expired-token", "hashed")


def test_reset_password_with_token_raises_not_found_for_already_used_token(db):
    make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    reset_password_with_token(db, token, "hashed-1")
    with pytest.raises(NotFound):
        reset_password_with_token(db, token, "hashed-2")


def test_reset_password_with_token_raises_not_found_for_soft_deleted_user(db):
    u = make_user(db, "reset@e.com")
    token = create_password_reset_token(db, "reset@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    with pytest.raises(NotFound):
        reset_password_with_token(db, token, "hashed")


def test_set_admin_grants_admin(db):
    make_user(db, "admin@e.com")
    result = set_admin(db, "admin@e.com", True)
    assert result.is_admin is True


def test_set_admin_revokes_admin(db):
    make_user(db, "admin@e.com")
    set_admin(db, "admin@e.com", True)
    result = set_admin(db, "admin@e.com", False)
    assert result.is_admin is False


def test_set_admin_raises_not_found_for_missing_user(db):
    with pytest.raises(NotFound):
        set_admin(db, "ghost@e.com", True)


def test_list_users_with_scan_counts_counts_active_scans(db):
    u1 = make_user(db, "a@e.com")
    u2 = make_user(db, "b@e.com")
    db.add_all([
        Scan(user_id=u1.id, search_windows=WINDOWS),
        Scan(user_id=u1.id, search_windows=WINDOWS),
    ])
    db.flush()
    counts = dict((u.id, count) for u, count in list_users_with_scan_counts(db))
    assert counts[u1.id] == 2
    assert counts[u2.id] == 0


def test_list_users_with_scan_counts_excludes_soft_deleted_users(db):
    from datetime import datetime, timezone
    u = make_user(db, "gone@e.com")
    u.deleted_at = datetime.now(timezone.utc)
    db.flush()
    ids = [usr.id for usr, _ in list_users_with_scan_counts(db)]
    assert u.id not in ids


def test_list_users_with_scan_counts_excludes_soft_deleted_scans(db):
    from datetime import datetime, timezone
    u = make_user(db, "a@e.com")
    scan = Scan(user_id=u.id, search_windows=WINDOWS, deleted_at=datetime.now(timezone.utc))
    db.add(scan)
    db.flush()
    counts = dict((usr.id, count) for usr, count in list_users_with_scan_counts(db))
    assert counts[u.id] == 0
