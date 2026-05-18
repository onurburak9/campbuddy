import logging
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from db.models import Scan, ScanRun, ScanResult
from db.session import get_db
from core.availability import check_availability
from core.booking import attempt_cart_add
from core.crypto import decrypt_password
from core.notifier import notify, notify_digest, NotificationPayload

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def run_scan(scan_id: int, session_factory, settings) -> None:
    # Transaction 1 (fast): load config, start run
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

    # Slow I/O: check availability — no lock held
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

    try:
        digest_batch: list[tuple[int, NotificationPayload]] = []

        for site in sites:
            booking_date = (
                site.booking_date.date()
                if hasattr(site.booking_date, "date")
                else site.booking_date
            )
            booking_end_date = (
                site.booking_end_date.date()
                if hasattr(site.booking_end_date, "date")
                else site.booking_end_date
            )

            # Transaction 2 (fast): check duplicate, write result
            with get_db(session_factory) as db:
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
                result = ScanResult(
                    scan_run_id=run_id,
                    scan_id=scan_id,
                    campsite_id=str(site.campsite_id),
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    first_seen_at=_now(),
                )
                db.add(result)
                db.flush()
                result_id = result.id


            # Slow I/O: cart add — no lock held
            cart_added = False
            if user and user.recreationgov_email and user.recreationgov_password:
                try:
                    pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
                    cart_added = attempt_cart_add(
                        site.booking_url, user.recreationgov_email, pw, settings,
                        check_in=booking_date.strftime("%m-%d-%Y"),
                        check_out=booking_end_date.strftime("%m-%d-%Y"),
                    )
                except Exception as e:
                    logger.error("Cart add error for scan %d: %s", scan_id, e)

            # Transaction 3 (fast): persist cart status
            with get_db(session_factory) as db:
                result = db.query(ScanResult).filter(ScanResult.id == result_id).first()
                result.cart_added = cart_added
                if cart_added:
                    result.cart_added_at = _now()

                payload = NotificationPayload(
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    cart_added=cart_added,
                    nights=scan.nights,
                )

                if cart_added:
                    notify(scan, payload, settings)
                    result.notified = True
                    result.notified_at = _now()
                else:
                    digest_batch.append((result_id, payload))

        if digest_batch:
            digest_payloads = [p for _, p in digest_batch]
            try:
                notify_digest(scan, digest_payloads, settings)
                now = _now()
                result_ids = [rid for rid, _ in digest_batch]
                with get_db(session_factory) as db:
                    db.query(ScanResult).filter(ScanResult.id.in_(result_ids)).update(
                        {"notified": True, "notified_at": now}, synchronize_session=False
                    )
            except Exception as e:
                logger.error("Digest notify failed for scan %d: %s", scan_id, e)

        # Transaction 4 (fast): finalize run
        with get_db(session_factory) as db:
            run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
            run.outcome = "success" if sites else "no_results"
            run.sites_found = len(sites)
            run.finished_at = _now()

    except Exception as e:
        logger.exception("Scan %d failed: %s", scan_id, e)
        with get_db(session_factory) as db:
            run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
            if run:
                run.outcome = "error"
                run.error_message = str(e)
                run.sites_found = 0
                run.finished_at = _now()
