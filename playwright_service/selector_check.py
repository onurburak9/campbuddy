"""Loud early warning for a Recreation.gov redesign.

Every selector in `browser.py` is a guess about someone else's markup. When
Recreation.gov moved its login form, add-to-cart broke silently for weeks
because nothing in CI ever touched a real page.

Run this against the live site (no credentials, no cart changes):

    docker compose exec playwright python -m playwright_service.selector_check

Exits non-zero and names every selector that no longer resolves.
"""
import logging
import sys
from datetime import date, timedelta

from playwright_service.browser import (
    CART_SELECTOR,
    EMAIL_SELECTOR,
    LOGIN_URL,
    PASSWORD_SELECTOR,
    SUBMIT_BUTTON_NAME,
    _set_search_session,
    _with_page,
    run_in_browser_thread,
    shutdown_browser,
)

logger = logging.getLogger(__name__)

# Any bookable campsite works; this one is a stable year-round USACE site.
DEFAULT_CAMPSITE_URL = "https://www.recreation.gov/camping/campsites/42210"

LOGIN_SELECTORS = {
    "email field": EMAIL_SELECTOR,
    "password field": PASSWORD_SELECTOR,
}

CAMPSITE_SELECTORS = {
    "add-to-cart button": CART_SELECTOR,
}


def missing_login_selectors(page) -> list[str]:
    """Names of login-page selectors that no longer resolve."""
    missing = [
        f"{label} ({selector})"
        for label, selector in LOGIN_SELECTORS.items()
        if page.locator(selector).count() == 0
    ]
    if page.get_by_role("button", name=SUBMIT_BUTTON_NAME, exact=True).count() == 0:
        missing.append(f"submit button (role=button, name={SUBMIT_BUTTON_NAME!r})")
    return missing


def missing_campsite_selectors(page) -> list[str]:
    """Names of campsite-page selectors that no longer resolve."""
    return [
        f"{label} ({selector})"
        for label, selector in CAMPSITE_SELECTORS.items()
        if page.locator(selector).count() == 0
    ]


def _probe(page, campsite_url: str) -> list[str]:
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_selector(EMAIL_SELECTOR, timeout=30_000)
    missing = [f"login: {m}" for m in missing_login_selectors(page)]

    # The Add to Cart button only renders once a stay is selected, so seed the
    # search session exactly as the real cart-add flow does.
    check_in = date.today() + timedelta(days=60)
    _set_search_session(page, check_in, check_in + timedelta(days=2))
    page.goto(campsite_url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_selector("h1", timeout=30_000)
    page.wait_for_timeout(3_000)
    return missing + [f"campsite: {m}" for m in missing_campsite_selectors(page)]


def check_live_selectors(campsite_url: str = DEFAULT_CAMPSITE_URL) -> list[str]:
    """Load the real pages and return everything that no longer resolves."""
    return run_in_browser_thread(lambda: _with_page(lambda page: _probe(page, campsite_url)))


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        missing = check_live_selectors()
    finally:
        shutdown_browser()
    if missing:
        for item in missing:
            print(f"STALE SELECTOR: {item}")
        print(f"\n{len(missing)} selector(s) no longer resolve — add-to-cart is broken.")
        return 1
    print("All Recreation.gov selectors still resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
