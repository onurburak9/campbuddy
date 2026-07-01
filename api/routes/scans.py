import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from api.deps import get_db_dep, get_current_user
from api.schemas import ScanCreate, ScanUpdate, ScanResponse, ScanRunResponse, ScanResultResponse, ScanStatsResponse
from core.services import scans as scans_svc
from core.services import history as history_svc
from db.models import ScanOutcome

router = APIRouter()


@router.get("", response_model=List[ScanResponse])
def list_scans(db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.list_scans(db, user.id)


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def create_scan(body: ScanCreate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.create_scan(db, user.id, json.loads(body.json()))


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.get_scan(db, scan_id, user.id)


@router.patch("/{scan_id}", response_model=ScanResponse)
def update_scan(scan_id: int, body: ScanUpdate, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.update_scan(db, scan_id, user.id, json.loads(body.json(exclude_unset=True)))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    scans_svc.delete_scan(db, scan_id, user.id)


@router.post("/{scan_id}/pause", response_model=ScanResponse)
def pause_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.pause_scan(db, scan_id, user.id)


@router.post("/{scan_id}/resume", response_model=ScanResponse)
def resume_scan(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return scans_svc.resume_scan(db, scan_id, user.id)


@router.get("/{scan_id}/runs", response_model=List[ScanRunResponse])
def list_runs(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    outcome: Optional[ScanOutcome] = Query(default=None),
    started_after: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_runs(
        db, scan_id, user.id, page=page, page_size=page_size,
        outcome=outcome, started_after=started_after,
    )


@router.get("/{scan_id}/runs/{run_id}/results", response_model=List[ScanResultResponse])
def list_run_results(
    scan_id: int,
    run_id: int,
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_run_results(db, scan_id, run_id, user.id)


@router.get("/{scan_id}/results", response_model=List[ScanResultResponse])
def list_results(
    scan_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_dep),
    user=Depends(get_current_user),
):
    return history_svc.list_results(db, scan_id, user.id, page=page, page_size=page_size)


@router.get("/{scan_id}/stats", response_model=ScanStatsResponse)
def get_stats(scan_id: int, db: Session = Depends(get_db_dep), user=Depends(get_current_user)):
    return history_svc.stats(db, scan_id, user.id)
