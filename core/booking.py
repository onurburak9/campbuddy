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
