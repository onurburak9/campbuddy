import base64

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from config.settings import Settings, get_settings


VALID_KEY = Fernet.generate_key().decode()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", VALID_KEY)
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret-key")
    return monkeypatch


def test_loads_required_fields(env):
    s = Settings(_env_file=None)
    assert s.smtp_user == "test@example.com"
    assert s.smtp_host == "smtp.gmail.com"
    assert s.database_url == "sqlite:///./data/campbuddy.db"
    assert s.playwright_service_url == "http://playwright:8001"


def test_telegram_defaults_empty(env):
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == ""


def test_missing_required_field_raises(env):
    env.delenv("ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_fernet_key_raises(env):
    env.setenv("ENCRYPTION_KEY", "abc")  # invalid base64 padding
    with pytest.raises(ValidationError, match="url-safe base64"):
        Settings(_env_file=None)


def test_short_fernet_key_raises(env):
    short = base64.urlsafe_b64encode(b"a" * 16).decode()
    env.setenv("ENCRYPTION_KEY", short)
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None)


def test_get_settings_cached(env):
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b


def test_api_secret_key_loaded_from_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SMTP_USER", "u@e.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_FROM", "u@e.com")
    monkeypatch.setenv("API_SECRET_KEY", "my-secret")
    s = Settings(_env_file=None)
    assert s.api_secret_key == "my-secret"


def test_ridb_api_key_defaults_empty(env):
    s = Settings(_env_file=None)
    assert s.ridb_api_key == ""


def test_ridb_api_key_loaded_from_env(env):
    env.setenv("RIDB_API_KEY", "test-ridb-key")
    s = Settings(_env_file=None)
    assert s.ridb_api_key == "test-ridb-key"
