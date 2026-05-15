from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.deps import get_db_dep, get_current_user
from api.schemas import ProfileUpdate, ProfileResponse
from config.settings import get_settings
from core.services.users import update_profile
from core.services.exceptions import NotFound

router = APIRouter()


@router.patch("/me", response_model=ProfileResponse)
def patch_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    settings = get_settings()
    try:
        return update_profile(db, user.id, body.dict(exclude_unset=True), settings.encryption_key)
    except NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
