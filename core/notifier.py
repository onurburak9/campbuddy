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
    noun = "site" if n == 1 else "sites"
    subject = f"{n} {noun} available — {header}"

    date_ranges = list(dict.fromkeys((p.booking_date, p.booking_end_date) for p in payloads))
    if len(date_ranges) == 1:
        start, end = date_ranges[0]
        if start.month == end.month:
            subject += f" [{start.strftime('%b')} {start.day}-{end.day}]"
        else:
            subject += f" [{start.strftime('%b')} {start.day}-{end.strftime('%b')} {end.day}]"

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

    has_carted = any(p.cart_added for p in payloads)
    if has_carted:
        lines.append("\nSites marked [IN CART] are already in your Recreation.gov cart — complete payment within ~15 min.")
    else:
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


def _telegram_digest_body(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)

    date_ranges = list(dict.fromkeys((p.booking_date, p.booking_end_date) for p in payloads))
    date_suffix = ""
    if len(date_ranges) == 1:
        start, end = date_ranges[0]
        if start.month == end.month:
            date_suffix = f" [{start.strftime('%b')} {start.day}-{end.day}]"
        else:
            date_suffix = f" [{start.strftime('%b')} {start.day}-{end.strftime('%b')} {end.day}]"

    noun = "site" if n == 1 else "sites"
    header = f"🏕 {n} {noun} available{date_suffix}"

    by_facility: dict[str, list[NotificationPayload]] = {}
    for p in payloads:
        by_facility.setdefault(p.facility_name, []).append(p)

    has_carted = any(p.cart_added for p in payloads)
    footer = (
        "✅ Complete payment within ~15 min"
        if has_carted
        else "⚠️ Book manually"
    )

    LIMIT = 4000
    SUFFIX_RESERVE = 80

    all_lines: list[str] = [header, ""]
    for facility, group in by_facility.items():
        all_lines.append(facility)
        for p in group:
            prefix = "  ✅ " if p.cart_added else "  "
            all_lines.append(f"{prefix}Site {p.site_name} — {p.booking_url}")

    body = "\n".join(all_lines)
    if len(body) + 1 + len(footer) <= LIMIT:
        return body + "\n" + footer

    included_count = 0
    site_lines_total = sum(len(g) for g in by_facility.values())
    accumulated = ""

    for line in all_lines:
        candidate = (accumulated + "\n" + line) if accumulated else line
        is_site_line = line.startswith("  ✅ Site ") or line.startswith("  Site ")
        suffix_needed = SUFFIX_RESERVE
        if len(candidate) + suffix_needed > LIMIT:
            break
        accumulated = candidate
        if is_site_line:
            included_count += 1

    remaining = site_lines_total - included_count
    truncation_suffix = f"\n... and {remaining} more — see email."
    # footer omitted in truncated path — the "see email" suffix serves the same purpose
    return accumulated + truncation_suffix


def send_telegram_digest(chat_id: str, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    if not settings.telegram_bot_token:
        logger.warning("Telegram token not set, skipping digest")
        return
    text = _telegram_digest_body(payloads)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram API returned {resp.status_code}")
    logger.info("Digest Telegram sent to %s (%d sites)", chat_id, len(payloads))


def _available_subject(payloads: list[NotificationPayload]) -> str:
    n = len(payloads)
    noun = "site" if n == 1 else "sites"
    facilities = list(dict.fromkeys(p.facility_name for p in payloads))
    header = facilities[0] if len(facilities) == 1 else f"{len(facilities)} campgrounds"
    return f"{n} {noun} available — {header}"


def _available_body(payloads: list[NotificationPayload], auto_book: bool) -> str:
    n = len(payloads)
    lines = [f"{n} campsites available — book now\n"]
    by_facility: dict[str, list[NotificationPayload]] = {}
    for p in payloads:
        by_facility.setdefault(p.facility_name, []).append(p)
    for facility, group in by_facility.items():
        lines.append("")
        lines.append(facility)
        for p in group:
            lines.append(f"  Site {p.site_name} ({p.campsite_type})  {_format_dates(p)}  {p.booking_url}")
    if auto_book:
        lines.append("\nAuto-booking is in progress — a follow-up email will confirm which sites made it into your cart.")
    return "\n".join(lines) + "\n"


def send_email_available(to: str, payloads: list[NotificationPayload], settings, auto_book: bool) -> None:
    if not payloads:
        return
    msg = MIMEText(_available_body(payloads, auto_book), "plain", "utf-8")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = _available_subject(payloads)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Available email sent to %s (%d sites)", to, len(payloads))


def send_telegram_available(chat_id: str, payloads: list[NotificationPayload], settings, auto_book: bool) -> None:
    if not payloads or not settings.telegram_bot_token:
        return
    n = len(payloads)
    noun = "site" if n == 1 else "sites"
    lines = [f"🏕 {n} {noun} available — book now", ""]
    for p in payloads:
        lines.append(f"  Site {p.site_name} — {p.booking_url}")
    if auto_book:
        lines.append("\n⏳ Auto-booking in progress — follow-up coming.")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": "\n".join(lines)}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram API returned {resp.status_code}")


def notify_available(scan, payloads: list[NotificationPayload], settings) -> None:
    if not payloads:
        return
    if scan.notify_via_email and scan.user.email:
        try:
            send_email_available(scan.user.email, payloads, settings, scan.auto_book)
        except Exception as e:
            logger.error("Available email failed: %s", e)
    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram_available(scan.user.telegram_chat_id, payloads, settings, scan.auto_book)
        except Exception as e:
            logger.error("Available Telegram failed: %s", e)


def notify_cart_results(scan, payloads: list[NotificationPayload], settings, sidecar_available: bool = True) -> None:
    if not payloads:
        return
    if not sidecar_available:
        # Nothing was carted; reuse the "available" phrasing but flag the outage.
        if scan.notify_via_email and scan.user.email:
            try:
                send_email_available(scan.user.email, payloads, settings, auto_book=False)
            except Exception as e:
                logger.error("Cart-results (unavailable) email failed: %s", e)
        if scan.notify_via_telegram and scan.user.telegram_chat_id:
            try:
                send_telegram_available(scan.user.telegram_chat_id, payloads, settings, auto_book=False)
            except Exception as e:
                logger.error("Cart-results (unavailable) Telegram failed: %s", e)
        return
    if scan.notify_via_email and scan.user.email:
        try:
            send_email_digest(scan.user.email, payloads, settings)
        except Exception as e:
            logger.error("Cart-results email failed: %s", e)
    if scan.notify_via_telegram and scan.user.telegram_chat_id:
        try:
            send_telegram_digest(scan.user.telegram_chat_id, payloads, settings)
        except Exception as e:
            logger.error("Cart-results Telegram failed: %s", e)


