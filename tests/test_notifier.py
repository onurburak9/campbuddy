from datetime import date
from unittest.mock import MagicMock

import pytest

from core.notifier import NotificationPayload, notify, send_email, send_telegram


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
    raw = instance.sendmail.call_args[0][2]
    assert "https://www.recreation.gov/camping/campsites/10357088" in raw
    assert "Added to cart" in raw


def test_email_fallback_message_when_cart_failed(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_email("to@example.com", make_payload(cart_added=False), make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert "book manually" in raw.lower()
    assert "https://www.recreation.gov/camping/campsites/10357088" in raw


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
