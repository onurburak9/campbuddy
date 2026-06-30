"""CLI integration tests — real in-memory SQLite, get_factory patched."""
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cli import cli
from db.models import Base, User, Scan


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def factory(mocker):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    mock_settings = mocker.MagicMock()
    mock_settings.encryption_key = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ="
    mocker.patch("cli.get_factory", return_value=(sf, mock_settings))
    return sf


def _seed_user(factory, email="u@e.com"):
    with factory() as db:
        user = User(email=email)
        db.add(user)
        db.commit()
        return user.id


def _seed_scan(factory, user_id):
    with factory() as db:
        scan = Scan(
            user_id=user_id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            status="active",
        )
        db.add(scan)
        db.commit()
        return scan.id


def test_delete_user_soft_deletes(runner, factory):
    user_id = _seed_user(factory)
    result = runner.invoke(cli, ["delete-user", str(user_id)], input="y\n")
    assert result.exit_code == 0
    with factory() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None
        assert user.deleted_at is not None


def test_delete_user_cascades_soft_delete_to_scans(runner, factory):
    user_id = _seed_user(factory)
    scan_id = _seed_scan(factory, user_id)
    runner.invoke(cli, ["delete-user", str(user_id)], input="y\n")
    with factory() as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        assert scan.deleted_at is not None


def test_update_user_rejects_deleted_user(runner, factory):
    user_id = _seed_user(factory)
    with factory() as db:
        db.query(User).filter(User.id == user_id).update(
            {"deleted_at": datetime.now(timezone.utc)}
        )
        db.commit()
    result = runner.invoke(cli, ["update-user", str(user_id), "--email", "new@e.com"])
    assert "not found" in result.output


def test_update_user_sets_hashed_password(runner, factory):
    import bcrypt
    user_id = _seed_user(factory)
    result = runner.invoke(cli, ["update-user", str(user_id), "--password", "hunter2"])
    assert result.exit_code == 0
    with factory() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.hashed_password is not None
        assert bcrypt.checkpw(b"hunter2", user.hashed_password.encode())


def test_update_user_sets_scan_limit(runner, factory):
    user_id = _seed_user(factory)
    result = runner.invoke(cli, ["update-user", str(user_id), "--scan-limit", "3"])
    assert result.exit_code == 0
    with factory() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.scan_limit == 3


# --- set-password ---

def test_set_password_sets_hashed_password_for_existing_user(runner, factory):
    _seed_user(factory, email="alice@example.com")
    result = runner.invoke(
        cli,
        ["set-password", "alice@example.com", "--password", "s3cr3t!"],
    )
    assert result.exit_code == 0
    assert "Password set" in result.output
    from api.auth import verify_password
    with factory() as db:
        user = db.query(User).filter(User.email == "alice@example.com").first()
        assert user.hashed_password is not None
        assert verify_password("s3cr3t!", user.hashed_password)


def test_set_password_fails_for_unknown_email(runner, factory):
    result = runner.invoke(
        cli,
        ["set-password", "nobody@example.com", "--password", "pass"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# --- change-password ---

def test_change_password_succeeds_when_current_password_correct(runner, factory):
    from api.auth import hash_password, verify_password
    _seed_user(factory, email="bob@example.com")
    with factory() as db:
        user = db.query(User).filter(User.email == "bob@example.com").first()
        user.hashed_password = hash_password("old-pass")
        db.commit()

    result = runner.invoke(
        cli,
        [
            "change-password",
            "bob@example.com",
            "--current-password", "old-pass",
            "--new-password", "new-pass!",
        ],
    )
    assert result.exit_code == 0
    assert "Password changed" in result.output
    with factory() as db:
        user = db.query(User).filter(User.email == "bob@example.com").first()
        assert verify_password("new-pass!", user.hashed_password)


def test_change_password_fails_when_current_password_wrong(runner, factory):
    from api.auth import hash_password, verify_password
    _seed_user(factory, email="carol@example.com")
    with factory() as db:
        user = db.query(User).filter(User.email == "carol@example.com").first()
        original_hash = hash_password("correct-pass")
        user.hashed_password = original_hash
        db.commit()

    result = runner.invoke(
        cli,
        [
            "change-password",
            "carol@example.com",
            "--current-password", "wrong-pass",
            "--new-password", "new-pass!",
        ],
    )
    assert result.exit_code != 0
    assert "incorrect" in result.output.lower() or "wrong" in result.output.lower() or "invalid" in result.output.lower()
    with factory() as db:
        user = db.query(User).filter(User.email == "carol@example.com").first()
        assert verify_password("correct-pass", user.hashed_password)


def test_change_password_fails_when_user_has_no_password(runner, factory):
    _seed_user(factory, email="dave@example.com")
    result = runner.invoke(
        cli,
        [
            "change-password",
            "dave@example.com",
            "--current-password", "anything",
            "--new-password", "new-pass!",
        ],
    )
    assert result.exit_code != 0
    assert "no password" in result.output.lower() or "not set" in result.output.lower()
