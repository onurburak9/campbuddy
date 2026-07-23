from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from api.auth import decode_token, COOKIE_NAME
from api.database import get_factory
from config.settings import get_settings
from core.services.exceptions import Forbidden
from db.models import User
from db.session import get_db


def get_db_dep():
    factory = get_factory()
    if factory is None:
        raise RuntimeError("api.database.init() was not called before serving requests")
    with get_db(factory) as db:
        yield db


def get_current_user(
    db: Session = Depends(get_db_dep),
    session_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> User:
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    settings = get_settings()
    user_id = decode_token(session_cookie, settings.api_secret_key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Cookie"},
        )
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise Forbidden("Admin access required")
    return user
