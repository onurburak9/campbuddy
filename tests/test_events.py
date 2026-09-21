from core.events import (
    REASON_BUTTON_DISABLED,
    REASON_LOGIN_FAILED,
    REASON_NO_REDIRECT,
    REASON_OVER_CAP,
    REASON_SIDECAR_ERROR,
    REASON_SIDECAR_UNAVAILABLE,
    REASON_UNKNOWN,
    cart_add_event,
    classify_cart_error,
    logfmt,
)


# --------------------------------------------------------------------------
# logfmt — the line has to survive Loki's parser
# --------------------------------------------------------------------------

def test_plain_values_are_not_quoted():
    assert logfmt(event="cart_add", result="success") == "event=cart_add result=success"


def test_values_with_spaces_are_quoted():
    assert logfmt(reason="no redirect") == 'reason="no redirect"'


def test_embedded_quotes_are_escaped():
    assert logfmt(error='say "hi"') == r'error="say \"hi\""'


def test_newlines_are_collapsed_to_keep_one_event_per_line():
    """Playwright errors are multi-line; unescaped they'd split into several
    Loki entries and break the logfmt parse."""
    line = logfmt(error="Timeout 30000ms exceeded.\nwaiting for locator(\"x\")")
    assert "\n" not in line
    assert line.startswith("error=")


def test_none_values_are_omitted():
    assert logfmt(event="cart_add", reason=None) == "event=cart_add"


def test_integers_are_rendered_bare():
    assert logfmt(duration_ms=18004) == "duration_ms=18004"


def test_empty_string_is_quoted_rather_than_dropped():
    assert logfmt(error="") == 'error=""'


# --------------------------------------------------------------------------
# cart_add_event
# --------------------------------------------------------------------------

def test_cart_add_event_is_tagged_for_querying():
    line = cart_add_event(result="success", scan_id=12, campsite_id="42210")
    assert "event=cart_add" in line
    assert "result=success" in line


def test_cart_add_event_carries_scan_and_campsite():
    line = cart_add_event(result="success", scan_id=12, campsite_id="42210")
    assert "scan_id=12" in line
    assert "campsite_id=42210" in line


def test_cart_add_event_includes_duration_when_known():
    line = cart_add_event(result="success", scan_id=1, campsite_id="1", duration_ms=18004)
    assert "duration_ms=18004" in line


def test_cart_add_failure_carries_a_reason_code():
    line = cart_add_event(result="failure", scan_id=1, campsite_id="1",
                          reason=REASON_BUTTON_DISABLED)
    assert f"reason={REASON_BUTTON_DISABLED}" in line


# --------------------------------------------------------------------------
# classify_cart_error — reason codes stay low-cardinality so they are safe as
# Grafana labels (and as Prometheus label values later)
# --------------------------------------------------------------------------

def test_classifies_a_disabled_add_button():
    assert classify_cart_error("Add to Cart is disabled for these dates") == REASON_BUTTON_DISABLED


def test_classifies_a_missing_order_details_redirect():
    error = "No order-details redirect after Add to Cart — still at https://rec.gov/x"
    assert classify_cart_error(error) == REASON_NO_REDIRECT


def test_classifies_a_rejected_login():
    """Recreation.gov drops the login silently; it surfaces as a timeout on the
    logged-in user marker."""
    error = ('Page.wait_for_selector: Timeout 45000ms exceeded.\n'
             'waiting for locator("button[aria-label^=\'User:\']")')
    assert classify_cart_error(error) == REASON_LOGIN_FAILED


def test_classifies_an_http_error_from_the_sidecar():
    assert classify_cart_error("HTTP 502") == REASON_SIDECAR_ERROR


def test_classifies_a_sidecar_connection_failure():
    assert classify_cart_error("[Errno 111] Connection refused") == REASON_SIDECAR_ERROR


def test_classifies_a_result_count_mismatch():
    assert classify_cart_error("result count mismatch") == REASON_SIDECAR_ERROR


def test_unrecognised_errors_fall_back_to_unknown():
    assert classify_cart_error("something nobody predicted") == REASON_UNKNOWN


def test_missing_error_is_unknown():
    assert classify_cart_error(None) == REASON_UNKNOWN


def test_reason_codes_are_all_label_safe():
    """No spaces or quotes — these become Grafana/Prometheus label values."""
    for reason in (REASON_BUTTON_DISABLED, REASON_LOGIN_FAILED, REASON_NO_REDIRECT,
                   REASON_OVER_CAP, REASON_SIDECAR_ERROR, REASON_SIDECAR_UNAVAILABLE,
                   REASON_UNKNOWN):
        assert reason == reason.strip()
        assert " " not in reason and '"' not in reason
