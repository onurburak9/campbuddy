"""The classifier turns collected signals into a diagnosis, so a wrong verdict
sends the investigation down the wrong path. These pin each branch.
"""
from playwright_service.login_diagnose import _looks_blocked, classify


def verdict(**signals):
    return classify(signals)[0]


def test_success_when_logged_in():
    assert verdict(logged_in=True, submitted=True) == "SUCCESS"


def test_edge_block_when_the_page_itself_is_challenged():
    assert verdict(blocked_page=True) == "EDGE_BLOCK"


def test_edge_block_outranks_a_missing_form():
    """A block page has no login form; reporting stale selectors would mislead."""
    assert verdict(blocked_page=True, missing_fields=["email (input#email)"]) == "EDGE_BLOCK"


def test_stale_selectors_when_fields_are_absent():
    assert verdict(missing_fields=["password (input#password)"]) == "STALE_SELECTORS"


def test_auth_rejected_when_an_auth_request_came_back_4xx():
    """A response from the server means the request got through — not bot scoring."""
    assert verdict(submitted=True, auth_responses=[{"status": 401, "url": "x"}]) == "AUTH_REJECTED"


def test_silent_rejection_when_submitted_but_no_auth_request():
    assert verdict(submitted=True, auth_responses=[]) == "SILENT_REJECTION"


def test_page_ok_when_probing_without_a_login_attempt():
    """--no-submit on a healthy page is a clean result, not an inconclusive one."""
    assert verdict(submitted=False, auth_responses=[], form_rendered=True) == "PAGE_OK"


def test_page_ok_requires_the_form_to_have_rendered():
    """The login form is rendered client-side; a probe that ran too early must
    not be reported as a healthy page."""
    assert verdict(submitted=False, auth_responses=[], form_rendered=False) == "UNKNOWN"


def test_success_takes_priority_over_a_stray_auth_response():
    assert verdict(logged_in=True, auth_responses=[{"status": 200, "url": "x"}]) == "SUCCESS"


def test_explanation_names_the_missing_selector():
    _, why = classify({"missing_fields": ["password (input#password)"]})
    assert "input#password" in why


def test_explanation_names_the_rejected_status():
    _, why = classify({"submitted": True, "auth_responses": [{"status": 403, "url": "x"}]})
    assert "403" in why


# --- block-page detection ---

def test_detects_a_cloudflare_challenge():
    assert _looks_blocked("Attention Required! | Cloudflare", "") is True


def test_detects_an_akamai_reference_id():
    assert _looks_blocked("Access Denied", "Reference #18.1c2 You don't have permission") is True


def test_detects_a_human_verification_prompt():
    assert _looks_blocked("", "Please verify you are human before continuing") is True


def test_normal_login_page_is_not_flagged():
    assert _looks_blocked(
        "Recreation.gov", "Log In to Recreation.gov Email Password Forgot Your Password?"
    ) is False
