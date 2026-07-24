from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from api.deps import get_db_dep, get_current_admin
from api.schemas import AdminUserResponse, AdminScanResponse, ScanResponse
from core.services import users as users_svc
from core.services import scans as scans_svc

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/users", response_model=List[AdminUserResponse])
def list_users(db: Session = Depends(get_db_dep)):
    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            is_admin=u.is_admin,
            scan_limit=u.scan_limit,
            scans_used=count,
            has_telegram=bool(u.telegram_chat_id),
            created_at=u.created_at,
        )
        for u, count in users_svc.list_users_with_scan_counts(db)
    ]


@router.get("/scans", response_model=List[AdminScanResponse])
def list_scans(db: Session = Depends(get_db_dep)):
    return [
        AdminScanResponse(
            id=s.id,
            user_id=s.user_id,
            user_email=s.user.email,
            provider=s.provider,
            name=s.name,
            status=s.status,
            polling_interval=s.polling_interval,
            created_at=s.created_at,
        )
        for s in scans_svc.list_all_scans(db)
    ]


@router.post("/scans/{scan_id}/pause", response_model=ScanResponse)
def pause_scan(scan_id: int, db: Session = Depends(get_db_dep)):
    return scans_svc.pause_scan(db, scan_id, admin=True)


@router.post("/scans/{scan_id}/resume", response_model=ScanResponse)
def resume_scan(scan_id: int, db: Session = Depends(get_db_dep)):
    return scans_svc.resume_scan(db, scan_id, admin=True)


@router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(scan_id: int, db: Session = Depends(get_db_dep)):
    scans_svc.delete_scan(db, scan_id, admin=True)
