from datetime import datetime, date, timezone

from api.schemas import ScanResultResponse
from db.models import ScanResult


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
