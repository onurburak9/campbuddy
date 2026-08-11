from fastapi import APIRouter, Depends, status
from api.deps import get_current_user
from api.schemas import FeedbackCreate
from config.settings import get_settings
from core.services import feedback as feedback_svc

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_feedback(body: FeedbackCreate, user=Depends(get_current_user)):
    feedback_svc.submit_feedback(user, body.page_path, body.message, get_settings())
