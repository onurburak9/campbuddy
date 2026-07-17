import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, hash_password, COOKIE_NAME, issue_session_cookie
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, register_user, scans_used, create_password_reset_token, reset_password_with_token
from core.services.exceptions import NotFound, InvalidState
from core.notifier import send_password_reset_email

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
    issue_session_cookie(response, user.id, settings)
    return {"ok": True}


@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    if not settings.registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is currently disabled")
    try:
        user = register_user(db, body.email, hash_password(body.password))
    except InvalidState:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    issue_session_cookie(response, user.id, settings)
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    raw_token = create_password_reset_token(db, body.email)
    if raw_token:
        reset_url = f"{settings.app_base_url}/reset-password?token={raw_token}"
        try:
            send_password_reset_email(body.email, reset_url, settings)
        except Exception as e:
            logger.error("Password reset email failed: %s", e)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, response: Response, db: Session = Depends(get_db_dep)):
    settings = get_settings()
    try:
        user = reset_password_with_token(db, body.token, hash_password(body.password))
    except NotFound:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")
    issue_session_cookie(response, user.id, settings)
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
