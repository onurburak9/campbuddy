import logging
import random
import time
from datetime import date, datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_sync

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.recreation.gov/log-in"
EMAIL_SELECTOR = "input#email"
PASSWORD_SELECTOR = "input#rec-acct-sign-in-password"
SUBMIT_SELECTOR = "button.rec-acct-sign-in-btn"
LOGGED_IN_SELECTOR = "button[aria-label^='User:']"
CART_SELECTOR = "#add-cart-campsite"

# Keep this in sync with the actual latest Chrome release
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.6478.127 Safari/537.36"
)

# Patches the most common headless-detection vectors
STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

    Object.defineProperty(navigator, 'plugins', {
        get: () => Object.assign([1,2,3,4,5], {__proto__: PluginArray.prototype})
    });

    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

    window.chrome = {
        runtime: {},
        loadTimes: () => {},
        csi: () => {},
        app: {}
    };

    // Realistic permission query (headless returns 'denied' for notifications by default)
    const _origQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (p) =>
        p.name === 'notifications'
            ? Promise.resolve({state: 'default', onchange: null})
            : _origQuery(p);
}
"""


def _jitter(lo=300, hi=900):
    time.sleep(random.uniform(lo, hi) / 1000)


def _human_type(page, selector: str, text: str) -> None:
    page.click(selector)
    _jitter(100, 300)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(30, 100) / 1000)


def _set_search_session(page, check_in: date, check_out: date) -> None:
    """Inject dates into Recreation.gov's localStorage search session."""
    checkin_str = check_in.strftime("%m/%d/%Y")
    checkout_str = check_out.strftime("%m/%d/%Y")
    page.evaluate(f"""() => {{
        const s = JSON.parse(localStorage.getItem('r1s_search_session') || '{{}}');
        s.checkin_time = '{checkin_str}';
        s.checkout_time = '{checkout_str}';
        localStorage.setItem('r1s_search_session', JSON.stringify(s));
    }}""")


def add_to_cart(booking_url: str, email: str, password: str, check_in: str, check_out: str) -> dict:
    check_in_date = datetime.strptime(check_in.strip(), "%m-%d-%Y").date()
    check_out_date = datetime.strptime(check_out.strip(), "%m-%d-%Y").date()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/Los_Angeles",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
        )
        context.add_init_script(STEALTH_JS)
        page = context.new_page()
        stealth_sync(page)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_selector(EMAIL_SELECTOR, timeout=30_000)

            _jitter(600, 1200)
            _human_type(page, EMAIL_SELECTOR, email)
            _jitter(400, 800)
            _human_type(page, PASSWORD_SELECTOR, password)
            _jitter(500, 1000)
            page.hover(SUBMIT_SELECTOR)
            _jitter(200, 500)
            page.click(SUBMIT_SELECTOR)
            page.wait_for_selector(LOGGED_IN_SELECTOR, timeout=15_000)
            logger.info("Login successful")

            _set_search_session(page, check_in_date, check_out_date)
            _jitter(400, 800)

            page.goto(booking_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_selector("h1", timeout=30_000)
            _jitter(1500, 2500)

            # Dismiss outdated browser banner if present
            try:
                page.click("button:has-text('Ignore')", timeout=2_000)
                _jitter(300, 600)
            except PlaywrightTimeout:
                pass

            page.wait_for_selector(CART_SELECTOR, timeout=15_000)
            page.hover(CART_SELECTOR)
            _jitter(400, 800)
            page.click(CART_SELECTOR)
            _jitter(2000, 4000)

            cart_label = page.get_attribute("a[aria-label*='Cart']", "aria-label") or "unknown"
            logger.info("Post-click cart state: %s", cart_label)

            if "in cart" in cart_label:
                return {"success": True}
            return {"success": False, "error": f"Cart not updated after click — state: {cart_label}"}

        except PlaywrightTimeout as e:
            logger.error("Playwright timeout: %s", e)
            return {"success": False, "error": f"Timeout: {e}"}
        except Exception as e:
            logger.error("Playwright error: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            browser.close()
