import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
except ImportError:  # pragma: no cover - sidecar-only dependency
    # The app venv deliberately excludes the browser stack (camply pins pydantic
    # v1, see ADR 005), but its unit tests still import this module.
    class PlaywrightTimeout(Exception):
        pass


LOGIN_URL = "https://www.recreation.gov/log-in"
EMAIL_SELECTOR = "input#email"
PASSWORD_SELECTOR = "input#password"
# The sign-in form is an unclassed submit button inside a modal; its accessible
# name is the only stable handle.
SUBMIT_BUTTON_NAME = "Log In"
LOGGED_IN_SELECTOR = "button[aria-label^='User:']"
CART_SELECTOR = "#add-cart-campsite"
# A successful "Add to Cart" leaves the campsite page for a per-reservation
# order-details URL. That redirect is the only per-site success signal: the
# cart badge is cumulative, so it still reads "1 item in cart" when the *second*
# site of a batch fails.
ORDER_DETAILS_PATH = "/camping/reservations/orderdetails"

# Recreation.gov silently drops logins from headless Chromium — the form spins
# and no auth request is ever sent. Run headed (the container supplies an Xvfb
# display); this switch exists only for local debugging.
HEADLESS_ENV_VAR = "PLAYWRIGHT_HEADLESS"

LOGIN_TIMEOUT_MS = 45_000
ORDER_DETAILS_TIMEOUT_MS = 20_000
STOP_TIMEOUT_SECONDS = 30

# Patches the most common headless-detection vectors. Deliberately does NOT
# touch the user agent: overriding it while navigator.userAgentData still
# reported the real build is what produced the "outdated browser" interstitial.
STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

    Object.defineProperty(navigator, 'plugins', {
        get: () => Object.assign([1,2,3,4,5], {__proto__: PluginArray.prototype})
    });

    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    window.chrome = window.chrome || {
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


def _login(page, email: str, password: str) -> None:
    # /log-in redirects to the homepage and renders sign-in as a modal.
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_selector(EMAIL_SELECTOR, timeout=30_000)
    _jitter(600, 1200)
    _human_type(page, EMAIL_SELECTOR, email)
    _jitter(400, 800)
    _human_type(page, PASSWORD_SELECTOR, password)
    _jitter(500, 1000)
    submit = page.get_by_role("button", name=SUBMIT_BUTTON_NAME, exact=True).first
    submit.hover()
    _jitter(200, 500)
    submit.click()
    page.wait_for_selector(LOGGED_IN_SELECTOR, timeout=LOGIN_TIMEOUT_MS)
    logger.info("Login successful")


def _add_single(page, booking_url: str, check_in: str, check_out: str) -> dict:
    check_in_date = datetime.strptime(check_in.strip(), "%m-%d-%Y").date()
    check_out_date = datetime.strptime(check_out.strip(), "%m-%d-%Y").date()
    _set_search_session(page, check_in_date, check_out_date)
    _jitter(400, 800)
    page.goto(booking_url, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_selector("h1", timeout=30_000)
    _jitter(1500, 2500)
    try:
        page.click("button:has-text('Ignore')", timeout=1_000)
        _jitter(300, 600)
    except PlaywrightTimeout:
        pass
    page.wait_for_selector(CART_SELECTOR, timeout=15_000)

    add_button = page.locator(CART_SELECTOR)
    if add_button.is_disabled():
        # Already held in this account's cart, or no longer bookable for these
        # dates. Report it rather than burning 30s on an unclickable element.
        return {"success": False, "error": "Add to Cart is disabled for these dates"}

    page.hover(CART_SELECTOR)
    _jitter(400, 800)
    add_button.click()
    try:
        page.wait_for_url(
            lambda url: ORDER_DETAILS_PATH in url, timeout=ORDER_DETAILS_TIMEOUT_MS
        )
    except PlaywrightTimeout:
        return {
            "success": False,
            "error": f"No order-details redirect after Add to Cart — still at {page.url}",
        }
    logger.info("Added to cart: %s", booking_url)
    return {"success": True, "error": None}


def _add_all(page, sites: list[dict]) -> list[dict]:
    results = []
    for s in sites:
        try:
            results.append(_add_single(page, s["booking_url"], s["check_in"], s["check_out"]))
        except Exception as e:
            logger.error("Cart add failed for %s: %s", s.get("booking_url"), e)
            results.append({"success": False, "error": str(e)})
    return results


LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]

CONTEXT_OPTIONS = {
    "viewport": {"width": 1440, "height": 900},
    "locale": "en-US",
    "timezone_id": "America/Los_Angeles",
    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
}


def _start_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


def _launch_browser(p):
    headless = os.getenv(HEADLESS_ENV_VAR, "false").lower() == "true"
    return p.chromium.launch(headless=headless, args=LAUNCH_ARGS)


def _new_context(browser_):
    context = browser_.new_context(**CONTEXT_OPTIONS)
    context.add_init_script(STEALTH_JS)
    return context


# The browser is launched once and kept alive. Closing a headed Chromium in
# this container never returns: it leaves zombie processes and wedges the
# container so hard that Docker itself cannot kill it. Closing a *context* is
# instant, so per-request isolation comes from contexts instead.
#
# Playwright's sync objects are bound to the thread that created them, and
# FastAPI runs sync endpoints on a threadpool, so every browser operation is
# funnelled through one dedicated thread.
_browser_state = {"playwright": None, "browser": None}
_executor = None
_executor_lock = threading.Lock()


def _get_executor():
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
        return _executor


def run_in_browser_thread(fn):
    """Run `fn` on the single thread that owns the Playwright objects."""
    return _get_executor().submit(fn).result()


def get_shared_browser():
    """The long-lived browser, launched on first use and after a crash."""
    browser_ = _browser_state["browser"]
    if browser_ is not None and browser_.is_connected():
        return browser_
    if browser_ is not None:
        logger.warning("Shared browser died; relaunching")
    if _browser_state["playwright"] is None:
        _browser_state["playwright"] = _start_playwright()
    _browser_state["browser"] = _launch_browser(_browser_state["playwright"])
    return _browser_state["browser"]


def _with_page(work):
    """Run `work(page)` in a throwaway context on the shared browser."""
    context = _new_context(get_shared_browser())
    try:
        return work(context.new_page())
    finally:
        context.close()


def _stop_playwright() -> None:
    playwright = _browser_state["playwright"]
    if playwright is not None:
        playwright.stop()


def shutdown_browser(wait: bool = True) -> None:
    """Release the browser. Call on process shutdown.

    `playwright.stop()` (unlike `browser.close()`, which never returns for a
    headed Chromium here) terminates the driver and reaps every chrome process.
    Skipping it leaves zombies behind and Docker cannot stop the container at
    all — `docker kill` reports "did not receive an exit event".

    The Playwright objects are bound to the browser thread, so the stop has to
    run there too.
    """
    global _executor
    executor = _executor
    stopped_cleanly = True
    if _browser_state["playwright"] is not None:
        try:
            if executor is not None:
                executor.submit(_stop_playwright).result(timeout=STOP_TIMEOUT_SECONDS)
            else:
                _stop_playwright()
        except Exception as e:
            # Never block shutdown on a wedged driver — the task may still be
            # running, so don't join the executor thread below either.
            logger.warning("Playwright shutdown failed: %s", e)
            stopped_cleanly = False
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=wait and stopped_cleanly)
            _executor = None
    _browser_state["playwright"] = None
    _browser_state["browser"] = None


def add_to_cart(booking_url: str, email: str, password: str, check_in: str, check_out: str) -> dict:
    def work(page):
        _login(page, email, password)
        return _add_single(page, booking_url, check_in, check_out)

    try:
        return run_in_browser_thread(lambda: _with_page(work))
    except Exception as e:
        logger.error("Playwright error: %s", e)
        return {"success": False, "error": str(e)}


def add_to_cart_batch(email: str, password: str, sites: list[dict]) -> list[dict]:
    def work(page):
        _login(page, email, password)
        return _add_all(page, sites)

    try:
        return run_in_browser_thread(lambda: _with_page(work))
    except Exception as e:
        logger.error("Batch login/setup error: %s", e)
        return [{"success": False, "error": str(e)} for _ in sites]
