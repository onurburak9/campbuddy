import pytest
from config.settings import Settings


def test_loads_required_fields(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.smtp_user == "test@example.com"
    assert s.database_url == "sqlite:///./data/campbuddy.db"
    assert s.playwright_service_url == "http://playwright:8001"


def test_telegram_defaults_empty(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "test@example.com")
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == ""
