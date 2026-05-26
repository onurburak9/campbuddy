from sqlalchemy import text
import api.database as api_db

# Import the real init so we can call it even though conftest patches the module
# attribute — keep a reference before the autouse fixture replaces it.
_real_init = api_db.init


def test_init_creates_factory_with_explicit_url(monkeypatch):
    # The autouse setup_test_db fixture patches api.database.init to a no-op,
    # so we call the real function via the saved reference and reset _factory
    # ourselves so the post-test autouse teardown is unaffected.
    monkeypatch.setattr(api_db, "_factory", None)
    _real_init("sqlite:///:memory:")
    factory = api_db.get_factory()
    assert factory is not None
    # Calling the factory should produce a working Session
    session = factory()
    try:
        session.execute(text("SELECT 1"))
    finally:
        session.close()


def test_init_falls_back_to_settings_url(monkeypatch):
    # Cover the `if database_url is None` branch by passing no URL.
    # get_settings() reads DATABASE_URL from env; monkeypatch it to in-memory.
    from config.settings import Settings
    monkeypatch.setattr(api_db, "_factory", None)
    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )
    _real_init()
    assert api_db.get_factory() is not None
