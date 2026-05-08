import logging
from datetime import datetime, timezone

from db.models import Scan, ScanRun, ScanResult, User
from core.availability import check_availability
from core.booking import attempt_cart_add
from core.crypto import decrypt_password
from core.notifier import notify, NotificationPayload

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def run_scan(scan_id: int, session_factory, settings) -> None:
    with session_factory() as db:
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.status == "active").first()
        if not scan:
            logger.warning("Scan %d not found or inactive", scan_id)
            return

        run = ScanRun(scan_id=scan_id, started_at=_now())
        db.add(run)
        db.flush()

        try:
            sites = check_availability(scan)
            run.sites_found = len(sites)
            run.outcome = "success" if sites else "no_results"
            user = db.query(User).filter(User.id == scan.user_id).first()

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
                    scan_run_id=run.id,
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

                cart_added = False
                if user and user.recreationgov_email and user.recreationgov_password:
                    try:
                        pw = decrypt_password(user.recreationgov_password, settings.encryption_key)
                        cart_added = attempt_cart_add(
                            site.booking_url, user.recreationgov_email, pw, settings
                        )
                    except Exception as e:
                        logger.error("Cart add error for scan %d: %s", scan_id, e)

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
                try:
                    notify(scan, payload, settings)
                    result.notified = True
                    result.notified_at = _now()
                except Exception as e:
                    logger.error("Notify error for scan %d: %s", scan_id, e)

        except Exception as e:
            logger.exception("Scan %d failed: %s", scan_id, e)
            run.outcome = "error"
            run.error_message = str(e)
            run.sites_found = 0
        finally:
            run.finished_at = _now()
            db.commit()
