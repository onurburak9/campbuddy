from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.deps import get_current_user
from api.schemas import RecreationAreaResult, CampgroundResult, CampsiteResult
from core.services import search as search_svc

router = APIRouter()


@router.get("/recreation-areas", response_model=List[RecreationAreaResult])
def search_recreation_areas(
    q: str = Query(..., min_length=2),
    user=Depends(get_current_user),
):
    return search_svc.search_recreation_areas(q)


@router.get("/recreation-areas/resolve", response_model=List[RecreationAreaResult])
def resolve_recreation_areas(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_recreation_areas(ids)


@router.get("/campgrounds", response_model=List[CampgroundResult])
def search_campgrounds(
    q: Optional[str] = Query(default=None),
    rec_area_ids: Optional[List[int]] = Query(default=None),
    user=Depends(get_current_user),
):
    if not q and not rec_area_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide q or rec_area_ids")
    return search_svc.search_campgrounds(q, rec_area_ids)


@router.get("/campgrounds/resolve", response_model=List[CampgroundResult])
def resolve_campgrounds(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_campgrounds(ids)


@router.get("/campsites", response_model=List[CampsiteResult])
def list_campsites(
    campground_ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.list_campsites(campground_ids)


@router.get("/campsites/resolve", response_model=List[CampsiteResult])
def resolve_campsites(
    ids: List[int] = Query(...),
    user=Depends(get_current_user),
):
    return search_svc.resolve_campsites(ids)
