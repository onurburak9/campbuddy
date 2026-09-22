import logging
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from db.models import Scan, ScanRun, ScanResult, ScanStatus
from db.session import get_db
from core.availability import active_windows, check_availability
from core.booking import attempt_cart_add_batch, sidecar_healthy
from core.crypto import decrypt_password
from core.events import (
    REASON_NO_CREDENTIALS,
    REASON_OVER_CAP,
    REASON_SIDECAR_UNAVAILABLE,
    RESULT_FAILURE,
    RESULT_SKIPPED,
    RESULT_SUCCESS,
    cart_add_event,
    classify_cart_error,
)
from core.notifier import (
    notify_available,
    notify_cart_results,
    notify_scan_stopped,
    NotificationPayload,
)

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _as_date(value):
    return value.date() if hasattr(value, "date") else value


def run_scan(scan_id: int, session_factory, settings) -> None:
    # TX1: load config, start run
    with get_db(session_factory) as db:
        scan = (
            db.query(Scan)
            .options(joinedload(Scan.user))
            .filter(Scan.id == scan_id, Scan.status == "active", Scan.deleted_at.is_(None))
            .first()
        )
        if not scan:
            logger.warning("Scan %d not found, inactive, or deleted", scan_id)
            return
        run = ScanRun(scan_id=scan_id, started_at=_now())
        db.add(run)
        db.flush()
        run_id = run.id

        if not active_windows(scan.search_windows):
            run.outcome = "no_results"
            run.sites_found = 0
            run.finished_at = _now()
            scan.status = ScanStatus.completed
            db.flush()
            db.expunge_all()
            notify_scan_stopped(scan, settings)
            return

        db.expunge_all()

    user = scan.user

    # Slow I/O: availability — no lock held
    try:
        sites = check_availability(scan)
    except Exception as e:
        logger.exception("Scan %d failed: %s", scan_id, e)
        with get_db(session_factory) as db:
            run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
            run.outcome = "error"
            run.error_message = str(e)
            run.sites_found = 0
            run.finished_at = _now()
        return

    current_keys = {(str(s.campsite_id), _as_date(s.booking_date)) for s in sites}

    # TX2: dedup + insert new results, collect payloads
    new_items: list[tuple[int, NotificationPayload, dict]] = []
    with get_db(session_factory) as db:
        for site in sites:
            booking_date = _as_date(site.booking_date)
            booking_end_date = _as_date(site.booking_end_date)
            if scan.notify_on_new_only:
                exists = (
                    db.query(ScanResult)
                    .filter(
                        ScanResult.scan_id == scan_id,
                        ScanResult.campsite_id == str(site.campsite_id),
                        ScanResult.booking_date == booking_date,
                    )
                    .first()
                )
                if exists:
                    continue
            seen = _now()
            result = ScanResult(
                scan_run_id=run_id, scan_id=scan_id,
                campsite_id=str(site.campsite_id),
                facility_id=str(site.facility_id), facility_name=site.facility_name,
                recreation_area_id=str(site.recreation_area_id), recreation_area=site.recreation_area,
                site_name=site.campsite_site_name,
                campsite_type=site.campsite_type,
                booking_date=booking_date, booking_end_date=booking_end_date,
                booking_url=site.booking_url, first_seen_at=seen, last_seen_at=seen,
                is_available=True,
            )
            db.add(result)
            db.flush()
            payload = NotificationPayload(
                facility_name=site.facility_name, site_name=site.campsite_site_name,
                campsite_type=site.campsite_type, booking_date=booking_date,
                booking_end_date=booking_end_date, booking_url=site.booking_url,
                cart_added=False, nights=scan.nights,
                recreation_area=site.recreation_area,
            )
            new_items.append((
                result.id, payload,
                {"booking_url": site.booking_url,
                 "check_in": booking_date.strftime("%m-%d-%Y"),
                 "check_out": booking_end_date.strftime("%m-%d-%Y")},
            ))

    # Availability lifecycle: bump last_seen for keys present this run,
    # flip previously-available keys that dropped out to unavailable.
    # Runs even when `sites` is empty (everything then goes unavailable).
    availability_now = _now()
    with get_db(session_factory) as db:
        rows = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        for r in rows:
            if (r.campsite_id, r.booking_date) in current_keys:
                r.last_seen_at = availability_now
                r.is_available = True
            elif r.is_available:
                r.is_available = False

    # Finalize the run NOW — before cart-add — so a sidecar crash can't orphan it.
    with get_db(session_factory) as db:
        run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
        run.outcome = "success" if sites else "no_results"
        run.sites_found = len(sites)
        run.finished_at = _now()

    if not new_items:
        return

    # Email #1 — available (fast). Mark notified only on success.
    payloads = [p for _, p, _ in new_items]
    try:
        notify_available(scan, payloads, settings)
        with get_db(session_factory) as db:
            db.query(ScanResult).filter(
                ScanResult.id.in_([rid for rid, _, _ in new_items])
            ).update({"notified": True, "notified_at": _now()}, synchronize_session=False)
    except Exception as e:
        logger.error("Available notification failed for scan %d: %s", scan_id, e)

    # Cart-add + Email #2 — only when auto_book is on.
    if not scan.auto_book:
        return
    if not (user and user.recreationgov_email and user.recreationgov_password):
        # auto_book is on but the account has no Recreation.gov login stored.
        # Returning silently here is indistinguishable from "nothing was
        # available", so surface it as a skip.
        logger.info(cart_add_event(
            result=RESULT_SKIPPED, scan_id=scan_id,
            reason=REASON_NO_CREDENTIALS, found=len(new_items),
        ))
        return

    try:
        if not sidecar_healthy(settings):
            logger.warning("Sidecar unhealthy; skipping cart-add for scan %d", scan_id)
            logger.info(cart_add_event(
                result=RESULT_SKIPPED, scan_id=scan_id,
                reason=REASON_SIDECAR_UNAVAILABLE, found=len(new_items),
            ))
            notify_cart_results(scan, payloads, settings, sidecar_available=False)
            return

        pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
        # Each add places a real 15-minute hold on a live campsite, and the
        # sidecar works through them one at a time — a popular campground can
        # free up dozens of sites at once, so only the first few are carted.
        cart_items = new_items[: settings.cart_add_max_sites]
        if len(new_items) > len(cart_items):
            logger.info(cart_add_event(
                result=RESULT_SKIPPED, scan_id=scan_id, reason=REASON_OVER_CAP,
                capped=len(cart_items), found=len(new_items),
            ))
        sites_payload = [s for _, _, s in cart_items]
        results = attempt_cart_add_batch(sites_payload, user.recreationgov_email, pw, settings)

        now = _now()
        with get_db(session_factory) as db:
            for (rid, payload, site), res in zip(cart_items, results):
                carted = bool(res.get("success"))
                error = None if carted else (res.get("error") or "")
                payload.cart_added = carted
                row = db.query(ScanResult).filter(ScanResult.id == rid).first()
                if row:
                    row.cart_added = carted
                    row.cart_error = error
                    if carted:
                        row.cart_added_at = now
                logger.info(cart_add_event(
                    result=RESULT_SUCCESS if carted else RESULT_FAILURE,
                    scan_id=scan_id,
                    campsite_id=row.campsite_id if row else None,
                    reason=None if carted else classify_cart_error(error),
                    duration_ms=res.get("duration_ms"),
                    error=error,
                ))
        notify_cart_results(scan, payloads, settings)
    except Exception as e:
        logger.error("Cart-add/notify phase failed for scan %d: %s", scan_id, e)
