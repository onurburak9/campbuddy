import logging
from functools import lru_cache
from typing import Optional

from camply import RecreationDotGov
from camply.config import RIDBConfig
from camply.containers.api_responses import RecreationAreaResponse

from config.settings import get_settings
from core.services.exceptions import UpstreamError
from core.services.ridb_assets import AssetsSearchError, search_assets

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_provider() -> RecreationDotGov:
    settings = get_settings()
    return RecreationDotGov(api_key=settings.ridb_api_key or None)


def _normalize_recreation_area(response: RecreationAreaResponse, raw: dict) -> dict:
    state = response.RECAREAADDRESS[0].AddressStateCode if response.RECAREAADDRESS else None
    # Managing agency (e.g. "National Park Service", "US Army Corps of Engineers") is the
    # closest RIDB gets to a "type" for a rec area — it isn't modeled by camply's
    # RecreationAreaResponse, so it's read straight off the raw RIDB payload.
    orgs = raw.get("ORGANIZATION") or []
    org_type = orgs[0].get("OrgName") if orgs else None
    return {"id": response.RecAreaID, "name": response.RecAreaName, "state": state, "type": org_type}


def _extract_asset_ids(assets: list, expected_type: Optional[str] = None) -> list:
    ids = []
    for item in assets:
        if expected_type and item.get("type") != expected_type:
            continue
        try:
            ids.append(int(item["id"]))
        except (KeyError, ValueError, TypeError):
            continue
    return ids


@lru_cache(maxsize=128)
def search_recreation_areas(query: str) -> list:
    try:
        assets = search_assets(query, "recarea")
    except AssetsSearchError as e:
        logger.warning("RIDB assets search unavailable (%s), falling back to recareas query search", e)
        return _search_recreation_areas_fallback(query)
    return resolve_recreation_areas(_extract_asset_ids(assets))


def _search_recreation_areas_fallback(query: str) -> list:
    provider = _get_provider()
    try:
        raw = provider.find_recreation_areas(search_string=query)
    except Exception as e:
        raise UpstreamError(str(e)) from e
    results = []
    for item in raw:
        try:
            results.append(_normalize_recreation_area(RecreationAreaResponse(**item), item))
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
            results.append(_normalize_recreation_area(RecreationAreaResponse(**data), data))
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
    if rec_area_ids:
        return _search_campgrounds_by_rec_area(rec_area_ids)
    try:
        assets = search_assets(query, "facility")
    except AssetsSearchError as e:
        logger.warning("RIDB assets search unavailable (%s), falling back to facilities query search", e)
        return _search_campgrounds_fallback(query)
    return resolve_campgrounds(_extract_asset_ids(assets, expected_type="Campground"))


def _search_campgrounds_by_rec_area(rec_area_ids) -> list:
    provider = _get_provider()
    try:
        facilities = provider.find_campgrounds(rec_area_id=list(rec_area_ids))
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return [_normalize_campground(f) for f in facilities]


def _search_campgrounds_fallback(query) -> list:
    provider = _get_provider()
    try:
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


def list_campsites(campground_ids: list) -> list:
    return _list_campsites_cached(tuple(sorted(campground_ids)))


@lru_cache(maxsize=128)
def _list_campsites_cached(campground_ids):
    provider = _get_provider()
    results = []
    try:
        for facility_id in campground_ids:
            for site in provider.paginate_recdotgov_campsites(facility_id=facility_id):
                results.append({
                    "id": site.campsite_id,
                    "name": site.name,
                    "loop": site.loop,
                    "campground_id": facility_id,
                })
    except Exception as e:
        raise UpstreamError(str(e)) from e
    return results


def resolve_campsites(ids: list) -> list:
    provider = _get_provider()
    results = []
    for campsite_id in ids:
        try:
            response = provider.get_campsite_by_id(campsite_id=campsite_id)
        except Exception:
            continue
        results.append({
            "id": response.CampsiteID,
            "name": response.CampsiteName,
            "loop": response.Loop,
            "campground_id": response.FacilityID,
        })
    return results
