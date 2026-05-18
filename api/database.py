from db.session import make_engine, make_session_factory

_factory = None


def init(database_url: str = None) -> None:
    global _factory
    if database_url is None:
        from config.settings import get_settings
        database_url = get_settings().database_url
    engine = make_engine(database_url)
    _factory = make_session_factory(engine)


def get_factory():
    return _factory
