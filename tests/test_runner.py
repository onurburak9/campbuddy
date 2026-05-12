import pytest
from datetime import datetime, date, timezone
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Scan, ScanRun, ScanResult
from core.runner import run_scan


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def settings():
    s = MagicMock()
    s.encryption_key = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ="
    s.playwright_service_url = "http://playwright:8001"
    return s


@pytest.fixture
def scan_id(factory):
    with factory() as db:
        user = User(
            email="test@example.com",
            recreationgov_email="rg@example.com",
            recreationgov_password="encrypted_placeholder",
        )
        db.add(user)
        db.flush()
        scan = Scan(
            user_id=user.id,
            search_windows=[{"start_date": "2026-07-03", "end_date": "2026-07-06"}],
            rec_area_ids=[1076],
            nights=3,
            polling_interval=300,
            notify_via_email=True,
            notify_via_telegram=False,
            notify_on_new_only=True,
            status="active",
        )
        db.add(scan)
        db.commit()
        return scan.id


def make_site(campsite_id="10357088", check_in=date(2026, 7, 3)):
    site = MagicMock()
    site.campsite_id = campsite_id
    site.facility_name = "Union West"
    site.campsite_site_name = "1"
    site.campsite_type = "STANDARD NONELECTRIC"
    site.booking_date = datetime.combine(check_in, datetime.min.time())
    site.booking_end_date = datetime.combine(date(2026, 7, 6), datetime.min.time())
    site.booking_url = f"https://www.recreation.gov/camping/campsites/{campsite_id}"
    site.booking_nights = 3
    return site


def test_run_writes_scan_run_on_no_results(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[])
    run_scan(scan_id, factory, settings)
    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "no_results"
        assert run.sites_found == 0
        assert run.finished_at is not None


def test_run_writes_scan_run_on_error(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", side_effect=RuntimeError("boom"))
    run_scan(scan_id, factory, settings)
    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "error"
        assert "boom" in run.error_message


def test_run_saves_result_notifies_and_marks_cart(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.cart_added is True
        assert result.notified is True
    mock_notify.assert_called_once()


def test_dedup_skips_same_site_same_date(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 0
    assert mock_notify_digest.call_count == 1  # only on first run; second run digest_batch is empty


def test_run_skips_deleted_scan(factory, scan_id, settings, mocker):
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update(
            {"deleted_at": datetime.now(timezone.utc)}
        )
        db.commit()
    mock_avail = mocker.patch("core.runner.check_availability")
    run_scan(scan_id, factory, settings)
    mock_avail.assert_not_called()
    with factory() as db:
        assert db.query(ScanRun).filter(ScanRun.scan_id == scan_id).count() == 0


def test_dedup_notifies_same_site_different_date(factory, scan_id, settings, mocker):
    site_a = make_site(check_in=date(2026, 7, 3))
    site_b = make_site(check_in=date(2026, 7, 10))
    mocker.patch("core.runner.check_availability", side_effect=[[site_a], [site_b]])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 0
    assert mock_notify_digest.call_count == 2  # once per run, each with 1 payload
    second_call_payloads = mock_notify_digest.call_args_list[1].args[1]
    assert len(second_call_payloads) == 1


def test_non_carted_site_routes_to_digest(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    mock_notify.assert_not_called()
    mock_notify_digest.assert_called_once()
    _, (_, payloads, _), _ = mock_notify_digest.mock_calls[0]
    assert len(payloads) == 1
    assert payloads[0].cart_added is False


def test_mixed_carted_and_non_carted_split_routing(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    site_c = make_site(campsite_id="333")
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b, site_c])
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.attempt_cart_add", side_effect=[True, False, True])
    mock_notify = mocker.patch("core.runner.notify")
    mock_notify_digest = mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 2
    assert mock_notify_digest.call_count == 1
    digest_payloads = mock_notify_digest.call_args[0][1]
    assert len(digest_payloads) == 1
    assert digest_payloads[0].cart_added is False



def test_digest_send_marks_all_results_notified(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        results = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert len(results) == 2
        assert all(r.notified for r in results)
        assert all(r.notified_at is not None for r in results)


def test_digest_failure_leaves_results_unnotified(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest", side_effect=RuntimeError("digest failed"))
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.notified is False
