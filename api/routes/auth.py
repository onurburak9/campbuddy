import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, create_token, hash_password, COOKIE_NAME
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, scans_used
from core.services.exceptions import NotFound

logger = logging.getLogger(__name__)

router = APIRouter()

_DUMMY_HASH = hash_password("dummy-password-for-timing-equalization")


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db_dep)):
    try:
        user = get_user_by_email(db, body.email)
        hashed = user.hashed_password or _DUMMY_HASH
    except NotFound:
        user = None
        hashed = _DUMMY_HASH
    valid_password = verify_password(body.password, hashed)
    if user is None or not user.hashed_password or not valid_password:
        logger.warning("Failed login attempt for email=%s", body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    settings = get_settings()
    token = create_token(user.id, settings.api_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=86400,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    settings = get_settings()
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        email=user.email,
        scan_limit=user.scan_limit,
        scans_used=scans_used(db, user.id),
        has_telegram=bool(user.telegram_chat_id),
    )
