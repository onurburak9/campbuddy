from datetime import date
from email import message_from_string
from email.header import decode_header, make_header
from unittest.mock import MagicMock

import pytest

from core.notifier import (
    NotificationPayload,
    notify,
    send_email,
    send_email_digest,
    send_telegram,
)


def _decode_email_body(raw: str) -> str:
    return message_from_string(raw).get_payload(decode=True).decode("utf-8")


def _decode_subject(raw_msg_string: str) -> str:
    msg = message_from_string(raw_msg_string)
    return str(make_header(decode_header(msg["Subject"])))


def make_settings(**overrides):
    s = MagicMock()
    s.smtp_host = "smtp.example.com"
    s.smtp_port = 587
    s.smtp_user = "from@example.com"
    s.smtp_password = "pass"
    s.smtp_from = "CampBuddy <from@example.com>"
    s.telegram_bot_token = "bot123:token"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def make_payload(cart_added=True):
    return NotificationPayload(
        facility_name="Union West",
        site_name="1",
        campsite_type="STANDARD NONELECTRIC",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://www.recreation.gov/camping/campsites/10357088",
        cart_added=cart_added,
        nights=3,
    )


def test_email_contains_booking_url_and_cart_status(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_email("to@example.com", make_payload(cart_added=True), make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "https://www.recreation.gov/camping/campsites/10357088" in body
    assert "Added to cart" in body


def test_email_fallback_message_when_cart_failed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_email("to@example.com", make_payload(cart_added=False), make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "book manually" in body.lower()
    assert "https://www.recreation.gov/camping/campsites/10357088" in body


def test_telegram_contains_booking_url(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    send_telegram("123456", make_payload(), make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert "https://www.recreation.gov/camping/campsites/10357088" in text
    assert "Union West" in text


def test_telegram_skips_when_no_token(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    send_telegram("123456", make_payload(), make_settings(telegram_bot_token=""))
    mock_post.assert_not_called()


def test_telegram_raises_on_api_error(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = False
    mock_post.return_value.status_code = 403
    with pytest.raises(RuntimeError, match="403"):
        send_telegram("123456", make_payload(), make_settings())


def test_notify_dispatches_both_channels(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_tg = mocker.patch("core.notifier.send_telegram")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = "123456"
    payload = make_payload()
    settings = make_settings()
    notify(scan, payload, settings)
    mock_email.assert_called_once_with("user@example.com", payload, settings)
    mock_tg.assert_called_once_with("123456", payload, settings)


def test_notify_skips_telegram_when_no_chat_id(mocker):
    mock_email = mocker.patch("core.notifier.send_email")
    mock_tg = mocker.patch("core.notifier.send_telegram")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = None
    notify(scan, make_payload(), make_settings())
    mock_email.assert_called_once()
    mock_tg.assert_not_called()


def test_notify_catches_email_failure(mocker):
    mocker.patch("core.notifier.send_email", side_effect=RuntimeError("SMTP down"))
    mock_tg = mocker.patch("core.notifier.send_telegram")
    scan = MagicMock()
    scan.notify_via_email = True
    scan.notify_via_telegram = True
    scan.user.email = "user@example.com"
    scan.user.telegram_chat_id = "123456"
    notify(scan, make_payload(), make_settings())
    mock_tg.assert_called_once()


# ---------------------------------------------------------------------------
# Digest helpers
# ---------------------------------------------------------------------------


def make_payload_at(
    facility="Chilkoot",
    site="23",
    check_in=date(2026, 7, 16),
    check_out=date(2026, 7, 18),
    cart_added=False,
):
    return NotificationPayload(
        facility_name=facility,
        site_name=site,
        campsite_type="STANDARD NONELECTRIC",
        booking_date=check_in,
        booking_end_date=check_out,
        booking_url=f"https://www.recreation.gov/camping/campsites/{site}",
        cart_added=cart_added,
        nights=2,
    )


def test_digest_email_subject_single_facility(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(site=str(i)) for i in range(21)]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert _decode_subject(raw) == "21 sites available — Chilkoot [Jul 16-18]"


def test_digest_email_subject_multiple_facilities(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(facility="Chilkoot", site="1"),
        make_payload_at(facility="Chilkoot", site="2"),
        make_payload_at(facility="Forks", site="3"),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert _decode_subject(raw) == "3 sites available — 2 campgrounds [Jul 16-18]"


def test_digest_email_subject_omits_dates_when_mixed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(site="1", check_in=date(2026, 7, 16), check_out=date(2026, 7, 18)),
        make_payload_at(site="2", check_in=date(2026, 7, 20), check_out=date(2026, 7, 22)),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    subject = _decode_subject(raw)
    assert "[" not in subject
    assert subject == "2 sites available — Chilkoot"


def test_digest_email_body_groups_by_facility(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(facility="Chilkoot", site="10"),
        make_payload_at(facility="Chilkoot", site="11"),
        make_payload_at(facility="Forks", site="99"),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "Chilkoot" in body
    assert "Forks" in body
    assert "Site 10" in body
    assert "Site 11" in body
    assert "Site 99" in body
    assert body.index("Chilkoot") < body.index("Forks")
    assert "https://www.recreation.gov/camping/campsites/10" in body
    assert "https://www.recreation.gov/camping/campsites/99" in body


def test_digest_email_marks_carted_fallback_rows(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [
        make_payload_at(site="1", cart_added=True),
        make_payload_at(site="2", cart_added=False),
    ]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    lines = body.splitlines()
    carted_line = next(l for l in lines if "Site 1" in l)
    not_carted_line = next(l for l in lines if "Site 2" in l)
    assert "IN CART" in carted_line
    assert "IN CART" not in not_carted_line


def test_digest_email_noop_when_empty(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    send_email_digest("to@example.com", [], make_settings())
    mock_smtp.assert_not_called()


def test_digest_email_one_smtp_send_for_many_sites(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(site=str(i)) for i in range(50)]
    send_email_digest("to@example.com", payloads, make_settings())
    assert instance.sendmail.call_count == 1
