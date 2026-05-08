import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.recreation.gov/login"
EMAIL_SELECTOR = "input[name='email'], input[type='email']"
PASSWORD_SELECTOR = "input[name='password'], input[type='password']"
SUBMIT_SELECTOR = "button[type='submit']"
CART_SELECTOR = "button[data-component='book-campsite'], button:has-text('Add to Cart'), button:has-text('Book Now')"


def add_to_cart(booking_url: str, email: str, password: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            page.fill(EMAIL_SELECTOR, email)
            page.fill(PASSWORD_SELECTOR, password)
            page.click(SUBMIT_SELECTOR)
            page.wait_for_url(lambda url: "login" not in url, timeout=15_000)

            page.goto(booking_url, wait_until="networkidle", timeout=30_000)
            page.wait_for_selector(CART_SELECTOR, timeout=10_000)
            page.click(CART_SELECTOR)
            page.wait_for_timeout(3_000)

            if "cart" in page.url or "checkout" in page.url:
                return {"success": True}
            return {"success": False, "error": "Cart page not reached after click"}

        except PlaywrightTimeout as e:
            logger.error("Playwright timeout: %s", e)
            return {"success": False, "error": f"Timeout: {e}"}
        except Exception as e:
            logger.error("Playwright error: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            browser.close()
