"""Structured events for Grafana/Loki.

Container stdout ships to Loki, but the app emits no metrics, so cart-add
outcomes were invisible: `cart_added=False` could mean "tried and failed",
"skipped over the cap", or "sidecar down", with no way to tell which.

These lines are logfmt so `| logfmt` parses them in LogQL:

    sum by (reason) (count_over_time(
      {container="campbuddy-app-1"} | logfmt
      | event="cart_add" | result="failure" [1h]))

`reason` is deliberately a small closed set — it is used as a Grafana label
and would become a Prometheus label value if counters are added later, so it
must never carry free text. The raw message is kept separately, in the log
line's `error` field and on `ScanResult.cart_error`.
"""
import re

CART_ADD_EVENT = "cart_add"

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
RESULT_SKIPPED = "skipped"

REASON_BUTTON_DISABLED = "button_disabled"
REASON_NO_REDIRECT = "no_redirect"
REASON_LOGIN_FAILED = "login_failed"
REASON_SIDECAR_UNAVAILABLE = "sidecar_unavailable"
REASON_NO_CREDENTIALS = "no_credentials"
REASON_SIDECAR_ERROR = "sidecar_error"
REASON_OVER_CAP = "over_cap"
REASON_UNKNOWN = "unknown"

_WHITESPACE = re.compile(r"\s+")
_NEEDS_QUOTING = re.compile(r'[\s"=]')


def logfmt(**fields) -> str:
    """Render fields as a single-line logfmt string. `None` values are dropped."""
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        text = _WHITESPACE.sub(" ", str(value)).strip()
        if text == "" or _NEEDS_QUOTING.search(text):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            text = f'"{escaped}"'
        parts.append(f"{key}={text}")
    return " ".join(parts)


def cart_add_event(
    result: str,
    scan_id: int,
    campsite_id: str | None = None,
    reason: str | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    **extra,
) -> str:
    """One line describing the outcome of a cart-add attempt."""
    return logfmt(
        event=CART_ADD_EVENT,
        result=result,
        scan_id=scan_id,
        campsite_id=campsite_id,
        reason=reason,
        duration_ms=duration_ms,
        **extra,
        error=error,
    )


def classify_cart_error(error: str | None) -> str:
    """Map a sidecar error message onto a low-cardinality reason code."""
    if not error:
        return REASON_UNKNOWN
    text = error.lower()
    if "disabled" in text:
        return REASON_BUTTON_DISABLED
    if "order-details redirect" in text:
        return REASON_NO_REDIRECT
    # The logged-in marker is the last step of login, so a timeout waiting for
    # it means Recreation.gov rejected the sign-in rather than erroring.
    if "user:" in text or "input#password" in text or "log in" in text:
        return REASON_LOGIN_FAILED
    if (
        "http " in text
        or "connection" in text
        or "count mismatch" in text
        or "connect" in text
    ):
        return REASON_SIDECAR_ERROR
    return REASON_UNKNOWN
