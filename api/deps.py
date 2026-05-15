from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from api.auth import decode_token, COOKIE_NAME
from api.database import get_factory
from config.settings import get_settings
from db.models import User
from db.session import get_db


def get_db_dep():
    with get_db(get_factory()) as db:
        yield db


def get_current_user(
    db: Session = Depends(get_db_dep),
    campbuddy_session: Optional[str] = Cookie(default=None),
) -> User:
    if not campbuddy_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    settings = get_settings()
    user_id = decode_token(campbuddy_session, settings.api_secret_key)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
