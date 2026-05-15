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
