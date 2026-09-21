from datetime import datetime, date, timedelta, timezone

from api.schemas import ScanResponse, ScanResultResponse
from db.models import Scan, ScanResult


def test_scan_result_response_includes_availability_fields():
    now = datetime.now(timezone.utc)
    result = ScanResult(
        id=1,
        scan_run_id=1,
        scan_id=1,
        campsite_id="1",
        facility_name="F",
        site_name="S",
        campsite_type="T",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://example.com",
        first_seen_at=now,
        last_seen_at=now,
        is_available=True,
        cart_added=False,
        notified=False,
    )
    resp = ScanResultResponse.from_orm(result)
    assert resp.first_seen_at == now
    assert resp.last_seen_at == now
    assert resp.is_available is True


def test_scan_result_response_exposes_the_cart_failure_reason():
    now = datetime.now(timezone.utc)
    result = ScanResult(
        id=1, scan_run_id=1, scan_id=1, campsite_id="1", facility_name="F",
        site_name="S", campsite_type="T", booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6), booking_url="https://example.com",
        first_seen_at=now, last_seen_at=now, is_available=True,
        cart_added=False, notified=False,
        cart_error="Add to Cart is disabled for these dates",
    )
    resp = ScanResultResponse.from_orm(result)
    assert resp.cart_error == "Add to Cart is disabled for these dates"


def test_scan_result_cart_error_defaults_to_none():
    now = datetime.now(timezone.utc)
    result = ScanResult(
        id=1, scan_run_id=1, scan_id=1, campsite_id="1", facility_name="F",
        site_name="S", campsite_type="T", booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6), booking_url="https://example.com",
        first_seen_at=now, last_seen_at=now, is_available=True,
        cart_added=True, notified=False,
    )
    assert ScanResultResponse.from_orm(result).cart_error is None


def test_scan_response_flags_expired_and_active_windows():
    past = {
        "start_date": (date.today() - timedelta(days=10)).isoformat(),
        "end_date": (date.today() - timedelta(days=5)).isoformat(),
    }
    future = {
        "start_date": (date.today() + timedelta(days=5)).isoformat(),
        "end_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    scan = Scan(
        id=1,
        user_id=1,
        provider="RecreationDotGov",
        status="active",
        polling_interval=300,
        search_windows=[past, future],
        nights=1,
        weekends_only=False,
        notify_via_email=True,
        notify_via_telegram=False,
        notify_on_new_only=True,
        auto_book=False,
        created_at=datetime.now(timezone.utc),
    )

    resp = ScanResponse.from_orm(scan)

    assert resp.search_windows[0]["expired"] is True
    assert resp.search_windows[1]["expired"] is False
