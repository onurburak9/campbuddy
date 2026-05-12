from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from db.models import Base


def make_engine(database_url: str):
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False, "timeout": 15} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _set_wal_mode(conn, _):
            conn.execute("PRAGMA journal_mode=WAL")
    return engine


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db(session_factory):
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
