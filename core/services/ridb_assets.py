import logging

import httpx

logger = logging.getLogger(__name__)

ASSETS_URL = "https://ridb.recreation.gov/api/v1/public/assets"


class AssetsSearchError(Exception):
    pass


def search_assets(terms: str, asset_type: str, limit: int = 15, timeout: float = 5.0) -> list:
    try:
        resp = httpx.get(
            ASSETS_URL,
            params={"terms": terms, "asset_types[]": asset_type, "limit": limit, "page": 0, "sort": "name"},
            timeout=timeout,
        )
        if not resp.is_success:
            raise AssetsSearchError(f"HTTP {resp.status_code}")
        data = resp.json()
    except httpx.HTTPError as e:
        raise AssetsSearchError(str(e)) from e
    except ValueError as e:
        raise AssetsSearchError(f"invalid JSON response: {e}") from e
    if "data" not in data:
        raise AssetsSearchError("response missing 'data' key")
    return data["data"]


def assets_endpoint_healthy(timeout: float = 5.0) -> bool:
    try:
        search_assets("yosemite", "recarea", limit=1, timeout=timeout)
        return True
    except AssetsSearchError:
        return False
