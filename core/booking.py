import logging
import httpx

logger = logging.getLogger(__name__)


def attempt_cart_add(booking_url: str, email: str, password: str, settings, check_in: str, check_out: str) -> bool:
    try:
        resp = httpx.post(
            f"{settings.playwright_service_url}/add-to-cart",
            json={"booking_url": booking_url, "email": email, "password": password, "check_in": check_in, "check_out": check_out},
            timeout=60.0,
        )
        if not resp.is_success:
            logger.error("Sidecar returned HTTP %d", resp.status_code)
            return False
        try:
            data = resp.json()
        except Exception:
            logger.error("Sidecar returned non-JSON body")
            return False
        if not data.get("success"):
            logger.warning("Cart add failed: %s", data.get("error"))
        return bool(data.get("success"))
    except httpx.HTTPError as e:
        logger.error("HTTP error contacting sidecar: %s", e)
        return False


def attempt_cart_add_batch(sites: list[dict], email: str, password: str, settings, timeout: float = 120.0) -> list[dict]:
    try:
        resp = httpx.post(
            f"{settings.playwright_service_url}/add-to-cart-batch",
            json={"email": email, "password": password, "sites": sites},
            timeout=timeout,
        )
        if not resp.is_success:
            logger.error("Batch sidecar returned HTTP %d", resp.status_code)
            return [{"success": False, "error": f"HTTP {resp.status_code}"} for _ in sites]
        results = resp.json().get("results", [])
        if len(results) != len(sites):
            logger.error("Batch result count %d != site count %d", len(results), len(sites))
            return [{"success": False, "error": "result count mismatch"} for _ in sites]
        return results
    except httpx.HTTPError as e:
        logger.error("HTTP error contacting batch sidecar: %s", e)
        return [{"success": False, "error": str(e)} for _ in sites]
    except Exception as e:
        logger.error("Batch sidecar bad response: %s", e)
        return [{"success": False, "error": str(e)} for _ in sites]


def sidecar_healthy(settings, timeout: float = 5.0) -> bool:
    try:
        resp = httpx.get(f"{settings.playwright_service_url}/health", timeout=timeout)
        return resp.is_success
    except httpx.HTTPError:
        return False
