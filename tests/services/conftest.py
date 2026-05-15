import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Base, User
from db.session import make_session_factory


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def make_user(db, email="u@e.com", scan_limit=5, hashed_password=None):
    user = User(email=email, scan_limit=scan_limit, hashed_password=hashed_password)
    db.add(user)
    db.flush()
    return user
