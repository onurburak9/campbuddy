from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.auth import verify_password, create_token, COOKIE_NAME
from api.deps import get_db_dep, get_current_user
from api.schemas import LoginRequest, MeResponse
from config.settings import get_settings
from core.services.users import get_user_by_email, scans_used
from core.services.exceptions import NotFound

router = APIRouter()


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db_dep)):
    try:
        user = get_user_by_email(db, body.email)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    settings = get_settings()
    token = create_token(user.id, settings.api_secret_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        email=user.email,
        scan_limit=user.scan_limit,
        scans_used=scans_used(db, user.id),
    )
