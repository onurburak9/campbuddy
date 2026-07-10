from functools import lru_cache
from typing import Optional

from camply import RecreationDotGov
from camply.config import RIDBConfig
from camply.containers.api_responses import RecreationAreaResponse

from config.settings import get_settings
from core.services.exceptions import UpstreamError


@lru_cache(maxsize=1)
def _get_provider() -> RecreationDotGov:
    settings = get_settings()
    return RecreationDotGov(api_key=settings.ridb_api_key or None)


def _normalize_recreation_area(response: RecreationAreaResponse) -> dict:
    state = response.RECAREAADDRESS[0].AddressStateCode if response.RECAREAADDRESS else None
    return {"id": response.RecAreaID, "name": response.RecAreaName, "state": state}


@lru_cache(maxsize=128)
def search_recreation_areas(query: str) -> list:
    provider = _get_provider()
    try:
        raw = provider.find_recreation_areas(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    results = []
    for item in raw:
        try:
            results.append(_normalize_recreation_area(RecreationAreaResponse(**item)))
        except Exception:
            continue
    return results


def resolve_recreation_areas(ids: list) -> list:
    provider = _get_provider()
    results = []
    for rec_area_id in ids:
        try:
            data = provider.get_ridb_data(
                path=f"{RIDBConfig.REC_AREA_API_PATH}/{rec_area_id}",
                params={"full": True},
            )
            results.append(_normalize_recreation_area(RecreationAreaResponse(**data)))
        except Exception:
            continue
    return results


def _normalize_campground(facility) -> dict:
    return {
        "id": facility.facility_id,
        "name": facility.facility_name,
        "recreation_area": facility.recreation_area,
        "recreation_area_id": facility.recreation_area_id,
    }


def search_campgrounds(query: Optional[str], rec_area_ids: Optional[list] = None) -> list:
    key = tuple(sorted(rec_area_ids)) if rec_area_ids else None
    return _search_campgrounds_cached(query, key)


@lru_cache(maxsize=128)
def _search_campgrounds_cached(query, rec_area_ids):
    provider = _get_provider()
    try:
        if rec_area_ids:
            facilities = provider.find_campgrounds(rec_area_id=list(rec_area_ids))
        else:
            facilities = provider.find_campgrounds(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return [_normalize_campground(f) for f in facilities]


def resolve_campgrounds(ids: list) -> list:
    provider = _get_provider()
    results = []
    for campground_id in ids:
        try:
            facilities = provider.find_campgrounds(campground_id=[campground_id])
        except Exception:
            continue
        if facilities:
            results.append(_normalize_campground(facilities[0]))
    return results
