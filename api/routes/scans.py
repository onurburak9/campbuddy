from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from api.deps import get_db_dep, get_current_user
from api.schemas import ScanCreate, ScanUpdate, ScanResponse, ScanRunResponse, ScanResultResponse
from core.services import scans as scans_svc
from core.services import history as history_svc
from core.services.exceptions import NotFound, Forbidden, LimitExceeded

router = APIRouter()


def _scan_errors(exc):
    if isinstance(exc, NotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, Forbidden):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, LimitExceeded):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


@router.get("", response_model=List[ScanResponse])
def list_scans(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.list_scans(db, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def create_scan(body: ScanCreate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.create_scan(db, user.id, body.dict(exclude_unset=False))
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.get_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.patch("/{scan_id}", response_model=ScanResponse)
def update_scan(scan_id: int, body: ScanUpdate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.update_scan(db, scan_id, user.id, body.dict(exclude_unset=True))
    except Exception as exc:
        _scan_errors(exc)


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        scans_svc.delete_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.post("/{scan_id}/pause", response_model=ScanResponse)
def pause_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.pause_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.post("/{scan_id}/resume", response_model=ScanResponse)
def resume_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    try:
        return scans_svc.resume_scan(db, scan_id, user.id)
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}/runs", response_model=List[ScanRunResponse])
def list_runs(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    try:
        return history_svc.list_runs(db, scan_id, user.id, page=page, page_size=page_size)
    except Exception as exc:
        _scan_errors(exc)


@router.get("/{scan_id}/results", response_model=List[ScanResultResponse])
def list_results(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    try:
        return history_svc.list_results(db, scan_id, user.id, page=page, page_size=page_size)
    except Exception as exc:
        _scan_errors(exc)
