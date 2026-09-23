"""Diagnose why a Recreation.gov sign-in is being rejected.

Recreation.gov fails logins *silently*: the form submits, the button spins for
~30s, no auth request is ever sent, and no error is shown. `login_failed` in
the cart_add events tells you it happened but not why. This collects the
evidence needed to tell the causes apart:

  - edge/WAF block          → the page itself never loads normally
  - bot scoring (IP or      → page loads, form submits, but no auth POST
    fingerprint)              is issued and the button silently resets
  - bad credentials         → an auth POST happens and returns 4xx
  - stale selectors         → the form fields aren't found at all

Run it against the live site from the host you're debugging. No cart holds are
placed — it stops at the login step. Copy it to `/app`, not `/tmp`: a script's
own directory is what lands on sys.path, so from /tmp the `playwright_service`
package is not importable.

    docker cp playwright_service/login_diagnose.py \
        "$(docker compose ps -q playwright)":/app/login_diagnose.py
    docker compose exec -T playwright python /app/login_diagnose.py \
        --email you@example.com --password 'your-password'

Credentials are read from --email/--password or RECGOV_EMAIL/RECGOV_PASSWORD.
Pass --no-submit to probe the page without attempting a login at all.
"""
import argparse
import json
import os
import sys
import time

from playwright_service.browser import (
    CONTEXT_OPTIONS,
    EMAIL_SELECTOR,
    HEADLESS_ENV_VAR,
    LAUNCH_ARGS,
    PlaywrightTimeout,
    LOGGED_IN_SELECTOR,
    LOGIN_URL,
    PASSWORD_SELECTOR,
    STEALTH_JS,
    SUBMIT_BUTTON_NAME,
    _browser_state,
    _human_type,
    _jitter,
    _new_context,
    get_shared_browser,
    run_in_browser_thread,
    shutdown_browser,
)

# Telemetry endpoints drown out the request log; none of them are auth.
NOISE = (
    "mapbox.com", "analytics.google", "googletagmanager", "doubleclick",
    "google-analytics", "gstatic.com", "fonts.", "launchdarkly", "segment",
    "qualtrics", "adobedtm", "/pagead/", "/ccm/", "/rmkt/",
)

BLOCK_MARKERS = (
    "access denied", "reference #", "request unsuccessful", "attention required",
    "cloudflare", "akamai", "perimeterx", "incapsula", "datadome",
    "unusual traffic", "are you a robot", "verify you are human",
)


def classify(signals: dict) -> tuple[str, str]:
    """Turn collected signals into a verdict. Pure, so it can be tested."""
    if signals.get("blocked_page"):
        return ("EDGE_BLOCK",
                "The login page itself was blocked or challenged before any form "
                "interaction. This is edge/WAF level — usually the source IP.")
    if signals.get("missing_fields"):
        return ("STALE_SELECTORS",
                f"Login form fields not found: {', '.join(signals['missing_fields'])}. "
                "Recreation.gov likely changed its markup again — run selector_check.")
    if signals.get("logged_in"):
        return ("SUCCESS", "Login succeeded. Sign-in is not the problem.")
    if signals.get("auth_responses"):
        codes = ", ".join(str(r["status"]) for r in signals["auth_responses"])
        return ("AUTH_REJECTED",
                f"An auth request was sent and rejected ({codes}). The request is "
                "reaching Recreation.gov, so this points at the credentials or an "
                "account state (locked, needs verification) — not bot detection.")
    if signals.get("submitted") and not signals.get("auth_responses"):
        return ("SILENT_REJECTION",
                "The form submitted but no auth request was ever sent — the client "
                "side gave up before calling the API. This is reCAPTCHA scoring the "
                "session as a bot. The usual driver is the source IP reputation "
                "(datacenter ranges score badly) rather than anything in the page.")
    if not signals.get("submitted") and signals.get("form_rendered"):
        return ("PAGE_OK",
                "The login page renders and every field resolves. No login was "
                "attempted (--no-submit), so this says nothing about whether "
                "sign-in succeeds — rerun with credentials for that.")
    return ("UNKNOWN", "No clear signal; inspect the dump below.")


def _looks_blocked(title: str, body_text: str) -> bool:
    haystack = f"{title} {body_text}".lower()
    return any(m in haystack for m in BLOCK_MARKERS)


# Whitelist, not blocklist: a successful login returns the whole account
# object — name, home address, phone, email — alongside the JWT. Anything not
# explicitly diagnostic is withheld.
DIAGNOSTIC_KEYS = ("error", "message", "code", "detail", "reason", "title", "status")


def redact_body(text: str) -> str:
    """Keep the diagnostic fields of an auth response, drop everything else.

    Output from this tool gets pasted into chats and issues, so the error must
    survive printing while the token and PII must not.
    """
    if not text:
        return ""
    try:
        data = json.loads(text)
    except Exception:
        return text[:600]
    if not isinstance(data, dict):
        return text[:600]
    out = {}
    for k, v in data.items():
        if isinstance(v, bool) or v is None:
            # Booleans can't carry PII and flags like prompt_mfa matter here.
            out[k] = v
        elif k.lower() in DIAGNOSTIC_KEYS and isinstance(v, (str, int, float)):
            out[k] = v
        elif isinstance(v, str):
            out[k] = f"<redacted {len(v)} chars>"
        else:
            out[k] = "<redacted>"
    return json.dumps(out)[:600]


MACOS_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")


def apply_macos_identity(page, major: int) -> None:
    """Present as desktop Chrome on macOS, consistently.

    Recreation.gov posts a client-side device fingerprint with the login. Ours
    is computed on Linux in a container; a real Chrome on macOS from the same
    IP is accepted. Overriding only navigator.userAgent is what produced the
    "outdated browser" interstitial previously — the string disagreed with
    navigator.userAgentData. CDP's setUserAgentOverride sets the UA string,
    the client-hint headers and userAgentData together, so they agree.
    """
    client = page.context.new_cdp_session(page)
    client.send("Emulation.setUserAgentOverride", {
        "userAgent": MACOS_UA.format(major=major),
        "platform": "MacIntel",
        "acceptLanguage": "en-US,en;q=0.9",
        "userAgentMetadata": {
            "brands": [
                {"brand": "Not_A Brand", "version": "8"},
                {"brand": "Chromium", "version": str(major)},
                {"brand": "Google Chrome", "version": str(major)},
            ],
            "fullVersion": f"{major}.0.0.0",
            "platform": "macOS",
            "platformVersion": "14.6.0",
            "architecture": "x86",
            "model": "",
            "mobile": False,
        },
    })


def _probe(page, email, password, submit, settle, as_macos=0):
    if as_macos:
        apply_macos_identity(page, as_macos)
    signals = {"missing_fields": [], "auth_responses": [], "requests": []}

    def on_response(resp):
        url = resp.url
        if any(n in url for n in NOISE):
            return
        if resp.request.method != "POST":
            return
        entry = {"status": resp.status, "url": url[:160]}
        signals["requests"].append(entry)
        if "recreation.gov" in url:
            # The status alone doesn't say *why*. Recreation.gov returns 400
            # with no visible error in the UI, so the body is the only place
            # the reason exists. Request bodies are never read — they carry
            # the password.
            try:
                entry["body"] = redact_body(resp.text() or "")
            except Exception as e:
                entry["body"] = f"<unreadable: {e}>"
            signals["auth_responses"].append(entry)

    page.on("response", on_response)

    t0 = time.perf_counter()
    resp = page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    # /log-in is a SPA route: it redirects client-side and renders the sign-in
    # modal only after hydration. Probing straight after domcontentloaded finds
    # no fields and grecaptcha undefined — a false STALE_SELECTORS. Wait for the
    # form exactly as _login does before judging anything.
    try:
        page.wait_for_selector(EMAIL_SELECTOR, timeout=30_000)
        signals["form_rendered"] = True
    except PlaywrightTimeout:
        signals["form_rendered"] = False
    page.wait_for_timeout(2_000)

    signals["http_status"] = resp.status if resp else None
    signals["final_url"] = page.url
    signals["title"] = page.title()
    body = page.evaluate("() => document.body ? document.body.innerText.slice(0, 2000) : ''")
    signals["blocked_page"] = _looks_blocked(signals["title"], body)
    signals["page_load_s"] = round(time.perf_counter() - t0, 1)

    for label, sel in (("email", EMAIL_SELECTOR), ("password", PASSWORD_SELECTOR)):
        if page.locator(sel).count() == 0:
            signals["missing_fields"].append(f"{label} ({sel})")

    signals["captcha_nodes"] = page.evaluate(
        """() => document.querySelectorAll('[class*=captcha],[id*=captcha],iframe[src*=recaptcha],iframe[src*=hcaptcha]').length""")
    signals["grecaptcha"] = page.evaluate("() => typeof window.grecaptcha")
    signals["ua"] = page.evaluate("() => navigator.userAgent")
    signals["ua_data"] = page.evaluate(
        "() => navigator.userAgentData ? navigator.userAgentData.brands : null")
    signals["webdriver"] = page.evaluate("() => navigator.webdriver")
    signals["outdated_banner"] = page.locator("text=outdated browser").count() > 0

    if not submit or signals["missing_fields"] or signals["blocked_page"]:
        signals["submitted"] = False
        return signals

    _jitter(500, 900)
    _human_type(page, EMAIL_SELECTOR, email)
    _jitter(400, 700)
    _human_type(page, PASSWORD_SELECTOR, password)
    signals["fields_filled"] = page.evaluate(
        """() => ({email: !!document.querySelector('input#email')?.value.length,
                   password: !!document.querySelector('input#password')?.value.length})""")

    button = page.get_by_role("button", name=SUBMIT_BUTTON_NAME, exact=True)
    signals["submit_button_count"] = button.count()
    if signals["submit_button_count"] == 0:
        signals["missing_fields"].append(f"submit button ({SUBMIT_BUTTON_NAME!r})")
        signals["submitted"] = False
        return signals

    t1 = time.perf_counter()
    button.first.click()
    signals["submitted"] = True

    states = []
    for _ in range(settle // 5):
        page.wait_for_timeout(5000)
        if page.locator(PASSWORD_SELECTOR).count() == 0 or page.locator(LOGGED_IN_SELECTOR).count():
            signals["logged_in"] = True
            break
        states.append(page.evaluate(
            """() => {const f=document.querySelector('input#password');
                 if(!f) return 'modal-gone';
                 const b=Array.from(document.querySelectorAll('button'))
                   .find(x=>x.closest('form')===f.closest('form') && x.type==='submit');
                 return b ? (b.disabled?'disabled:':'') + (b.innerText||'').trim().replace(/\\s+/g,' ') : 'no-button';}"""))
    signals["button_states"] = states
    signals["settle_s"] = round(time.perf_counter() - t1, 1)
    signals["logged_in"] = bool(signals.get("logged_in"))
    signals["visible_errors"] = page.evaluate(
        """() => Array.from(document.querySelectorAll('[role=alert],[class*=error i]'))
             .map(e=>(e.innerText||'').trim()).filter(t=>t && t.length<200).slice(0,5)""")

    try:
        page.screenshot(path="/tmp/login_diagnose.png", full_page=False)
        signals["screenshot"] = "/tmp/login_diagnose.png"
    except Exception as e:
        signals["screenshot"] = f"failed: {e}"
    return signals


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", default=os.getenv("RECGOV_EMAIL"))
    p.add_argument("--password", default=os.getenv("RECGOV_PASSWORD"))
    p.add_argument("--no-submit", action="store_true", help="probe the page only")
    p.add_argument("--settle", type=int, default=60, help="seconds to watch after submit")
    p.add_argument("--as-macos", type=int, nargs="?", const=153, default=0,
                   metavar="MAJOR", help="present as macOS Chrome (default 153)")
    p.add_argument("--channel", default=None,
                   help="browser build to drive, e.g. chrome "
                        "(install first: playwright install chrome)")
    p.add_argument("--profile", default=None, metavar="DIR",
                   help="persistent profile dir, so cookies and localStorage "
                        "survive between runs")
    args = p.parse_args(argv)

    submit = not args.no_submit
    if submit and not (args.email and args.password):
        print("Need --email/--password (or RECGOV_EMAIL/RECGOV_PASSWORD), "
              "or pass --no-submit.", file=sys.stderr)
        return 2

    print(f"=== Recreation.gov login diagnosis "
          f"(channel={args.channel or 'bundled-chromium'}, "
          f"profile={args.profile or 'fresh'}) ===", flush=True)
    try:
        signals = run_in_browser_thread(lambda: _probe_in_context(
            args.email, args.password, submit, args.settle, args.as_macos,
            args.channel, args.profile))
    finally:
        shutdown_browser()

    verdict, explanation = classify(signals)
    print("\n--- signals ---")
    for k in ("http_status", "final_url", "title", "page_load_s", "form_rendered", "blocked_page",
              "missing_fields", "captcha_nodes", "grecaptcha", "webdriver",
              "outdated_banner", "ua", "ua_data", "fields_filled",
              "submit_button_count", "submitted", "button_states", "settle_s",
              "logged_in", "visible_errors", "screenshot"):
        if k in signals:
            print(f"  {k}: {json.dumps(signals[k])[:300]}")
    print(f"\n  non-telemetry POSTs: {json.dumps(signals.get('requests', []))[:600]}")
    for a in signals.get("auth_responses", []):
        print(f"\n  AUTH RESPONSE {a['status']} {a['url']}\n    body: {a.get('body', '')}")
    print(f"\n=== VERDICT: {verdict} ===\n{explanation}")
    return 0 if verdict == "SUCCESS" else 1


def _make_context(channel=None, profile_dir=None):
    """Context for the probe, optionally on a different browser build.

    Playwright's bundled Chromium renders through SwiftShader under Xvfb and
    fingerprints very differently from a real Google Chrome — which is the
    remaining difference between the browser that gets 200 from the production
    IP and the one that gets 400. `channel="chrome"` drives an actual Chrome
    install; `profile_dir` keeps cookies and localStorage between runs.

    The dedicated browser is deliberately never closed: browser.close() does
    not return for a headed Chromium here. shutdown_browser() reaps it through
    playwright.stop() when main() finishes.
    """
    get_shared_browser()  # ensures the playwright driver is running
    playwright = _browser_state["playwright"]
    headless = os.getenv(HEADLESS_ENV_VAR, "false").lower() == "true"

    if profile_dir:
        context = playwright.chromium.launch_persistent_context(
            profile_dir, headless=headless, channel=channel or None,
            args=LAUNCH_ARGS, **CONTEXT_OPTIONS)
        context.add_init_script(STEALTH_JS)
        return context
    if channel:
        browser_ = playwright.chromium.launch(
            headless=headless, channel=channel, args=LAUNCH_ARGS)
        context = browser_.new_context(**CONTEXT_OPTIONS)
        context.add_init_script(STEALTH_JS)
        return context
    return _new_context(get_shared_browser())


def _probe_in_context(email, password, submit, settle, as_macos=0,
                      channel=None, profile_dir=None):
    context = _make_context(channel, profile_dir)
    try:
        # A persistent context opens with a page already attached.
        page = context.pages[0] if context.pages else context.new_page()
        return _probe(page, email, password, submit, settle, as_macos)
    finally:
        context.close()


if __name__ == "__main__":
    sys.exit(main())
