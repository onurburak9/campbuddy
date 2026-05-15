from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.deps import get_db_dep, get_current_user
from api.schemas import ProfileUpdate
from config.settings import get_settings
from core.services.users import update_profile

router = APIRouter()


class ProfileResponse(BaseModel):
    id: int
    email: str
    telegram_chat_id: Optional[str]
    recreationgov_email: Optional[str]
    scan_limit: int

    class Config:
        orm_mode = True


@router.patch("/me", response_model=ProfileResponse)
def patch_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    settings = get_settings()
    return update_profile(db, user.id, body.dict(exclude_unset=True), settings.encryption_key)
