import smtplib
import logging
import requests
from dataclasses import dataclass
from datetime import date
from email.mime.text import MIMEText

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


def _format_dates(p: NotificationPayload, ascii_only: bool = False) -> str:
    sep = " - " if ascii_only else " – "
    return f"{p.booking_date.strftime('%b %-d')}{sep}{p.booking_end_date.strftime('%b %-d')}"


def send_email(to: str, payload: NotificationPayload, settings) -> None:
    dates = _format_dates(payload, ascii_only=True)
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
    msg = MIMEText(body, "plain", "us-ascii")
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
        logger.error("Telegram failed: %s", resp.text)


def notify(scan, payload: NotificationPayload, settings) -> None:
    if scan.notify_via_email and scan.user.email:
        try:
            send_email(scan.user.email, payload, settings)
        except Exception as e:
            logger.error("Email error: %s", e)

    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram(scan.user.telegram_chat_id, payload, settings)
        except Exception as e:
            logger.error("Telegram error: %s", e)
