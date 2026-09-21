"""Unit tests for the DOM-driving half of the sidecar.

These cover `_login`, `_add_single` and `_new_page` — the functions that were
previously only ever mocked out, which is why a Recreation.gov redesign broke
add-to-cart without turning a single test red. A fake page records which
selectors the code actually drives, so a stale selector fails here.
"""
import pytest

import playwright_service.browser as browser


@pytest.fixture(autouse=True)
def no_sleeping(mocker):
    """Strip the anti-bot jitter so the suite stays fast."""
    mocker.patch.object(browser, "_jitter")
    mocker.patch.object(browser.time, "sleep")


class FakeLocator:
    def __init__(self, page, selector, disabled=False):
        self.page = page
        self.selector = selector
        self._disabled = disabled

    @property
    def first(self):
        return self

    def is_disabled(self):
        return self._disabled

    def hover(self):
        self.page.hovered.append(self.selector)

    def click(self, **kwargs):
        self.page.clicked.append(self.selector)
        self.page._run_click_effect(self.selector)


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def type(self, char):
        self.page.typed[self.page.focused] = self.page.typed.get(self.page.focused, "") + char


class FakePage:
    """Minimal stand-in for a Playwright Page that records what it was asked to do."""

    def __init__(self, url="about:blank", missing_selectors=(), disabled_selectors=(),
                 click_effects=None, url_after_cart_click=None):
        self.url = url
        self.missing = set(missing_selectors)
        self.disabled = set(disabled_selectors)
        self.click_effects = click_effects or {}
        self.url_after_cart_click = url_after_cart_click
        self.typed = {}
        self.clicked = []
        self.hovered = []
        self.waited_selectors = []
        self.evaluated = []
        self.goto_urls = []
        self.focused = None
        self.keyboard = FakeKeyboard(self)

    def _run_click_effect(self, selector):
        if selector == browser.CART_SELECTOR and self.url_after_cart_click:
            self.url = self.url_after_cart_click
        effect = self.click_effects.get(selector)
        if effect:
            effect(self)

    def goto(self, url, **kwargs):
        self.goto_urls.append(url)
        self.url = url

    def wait_for_selector(self, selector, **kwargs):
        self.waited_selectors.append(selector)
        if selector in self.missing:
            raise browser.PlaywrightTimeout(f"Timeout waiting for {selector}")

    def click(self, selector, **kwargs):
        if selector in self.missing:
            raise browser.PlaywrightTimeout(f"Timeout waiting for {selector}")
        self.focused = selector
        self.clicked.append(selector)
        self._run_click_effect(selector)

    def hover(self, selector, **kwargs):
        self.hovered.append(selector)

    def wait_for_url(self, matcher, **kwargs):
        # Clicks resolve synchronously here, so the URL is already final.
        if matcher(self.url) if callable(matcher) else matcher in self.url:
            return
        raise browser.PlaywrightTimeout(f"Timeout waiting for url, still at {self.url}")

    def locator(self, selector):
        return FakeLocator(self, selector, disabled=selector in self.disabled)

    def get_by_role(self, role, name=None, exact=False):
        return FakeLocator(self, f"role={role}[name={name}]")

    def evaluate(self, script, *args):
        self.evaluated.append(script)


ORDER_DETAILS_URL = "https://www.recreation.gov/camping/reservations/orderdetails?id=abc-123"
CAMPSITE_URL = "https://www.recreation.gov/camping/campsites/42667"


def make_campsite_page(**kwargs):
    kwargs.setdefault("url", "https://www.recreation.gov/")
    # The outdated-browser banner is absent on a current browser.
    kwargs.setdefault("missing_selectors", ["button:has-text('Ignore')"])
    return FakePage(**kwargs)


# --------------------------------------------------------------------------
# _login
# --------------------------------------------------------------------------

def test_login_types_into_the_current_password_field():
    page = FakePage()
    browser._login(page, "u@e.com", "s3cret")
    assert page.typed["input#password"] == "s3cret"


def test_login_types_into_the_current_email_field():
    page = FakePage()
    browser._login(page, "u@e.com", "s3cret")
    assert page.typed["input#email"] == "u@e.com"


def test_login_waits_for_the_logged_in_user_marker():
    page = FakePage()
    browser._login(page, "u@e.com", "s3cret")
    assert browser.LOGGED_IN_SELECTOR in page.waited_selectors


def test_login_raises_when_the_logged_in_marker_never_appears():
    page = FakePage(missing_selectors=[browser.LOGGED_IN_SELECTOR])
    with pytest.raises(browser.PlaywrightTimeout):
        browser._login(page, "u@e.com", "s3cret")


# --------------------------------------------------------------------------
# _add_single
# --------------------------------------------------------------------------

def test_add_single_succeeds_when_order_details_page_is_reached():
    page = make_campsite_page(url_after_cart_click=ORDER_DETAILS_URL)
    result = browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    assert result == {"success": True, "error": None}


def test_add_single_fails_when_click_does_not_reach_order_details():
    """A cumulative cart badge must not be mistaken for this site being added."""
    page = make_campsite_page(url_after_cart_click=None)
    result = browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    assert result["success"] is False
    assert CAMPSITE_URL in result["error"]


def test_add_single_reports_a_disabled_add_button_instead_of_timing_out():
    page = make_campsite_page(disabled_selectors=[browser.CART_SELECTOR])
    result = browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    assert result["success"] is False
    assert "disabled" in result["error"].lower()


def test_add_single_does_not_click_a_disabled_add_button():
    page = make_campsite_page(disabled_selectors=[browser.CART_SELECTOR])
    browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    assert browser.CART_SELECTOR not in page.clicked


def test_add_single_injects_the_requested_stay_dates():
    page = make_campsite_page(url_after_cart_click=ORDER_DETAILS_URL)
    browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    session_script = page.evaluated[0]
    assert "10/12/2026" in session_script
    assert "10/14/2026" in session_script


def test_add_single_survives_a_missing_outdated_browser_banner():
    page = make_campsite_page(url_after_cart_click=ORDER_DETAILS_URL)
    result = browser._add_single(page, CAMPSITE_URL, "10-12-2026", "10-14-2026")
    assert result["success"] is True


# --------------------------------------------------------------------------
# _new_page
# --------------------------------------------------------------------------

class FakeContext:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.init_scripts = []
        self.closed = False
        self.page = None

    def add_init_script(self, script):
        self.init_scripts.append(script)

    def new_page(self):
        self.page = FakePage()
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, launch_kwargs=None, connected=True):
        self.launch_kwargs = launch_kwargs or {}
        self.contexts = []
        self._connected = connected
        self.closed = False

    def is_connected(self):
        return self._connected

    def new_context(self, **kwargs):
        context = FakeContext(kwargs)
        self.contexts.append(context)
        return context

    def close(self):
        self.closed = True

    @property
    def context(self):
        return self.contexts[-1]


class FakeChromium:
    def __init__(self):
        self.browser = None

    def launch(self, **kwargs):
        self.browser = FakeBrowser(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


class FakePlaywrightHandle:
    """Stand-in for the object returned by sync_playwright().start()."""

    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


@pytest.fixture(autouse=True)
def reset_shared_browser():
    browser.shutdown_browser(wait=False)
    yield
    browser.shutdown_browser(wait=False)


def test_launch_is_headed_by_default(monkeypatch):
    """Headless Chromium is silently rejected by Recreation.gov's bot checks."""
    monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
    p = FakePlaywright()
    browser._launch_browser(p)
    assert p.chromium.browser.launch_kwargs["headless"] is False


def test_launch_can_be_forced_headless_for_local_debugging(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")
    p = FakePlaywright()
    browser._launch_browser(p)
    assert p.chromium.browser.launch_kwargs["headless"] is True


def test_context_does_not_spoof_the_user_agent():
    """A faked UA version contradicted navigator.userAgentData and tripped detection."""
    fake = FakeBrowser()
    browser._new_context(fake)
    assert "user_agent" not in fake.context.kwargs


def test_context_does_not_spoof_client_hint_headers():
    fake = FakeBrowser()
    browser._new_context(fake)
    headers = fake.context.kwargs.get("extra_http_headers", {})
    assert not any(h.startswith("sec-ch-ua") for h in headers)


def test_context_installs_the_stealth_init_script():
    fake = FakeBrowser()
    browser._new_context(fake)
    assert fake.context.init_scripts == [browser.STEALTH_JS]


# --------------------------------------------------------------------------
# Shared browser lifecycle
#
# browser.close() never returns for headed Chromium in the sidecar container —
# it leaves zombie processes and wedges the container. So the browser is
# launched once and reused; isolation comes from a per-request context.
# --------------------------------------------------------------------------

def test_browser_is_launched_once_and_reused(mocker):
    launch = mocker.patch.object(browser, "_launch_browser", return_value=FakeBrowser())
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())
    assert browser.get_shared_browser() is browser.get_shared_browser()
    assert launch.call_count == 1


def test_browser_is_relaunched_after_it_crashes(mocker):
    dead, fresh = FakeBrowser(connected=False), FakeBrowser(connected=True)
    mocker.patch.object(browser, "_launch_browser", side_effect=[dead, fresh])
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())
    browser.get_shared_browser()
    assert browser.get_shared_browser() is fresh


def test_each_request_gets_its_own_context(mocker):
    """Contexts must not be shared — two users' credentials would mix."""
    fake = FakeBrowser()
    mocker.patch.object(browser, "_launch_browser", return_value=fake)
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())
    browser._with_page(lambda page: None)
    browser._with_page(lambda page: None)
    assert len(fake.contexts) == 2


def test_context_is_closed_after_the_work_finishes(mocker):
    fake = FakeBrowser()
    mocker.patch.object(browser, "_launch_browser", return_value=fake)
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())
    browser._with_page(lambda page: "done")
    assert fake.context.closed is True


def test_context_is_closed_when_the_work_raises(mocker):
    fake = FakeBrowser()
    mocker.patch.object(browser, "_launch_browser", return_value=fake)
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())

    def boom(page):
        raise RuntimeError("nav failed")

    with pytest.raises(RuntimeError):
        browser._with_page(boom)
    assert fake.context.closed is True


def test_the_shared_browser_is_not_closed_between_requests(mocker):
    """Closing it per request is exactly what hangs the sidecar."""
    fake = FakeBrowser()
    mocker.patch.object(browser, "_launch_browser", return_value=fake)
    mocker.patch.object(browser, "_start_playwright", return_value=FakePlaywrightHandle())
    browser._with_page(lambda page: None)
    assert fake.closed is False


def test_shutdown_stops_playwright_to_reap_chrome(mocker):
    """browser.close() never returns, but playwright.stop() reaps every chrome
    process — without it the container cannot be stopped by Docker at all."""
    handle = FakePlaywrightHandle()
    mocker.patch.object(browser, "_start_playwright", return_value=handle)
    mocker.patch.object(browser, "_launch_browser", return_value=FakeBrowser())
    browser.get_shared_browser()
    browser.shutdown_browser()
    assert handle.stopped is True


def test_shutdown_is_safe_when_no_browser_was_ever_started():
    browser.shutdown_browser()  # must not raise


def test_shutdown_survives_a_playwright_stop_failure(mocker):
    handle = FakePlaywrightHandle()
    mocker.patch.object(handle, "stop", side_effect=RuntimeError("driver gone"))
    mocker.patch.object(browser, "_start_playwright", return_value=handle)
    mocker.patch.object(browser, "_launch_browser", return_value=FakeBrowser())
    browser.get_shared_browser()
    browser.shutdown_browser()  # must not raise
    assert browser._browser_state["browser"] is None


def test_add_to_cart_returns_an_error_dict_when_the_browser_cannot_start(mocker):
    mocker.patch.object(browser, "_start_playwright", side_effect=RuntimeError("no display"))
    result = browser.add_to_cart("https://rec.gov/1", "u@e.com", "pw", "10-12-2026", "10-14-2026")
    assert result["success"] is False
    assert "no display" in result["error"]


def test_add_to_cart_batch_returns_one_error_per_site_when_the_browser_cannot_start(mocker):
    mocker.patch.object(browser, "_start_playwright", side_effect=RuntimeError("no display"))
    sites = [{"booking_url": "u1", "check_in": "10-12-2026", "check_out": "10-14-2026"},
             {"booking_url": "u2", "check_in": "10-12-2026", "check_out": "10-14-2026"}]
    results = browser.add_to_cart_batch("u@e.com", "pw", sites)
    assert len(results) == 2
    assert all(r["success"] is False for r in results)
