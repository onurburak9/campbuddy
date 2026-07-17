from datetime import date
from email import message_from_string
from email.header import decode_header, make_header
from unittest.mock import MagicMock

import pytest

from core.notifier import (
    NotificationPayload,
    _available_body,
    notify_available,
    notify_cart_results,
    send_email,
    send_email_digest,
    send_password_reset_email,
    send_telegram,
    send_telegram_digest,
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


def test_password_reset_email_contains_reset_url(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_password_reset_email(
        "to@example.com", "https://app.example.com/reset-password?token=abc123", make_settings()
    )
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "https://app.example.com/reset-password?token=abc123" in body


def test_password_reset_email_sent_to_correct_recipient(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    send_password_reset_email(
        "to@example.com", "https://app.example.com/reset-password?token=abc123", make_settings()
    )
    from_addr, to_addr, _ = instance.sendmail.call_args[0]
    assert from_addr == "CampBuddy <from@example.com>"
    assert to_addr == "to@example.com"


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


def test_digest_email_subject_cross_month_dates(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(check_in=date(2026, 7, 30), check_out=date(2026, 8, 1))]
    send_email_digest("to@example.com", payloads, make_settings())
    raw = instance.sendmail.call_args[0][2]
    assert _decode_subject(raw) == "1 site available — Chilkoot [Jul 30-Aug 1]"


def test_digest_email_footer_when_all_carted_fallback(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(cart_added=True), make_payload_at(site="24", cart_added=True)]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "complete payment within" in body
    assert "book manually" not in body


def test_digest_email_footer_when_no_carted(mocker):
    mock_smtp = mocker.patch("core.notifier.smtplib.SMTP")
    instance = mock_smtp.return_value.__enter__.return_value
    payloads = [make_payload_at(cart_added=False)]
    send_email_digest("to@example.com", payloads, make_settings())
    body = _decode_email_body(instance.sendmail.call_args[0][2])
    assert "book manually" in body
    assert "complete payment within" not in body


# ---------------------------------------------------------------------------
# Digest Telegram
# ---------------------------------------------------------------------------


def test_digest_telegram_lists_all_sites(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    payloads = [
        make_payload_at(facility="Chilkoot", site="23"),
        make_payload_at(facility="Chilkoot", site="24"),
        make_payload_at(facility="Forks", site="5"),
    ]
    send_telegram_digest("123456", payloads, make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert "3 sites available" in text
    assert "Chilkoot" in text
    assert "Forks" in text
    assert "https://www.recreation.gov/camping/campsites/23" in text
    assert "https://www.recreation.gov/camping/campsites/5" in text


def test_digest_telegram_skips_when_no_token(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    payloads = [make_payload_at()]
    send_telegram_digest("123456", payloads, make_settings(telegram_bot_token=""))
    mock_post.assert_not_called()


def test_digest_telegram_noop_when_empty(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    send_telegram_digest("123456", [], make_settings())
    mock_post.assert_not_called()


def test_digest_telegram_truncates_long_message(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    payloads = [make_payload_at(site=str(i)) for i in range(200)]
    send_telegram_digest("123456", payloads, make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert len(text) <= 4096
    assert "more — see email" in text


def test_digest_telegram_raises_on_api_error(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = False
    mock_post.return_value.status_code = 429
    with pytest.raises(RuntimeError, match="429"):
        send_telegram_digest("123456", [make_payload_at()], make_settings())


def test_digest_telegram_cross_month_dates(mocker):
    mock_post = mocker.patch("core.notifier.requests.post")
    mock_post.return_value.ok = True
    payloads = [make_payload_at(check_in=date(2026, 7, 30), check_out=date(2026, 8, 1))]
    send_telegram_digest("123456", payloads, make_settings())
    text = mock_post.call_args[1]["json"]["text"]
    assert "Jul 30-Aug 1" in text


# ---------------------------------------------------------------------------
# Two-phase notifier: notify_available / notify_cart_results
# ---------------------------------------------------------------------------


def _payload(cart_added=False):
    return NotificationPayload(
        facility_name="Big Meadow", site_name="07", campsite_type="STANDARD",
        booking_date=date(2026, 7, 11), booking_end_date=date(2026, 7, 13),
        booking_url="https://rec.gov/1", cart_added=cart_added, nights=2,
    )


def _scan(auto_book=False, email=True, telegram=False):
    s = MagicMock()
    s.auto_book = auto_book
    s.notify_via_email = email
    s.notify_via_telegram = telegram
    s.user.email = "u@e.com"
    s.user.telegram_chat_id = "123" if telegram else None
    return s


def test_notify_available_sends_email(mocker):
    send = mocker.patch("core.notifier.send_email_available")
    notify_available(_scan(), [_payload()], MagicMock())
    send.assert_called_once()


def test_notify_available_skips_email_when_disabled(mocker):
    send = mocker.patch("core.notifier.send_email_available")
    notify_available(_scan(email=False), [_payload()], MagicMock())
    send.assert_not_called()


def test_notify_cart_results_sends_digest_email(mocker):
    send = mocker.patch("core.notifier.send_email_digest")
    notify_cart_results(_scan(), [_payload(cart_added=True)], MagicMock())
    send.assert_called_once()


def test_notify_available_swallows_send_error(mocker):
    mocker.patch("core.notifier.send_email_available", side_effect=RuntimeError("smtp"))
    # must not raise
    notify_available(_scan(), [_payload()], MagicMock())


def test_notify_cart_results_unavailable_sends_telegram(mocker):
    mocker.patch("core.notifier.send_email_available")
    send_tg = mocker.patch("core.notifier.send_telegram_available")
    notify_cart_results(
        _scan(email=False, telegram=True), [_payload()], MagicMock(), sidecar_available=False
    )
    send_tg.assert_called_once()


def test_notify_available_sends_telegram(mocker):
    send_tg = mocker.patch("core.notifier.send_telegram_available")
    notify_available(_scan(telegram=True), [_payload()], MagicMock())
    send_tg.assert_called_once()


def test_notify_available_skips_telegram_when_disabled(mocker):
    send_tg = mocker.patch("core.notifier.send_telegram_available")
    notify_available(_scan(telegram=False), [_payload()], MagicMock())
    send_tg.assert_not_called()


def test_notify_cart_results_sends_digest_telegram(mocker):
    mocker.patch("core.notifier.send_email_digest")
    send_tg = mocker.patch("core.notifier.send_telegram_digest")
    notify_cart_results(_scan(telegram=True), [_payload(cart_added=True)], MagicMock())
    send_tg.assert_called_once()


def test_notify_cart_results_unavailable_sends_email(mocker):
    send_email = mocker.patch("core.notifier.send_email_available")
    mocker.patch("core.notifier.send_telegram_available")
    notify_cart_results(_scan(email=True), [_payload()], MagicMock(), sidecar_available=False)
    send_email.assert_called_once()


def test_notify_cart_results_unavailable_does_not_send_carted_digests(mocker):
    mock_email_avail = mocker.patch("core.notifier.send_email_available")
    mock_tg_avail = mocker.patch("core.notifier.send_telegram_available")
    mock_email_digest = mocker.patch("core.notifier.send_email_digest")
    mock_tg_digest = mocker.patch("core.notifier.send_telegram_digest")
    notify_cart_results(
        _scan(email=True, telegram=True), [_payload()], MagicMock(), sidecar_available=False
    )
    mock_email_avail.assert_called_once()
    mock_tg_avail.assert_called_once()
    mock_email_digest.assert_not_called()
    mock_tg_digest.assert_not_called()


def test_notify_cart_results_swallows_send_error(mocker):
    mocker.patch("core.notifier.send_email_digest", side_effect=RuntimeError("smtp down"))
    # must not raise
    notify_cart_results(_scan(), [_payload(cart_added=True)], MagicMock())


def test_notify_cart_results_unavailable_swallows_send_error(mocker):
    mocker.patch("core.notifier.send_email_available", side_effect=RuntimeError("smtp down"))
    mocker.patch("core.notifier.send_telegram_available", side_effect=RuntimeError("tg down"))
    # must not raise
    notify_cart_results(
        _scan(email=True, telegram=True), [_payload()], MagicMock(), sidecar_available=False
    )


def test_available_body_contains_auto_book_followup_line():
    body = _available_body([_payload()], auto_book=True)
    assert "Auto-booking is in progress" in body


def test_available_body_omits_auto_book_followup_line_when_false():
    body = _available_body([_payload()], auto_book=False)
    assert "Auto-booking is in progress" not in body


def test_notify_available_noop_when_empty(mocker):
    mock_email = mocker.patch("core.notifier.send_email_available")
    mock_tg = mocker.patch("core.notifier.send_telegram_available")
    notify_available(_scan(telegram=True), [], MagicMock())
    mock_email.assert_not_called()
    mock_tg.assert_not_called()


def test_notify_cart_results_noop_when_empty(mocker):
    mock_email_avail = mocker.patch("core.notifier.send_email_available")
    mock_tg_avail = mocker.patch("core.notifier.send_telegram_available")
    mock_email_digest = mocker.patch("core.notifier.send_email_digest")
    mock_tg_digest = mocker.patch("core.notifier.send_telegram_digest")
    notify_cart_results(_scan(telegram=True), [], MagicMock())
    mock_email_avail.assert_not_called()
    mock_tg_avail.assert_not_called()
    mock_email_digest.assert_not_called()
    mock_tg_digest.assert_not_called()
