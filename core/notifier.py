import logging
import smtplib
from dataclasses import dataclass
from datetime import date
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    facility_name: str
    site_name: str
    campsite_type: str
    booking_date: date
    booking_end_date: date
    booking_url: str
    cart_added: bool
    nights: int


def _format_dates(p: NotificationPayload) -> str:
    start = f"{p.booking_date.strftime('%b')} {p.booking_date.day}"
    end = f"{p.booking_end_date.strftime('%b')} {p.booking_end_date.day}"
    return f"{start} - {end}"


def send_email(to: str, payload: NotificationPayload, settings) -> None:
    dates = _format_dates(payload)
    cart_line = (
        "Added to cart - complete payment within ~15 min"
        if payload.cart_added
        else "Could not add to cart automatically - book manually now"
    )
    body = (
        f"Site:   {payload.facility_name} - Site {payload.site_name} ({payload.campsite_type})\n"
        f"Dates:  {dates} ({payload.nights} nights)\n"
        f"Status: {cart_line}\n\n"
        f"Book here: {payload.booking_url}\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = f"Campsite available - {payload.facility_name} [{dates}]"

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Email sent to %s", to)


def send_telegram(chat_id: str, payload: NotificationPayload, settings) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not set, skipping")
        return
    dates = _format_dates(payload)
    cart_line = (
        "✅ Added to cart — complete payment within ~15 min"
        if payload.cart_added
        else "⚠️ Could not add to cart automatically — book manually now"
    )
    text = (
        f"🏕 Campsite available!\n"
        f"{payload.facility_name} — Site {payload.site_name}\n"
        f"{dates} ({payload.nights} nights) · {payload.campsite_type}\n\n"
        f"{cart_line}\n"
        f"🔗 {payload.booking_url}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram API returned {resp.status_code}")


def _digest_subject(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)
    facilities = list(dict.fromkeys(p.facility_name for p in payloads))
    header = facilities[0] if len(facilities) == 1 else f"{len(facilities)} campgrounds"
    subject = f"{n} sites available — {header}"

    date_ranges = list(dict.fromkeys((p.booking_date, p.booking_end_date) for p in payloads))
    if len(date_ranges) == 1:
        start, end = date_ranges[0]
        month = start.strftime("%b")
        subject += f" [{month} {start.day}-{end.day}]"

    return subject


def _digest_body(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)
    lines = [f"{n} campsites available\n"]

    by_facility: dict[str, list[NotificationPayload]] = {}
    for p in payloads:
        by_facility.setdefault(p.facility_name, []).append(p)

    for facility, group in by_facility.items():
        lines.append("")
        lines.append(facility)
        for p in group:
            prefix = "[IN CART - book within 15 min] " if p.cart_added else ""
            dates = _format_dates(p)
            lines.append(
                f"  {prefix}Site {p.site_name} ({p.campsite_type})  {dates}  {p.booking_url}"
            )

    lines.append("\nAuto-cart was not attempted or failed for these sites - book manually.")
    return "\n".join(lines) + "\n"


def send_email_digest(to: str, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    body = _digest_body(payloads)
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = _digest_subject(payloads)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Digest email sent to %s (%d sites)", to, len(payloads))


def notify(scan, payload: NotificationPayload, settings) -> None:
    if scan.notify_via_email and scan.user.email:
        try:
            send_email(scan.user.email, payload, settings)
        except Exception as e:
            logger.error("Email notification failed: %s", e)

    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram(scan.user.telegram_chat_id, payload, settings)
        except Exception as e:
            logger.error("Telegram notification failed: %s", e)
