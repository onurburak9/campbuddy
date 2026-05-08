import logging
from datetime import date
from camply.containers import SearchWindow
from camply.search import SearchRecreationDotGov

logger = logging.getLogger(__name__)

PROVIDER_MAP = {
    "RecreationDotGov": "SearchRecreationDotGov",
}


def check_availability(scan) -> list:
    cls_name = PROVIDER_MAP.get(scan.provider)
    if cls_name is None:
        raise ValueError(f"Unsupported provider: {scan.provider}")
    cls = globals()[cls_name]

    windows = [
        SearchWindow(
            start_date=date.fromisoformat(w["start_date"]),
            end_date=date.fromisoformat(w["end_date"]),
        )
        for w in scan.search_windows
    ]

    kwargs = dict(search_window=windows, nights=scan.nights, weekends_only=scan.weekends_only)
    if scan.rec_area_ids:
        kwargs["recreation_area"] = scan.rec_area_ids
    if scan.campground_ids:
        kwargs["campgrounds"] = scan.campground_ids
    if scan.campsite_ids:
        kwargs["campsites"] = scan.campsite_ids
    if scan.days_of_week:
        kwargs["days_of_the_week"] = scan.days_of_week

    sites = cls(**kwargs).get_matching_campsites(continuous=False)
    logger.info("Scan %s: %d site(s) found", getattr(scan, "id", "?"), len(sites))
    return sites
