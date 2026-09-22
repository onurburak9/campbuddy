"""A successful Recreation.gov login returns a JWT whose payload carries the
account holder's name, home address and phone number. Diagnostic output gets
pasted into chats and issues, so the token must never survive printing while
the diagnostically useful parts must.
"""
import json

from playwright_service.login_diagnose import redact_body


def test_access_token_is_not_printed():
    body = json.dumps({"access_token": "eyJhbGciOiJSUzI1NiJ9.PAYLOAD.SIG"})
    assert "eyJhbGciOiJSUzI1NiJ9" not in redact_body(body)


def test_redaction_notes_that_a_token_was_present():
    out = redact_body(json.dumps({"access_token": "x" * 40}))
    assert "redacted" in out
    assert "40" in out


def test_refresh_and_id_tokens_are_redacted_too():
    out = redact_body(json.dumps({"refresh_token": "a" * 20, "id_token": "b" * 20}))
    assert "aaaa" not in out
    assert "bbbb" not in out


def test_the_error_message_survives():
    """This is the whole point of capturing the body."""
    assert "additional challenge required" in redact_body(
        '{"error":"additional challenge required"}')


def test_diagnostic_fields_survive():
    out = redact_body(json.dumps({"error": "bad", "code": 400}))
    assert "bad" in out and "400" in out


def test_the_account_object_is_withheld():
    """A successful login returns name, home address, phone and email."""
    body = json.dumps({"access_token": "t" * 30, "account": {
        "email": "someone@example.com", "home_address": {"address1": "310 Main St"},
        "cell_phone": "(555) 123-4567", "last_name": "SURNAME"}})
    out = redact_body(body)
    for leaked in ("310 Main St", "someone@example.com", "555", "SURNAME"):
        assert leaked not in out


def test_unknown_string_fields_are_withheld():
    assert "sekrit" not in redact_body(json.dumps({"session": "sekrit"}))


def test_non_json_body_is_passed_through_truncated():
    assert redact_body("<html>Gateway Timeout</html>").startswith("<html>")


def test_empty_body_is_empty():
    assert redact_body("") == ""


def test_json_array_body_does_not_crash():
    assert redact_body('[1,2,3]') == "[1,2,3]"


def test_long_bodies_are_truncated():
    assert len(redact_body("z" * 5000)) <= 600


def test_boolean_flags_survive():
    """prompt_mfa tells us whether Recreation.gov wanted a second factor."""
    out = redact_body(json.dumps({"prompt_mfa": False, "is_guest": True}))
    assert '"prompt_mfa": false' in out
    assert '"is_guest": true' in out
