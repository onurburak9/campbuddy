import logging
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from db.models import Scan, ScanRun, ScanResult
from db.session import get_db
from core.availability import check_availability
from core.booking import attempt_cart_add_batch, sidecar_healthy
from core.crypto import decrypt_password
from core.notifier import notify_available, notify_cart_results, NotificationPayload

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
                facility_name=site.facility_name, site_name=site.campsite_site_name,
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
        return

    try:
        if not sidecar_healthy(settings):
            logger.warning("Sidecar unhealthy; skipping cart-add for scan %d", scan_id)
            notify_cart_results(scan, payloads, settings, sidecar_available=False)
            return

        pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
        sites_payload = [s for _, _, s in new_items]
        results = attempt_cart_add_batch(sites_payload, user.recreationgov_email, pw, settings)

        now = _now()
        with get_db(session_factory) as db:
            for (rid, payload, _), res in zip(new_items, results):
                carted = bool(res.get("success"))
                payload.cart_added = carted
                row = db.query(ScanResult).filter(ScanResult.id == rid).first()
                if row:
                    row.cart_added = carted
                    if carted:
                        row.cart_added_at = now
        notify_cart_results(scan, payloads, settings)
    except Exception as e:
        logger.error("Cart-add/notify phase failed for scan %d: %s", scan_id, e)
