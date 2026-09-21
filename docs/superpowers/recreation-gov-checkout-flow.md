# Recreation.gov Checkout Flow

> **Agentic reference document.** Written for future Claude sessions working on `playwright_service/browser.py`. Covers the live site behaviour discovered through MCP-driven browser exploration in May 2026. Verify selectors are still valid before changing them — the site is a React SPA and DOM can drift.

---

## Overview

Recreation.gov is a React SPA backed by a federal API. All navigation stays on the same origin (`https://www.recreation.gov`). The checkout flow has three phases:

1. **Login** — modal on the homepage, session persisted in cookies
2. **Date selection** — pre-populate `localStorage` before navigating to the campsite page
3. **Cart add** — click a sticky footer button; page stays on campsite URL after success

---

## Phase 1: Login

### URL

Navigating to `https://www.recreation.gov/log-in` redirects to `https://www.recreation.gov/` (root) with a login modal already open. **Do not navigate to `/login`** — that path does not exist.

### Modal selectors (confirmed live)

| Element | Selector |
|---------|----------|
| Email input | `input#email` |
| Password input | `input#password` |
| Submit button | `get_by_role("button", name="Log In", exact=True)` |

The nav's sign-in control is labelled `"Sign Up / Log In"`, so an **exact** accessible-name
match on `"Log In"` resolves the modal's submit button uniquely. The old
`rec-acct-*` ids and classes were removed in the "sarsa" design-system rewrite.

### Success indicator

After a successful submit, the navbar renders a user button:

```
button[aria-label^="User:"]   →  e.g. aria-label="User: Onur Y."
```

Wait for this selector instead of watching URL changes — the URL is already `/` before and after login.

### `wait_until` strategy

Use `domcontentloaded`, not `networkidle`. Recreation.gov continuously polls background APIs; `networkidle` never fires within a 30-second timeout on this SPA.

---

## Phase 2: Date Selection via localStorage

### Why not URL parameters?

`?arrival_dt=06-01-2026&departure_dt=06-02-2026` appears to pre-select dates only when the React app already has session state (previously selected dates stored in memory). In a fresh headless session they are ignored. **Do not rely on URL parameters.**

### The localStorage key

Recreation.gov stores the current search session in:

```
localStorage key: "r1s_search_session"
```

Relevant fields (date format: `MM/DD/YYYY`):

```json
{
  "checkin_time": "06/01/2026",
  "checkout_time": "06/02/2026"
}
```

### Injection pattern

Set these fields **after login and before navigating to the campsite page**. Both pages share the same origin, so the value is available on navigation:

```python
page.evaluate("""() => {
    const s = JSON.parse(localStorage.getItem('r1s_search_session') || '{}');
    s.checkin_time = '06/01/2026';
    s.checkout_time = '06/02/2026';
    localStorage.setItem('r1s_search_session', JSON.stringify(s));
}""")
```

When the campsite page mounts, it reads this key and pre-selects the dates, causing the "Add to Cart" button to appear immediately in the sticky footer.

### Alternative: calendar clicking

If localStorage injection stops working, dates can be selected by clicking calendar cells directly. The calendar's date buttons use ARIA labels in the format:

```
"Thursday, July 16, 2026 - Available"
```

Python format string: `d.strftime("%A, %B %-d, %Y") + " - Available"`

The calendar defaults to showing the current month (left) + next month (right). Advance it with `button[aria-label="Next"]` — one click per month. To show month M that is N months ahead of today, click `max(0, N - 1)` times.

---

## Phase 3: Cart Add

### Campsite page URL

```
https://www.recreation.gov/camping/campsites/{campsite_id}
```

camply's `AvailableCampsite.booking_url` uses this format with no date parameters.

### Add to Cart button

```
#add-cart-campsite
```

This button is in a **sticky footer bar** that only renders when dates are selected. It does not appear on initial page load without date context.

### Success detection

After clicking, the page **stays on the campsite URL** — there is no navigation to `/cart` or `/checkout`. Success is indicated by the navbar cart link updating its `aria-label`:

```
a[aria-label*="in cart"]   →  e.g. "Cart - 1 item in cart."
```

When the cart is empty, the link reads `aria-label="Cart"` with no count.

### What happens next (for the user)

Recreation.gov navigates to an **Order Details** page where the user fills in occupant details and proceeds to payment. CampBuddy does not automate this step — the notification sent to the user contains the booking URL so they can complete checkout manually within the cart expiry window (typically 15 minutes).

---

## Bot Detection and Mitigations

Recreation.gov applies multiple layers of bot detection. As of May 2026, headless Chromium without mitigations triggers a **reCAPTCHA v2 checkbox** on the cart add step.

### What triggers detection

| Signal | Notes |
|--------|--------|
| `navigator.webdriver = true` | Default in Playwright headless |
| Stale Chrome version in UA | Banner: "You are using an outdated browser" |
| Missing `window.chrome` runtime | Standard headless tell |
| Instant form fill (no keystroke delay) | Behavioural signal |
| Missing `navigator.plugins`, `hardwareConcurrency`, `deviceMemory` | Fingerprint signals |

### Current mitigations (see `playwright_service/browser.py`)

1. **Headed Chromium on an Xvfb display** — the single biggest lever. Headless is
   rejected silently: the sign-in form spins for ~30 s and **no auth request is
   ever sent**. Verified on both Chromium 125 and 147.
2. **Manual `STEALTH_JS`** init script — `webdriver`, `plugins`, `languages`,
   `chrome` runtime, and `permissions.query`
3. **No user-agent override.** Spoofing the UA string while `navigator.userAgentData`
   still reported the real build produced an *"outdated browser… may prevent you
   from making purchases"* interstitial. Let the real browser identify itself and
   keep the image current instead.
4. **Human-like typing** — per-character delays (30–100 ms) via `page.keyboard.type()`
5. **Jitter delays** — random pauses between every major action (hover, click, navigation)
6. **Hover before click** on the cart button
7. **Dismiss outdated browser banner** — clicks `button:has-text('Ignore')` if present (non-fatal timeout if absent)

### If CAPTCHA returns

If a future Recreation.gov update re-enables the CAPTCHA despite the current mitigations, options are:

- **CAPTCHA solving service** — integrate CapSolver or 2captcha (adds ~2–5 s latency per solve, ~$1–3/1k solves)
- **Notify-only fallback** — disable cart add, send booking URL with pre-filled date params as a deep link for the user to click manually

---

## Key Selectors Reference

| Purpose | Selector | Notes |
|---------|----------|-------|
| Email field | `input#email` | Inside login modal |
| Password field | `input#password` | Inside login modal |
| Login submit | `role=button[name="Log In"][exact]` | Nav control is "Sign Up / Log In", so exact match disambiguates |
| Logged-in check | `button[aria-label^="User:"]` | Appears in navbar after login |
| Calendar next month | `button[aria-label="Next"]` | class `next-prev-button` |
| Calendar date | `role=button[name="{Weekday}, {Month} {Day}, {Year} - Available"]` | ARIA label on each cell |
| Add to Cart | `#add-cart-campsite` | In sticky footer, visible only when dates selected |
| Outdated browser banner | `button:has-text('Ignore')` | Dismiss it; non-fatal if absent |
| Cart link | `a#ga-global-nav-account-cart-link` | aria-label goes `"Cart"` → `"Cart - 1 item in cart."`; **cumulative — not a per-site success signal** |
| Add-to-cart success | URL contains `/camping/reservations/orderdetails` | Clicking Add to Cart navigates here; the only per-site signal |
