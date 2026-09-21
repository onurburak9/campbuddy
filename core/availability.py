import logging
from datetime import date

from camply.containers import SearchWindow
from camply.search import SearchRecreationDotGov

logger = logging.getLogger(__name__)

PROVIDER_MAP = {
    "RecreationDotGov": SearchRecreationDotGov,
}

# Equipment values camply's `equipment=` kwarg natively filters on
# (camply.config.search_config.EquipmentOptions.__all_accepted_equipment__).
CAMPLY_EQUIPMENT_OPTIONS = ("tent", "rv", "trailer", "vehicle")

# camply buckets "Horse" (along with Hammock/Boat) under an "other" equipment
# category that its own `equipment=` kwarg validation rejects as unrecognized,
# so it can never filter for it. We filter for it ourselves post-fetch by
# inspecting each site's raw permitted_equipment list.
HORSE_EQUIPMENT = "horse"

EQUIPMENT_TYPES = CAMPLY_EQUIPMENT_OPTIONS + (HORSE_EQUIPMENT,)


def _is_expired(window: dict) -> bool:
    return date.fromisoformat(window["end_date"]) < date.today()


def active_windows(search_windows: list[dict]) -> list[dict]:
    return [w for w in search_windows if not _is_expired(w)]


def _permits_horse(site) -> bool:
    permitted = getattr(site, "permitted_equipment", None) or []
    return any(
        getattr(item, "equipment_name", "").lower() == HORSE_EQUIPMENT
        for item in permitted
    )


def check_availability(scan) -> list:
    cls = PROVIDER_MAP.get(scan.provider)
    if cls is None:
        raise ValueError(f"Unsupported provider: {scan.provider}")

    if not any([scan.rec_area_ids, scan.campground_ids, scan.campsite_ids]):
        raise ValueError(
            f"Scan {scan.id} has no targeting: at least one of "
            "rec_area_ids, campground_ids, or campsite_ids is required"
        )

    windows_data = active_windows(scan.search_windows)
    if not windows_data:
        return []

    windows = [
        SearchWindow(
            start_date=date.fromisoformat(w["start_date"]),
            end_date=date.fromisoformat(w["end_date"]),
        )
        for w in windows_data
    ]

    equipment_types = set(scan.equipment_types or [])

    kwargs = dict(search_window=windows, nights=scan.nights, weekends_only=scan.weekends_only)
    if scan.rec_area_ids:
        kwargs["recreation_area"] = scan.rec_area_ids
    if scan.campground_ids:
        kwargs["campgrounds"] = scan.campground_ids
    if scan.campsite_ids:
        kwargs["campsites"] = scan.campsite_ids
    if scan.days_of_week:
        kwargs["days_of_the_week"] = scan.days_of_week
    camply_equipment = equipment_types & set(CAMPLY_EQUIPMENT_OPTIONS)
    if camply_equipment:
        kwargs["equipment"] = [(name, None) for name in camply_equipment]

    sites = cls(**kwargs).get_matching_campsites(continuous=False)

    if HORSE_EQUIPMENT in equipment_types:
        sites = [site for site in sites if _permits_horse(site)]

    logger.info("Scan %s: %d site(s) found", getattr(scan, "id", "?"), len(sites))
    return sites
