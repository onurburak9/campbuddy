import pytest
from datetime import datetime, date, timedelta, timezone
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
    s.cart_add_max_sites = 5
    return s


FUTURE_START = (date.today() + timedelta(days=30)).isoformat()
FUTURE_END = (date.today() + timedelta(days=33)).isoformat()


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
            search_windows=[{"start_date": FUTURE_START, "end_date": FUTURE_END}],
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
    site.facility_id = 232447
    site.recreation_area_id = 2991
    site.recreation_area = "Yosemite National Park"
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


def test_run_saves_result_and_marks_cart_when_autobook_on(factory, scan_id, settings, mocker):
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True})
        db.commit()
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.attempt_cart_add_batch", return_value=[{"success": True, "error": None}])
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify_available = mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.notify_cart_results")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        result = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert result.cart_added is True
        assert result.notified is True
    mock_notify_available.assert_called_once()


def test_run_passes_recreation_area_to_notification_payload(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mock_notify_available = mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    payloads = mock_notify_available.call_args.args[1]
    assert payloads[0].recreation_area == "Yosemite National Park"


def test_dedup_skips_same_site_same_date(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mock_notify_available = mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify_available.call_count == 1  # second run: dedup, no new items, no email


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
    mock_notify_available = mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify_available.call_count == 2  # once per run, each with 1 payload
    second_call_payloads = mock_notify_available.call_args_list[1].args[1]
    assert len(second_call_payloads) == 1


def test_mixed_cart_add_results_recorded_and_reported(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    site_c = make_site(campsite_id="333")
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True})
        db.commit()
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b, site_c])
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch(
        "core.runner.attempt_cart_add_batch",
        return_value=[
            {"success": True, "error": None},
            {"success": False, "error": "boom"},
            {"success": True, "error": None},
        ],
    )
    mock_cart_results = mocker.patch("core.runner.notify_cart_results")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        results = {
            r.campsite_id: r
            for r in db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        }
        assert results["111"].cart_added is True
        assert results["222"].cart_added is False
        assert results["333"].cart_added is True
    mock_cart_results.assert_called_once()
    cart_payloads = mock_cart_results.call_args[0][1]
    assert sorted(p.cart_added for p in cart_payloads) == [False, True, True]


def test_available_send_marks_all_results_notified(factory, scan_id, settings, mocker):
    site_a = make_site(campsite_id="111")
    site_b = make_site(campsite_id="222")
    mocker.patch("core.runner.check_availability", return_value=[site_a, site_b])
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        results = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert len(results) == 2
        assert all(r.notified for r in results)
        assert all(r.notified_at is not None for r in results)


def test_re_find_updates_last_seen_at(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        first = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        first_seen = first.first_seen_at
        seen_after_run1 = first.last_seen_at
    run_scan(scan_id, factory, settings)
    with factory() as db:
        rows = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert len(rows) == 1  # dedup: still one row
        r = rows[0]
        assert r.first_seen_at == first_seen  # unchanged
        assert r.last_seen_at > seen_after_run1  # bumped on re-find
        assert r.is_available is True


def test_dropout_flips_is_available_false(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", side_effect=[[make_site()], []])
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)  # site present
    run_scan(scan_id, factory, settings)  # site gone (empty results)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.is_available is False


def test_reappearance_flips_is_available_true(factory, scan_id, settings, mocker):
    mocker.patch(
        "core.runner.check_availability",
        side_effect=[[make_site()], [], [make_site()]],
    )
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)  # present
    run_scan(scan_id, factory, settings)  # gone
    with factory() as db:
        assert db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one().is_available is False
    run_scan(scan_id, factory, settings)  # back
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.is_available is True


def test_new_row_stamps_last_seen_and_available(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.last_seen_at is not None
        assert r.last_seen_at >= r.first_seen_at
        assert r.is_available is True


def test_available_email_sent_before_cartadd(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    order = []
    mocker.patch("core.runner.notify_available", side_effect=lambda *a, **k: order.append("available"))
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.attempt_cart_add_batch",
                 side_effect=lambda *a, **k: order.append("cartadd") or [{"success": True, "error": None}])
    mocker.patch("core.runner.notify_cart_results", side_effect=lambda *a, **k: order.append("cart_results"))
    # enable auto_book on the scan
    with factory() as db:
        from db.models import Scan
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True}); db.commit()
    run_scan(scan_id, factory, settings)
    assert order == ["available", "cartadd", "cart_results"]


def test_run_finalized_before_cartadd(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    # cart-add raises → run must already be finalized with sites_found=1
    mocker.patch("core.runner.attempt_cart_add_batch", side_effect=RuntimeError("sidecar died"))
    with factory() as db:
        from db.models import Scan
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True}); db.commit()
    run_scan(scan_id, factory, settings)
    with factory() as db:
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "success"
        assert run.sites_found == 1
        assert run.finished_at is not None


def test_no_cartadd_when_autobook_off(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    batch = mocker.patch("core.runner.attempt_cart_add_batch")
    cart_results = mocker.patch("core.runner.notify_cart_results")
    run_scan(scan_id, factory, settings)  # scan_id fixture defaults auto_book False
    batch.assert_not_called()
    cart_results.assert_not_called()


def test_sidecar_unhealthy_notifies_unavailable_and_skips_cartadd(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.sidecar_healthy", return_value=False)
    batch = mocker.patch("core.runner.attempt_cart_add_batch")
    cart_results = mocker.patch("core.runner.notify_cart_results")
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True}); db.commit()
    run_scan(scan_id, factory, settings)
    batch.assert_not_called()
    cart_results.assert_called_once()
    assert cart_results.call_args.kwargs["sidecar_available"] is False


def _enable_autobook(factory, scan_id):
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update({"auto_book": True})
        db.commit()


def _many_sites(n):
    return [make_site(campsite_id=str(1000 + i)) for i in range(n)]


def test_cart_add_is_capped_at_the_configured_maximum(factory, scan_id, settings, mocker):
    """Acorn alone returns 69 free sites; each add places a real 15-minute hold."""
    settings.cart_add_max_sites = 3
    _enable_autobook(factory, scan_id)
    mocker.patch("core.runner.check_availability", return_value=_many_sites(12))
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.notify_cart_results")
    batch = mocker.patch("core.runner.attempt_cart_add_batch",
                         return_value=[{"success": True, "error": None}] * 3)
    run_scan(scan_id, factory, settings)
    assert len(batch.call_args.args[0]) == 3


def test_sites_beyond_the_cap_are_not_marked_as_carted(factory, scan_id, settings, mocker):
    settings.cart_add_max_sites = 3
    _enable_autobook(factory, scan_id)
    mocker.patch("core.runner.check_availability", return_value=_many_sites(12))
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.notify_cart_results")
    mocker.patch("core.runner.attempt_cart_add_batch",
                 return_value=[{"success": True, "error": None}] * 3)
    run_scan(scan_id, factory, settings)
    with factory() as db:
        rows = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert sum(1 for r in rows if r.cart_added) == 3
        assert len(rows) == 12


def test_every_found_site_is_still_notified_when_cart_add_is_capped(factory, scan_id, settings, mocker):
    settings.cart_add_max_sites = 3
    _enable_autobook(factory, scan_id)
    mocker.patch("core.runner.check_availability", return_value=_many_sites(12))
    mocker.patch("core.runner.sidecar_healthy", return_value=True)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.attempt_cart_add_batch",
                 return_value=[{"success": True, "error": None}] * 3)
    cart_results = mocker.patch("core.runner.notify_cart_results")
    run_scan(scan_id, factory, settings)
    assert len(cart_results.call_args.args[1]) == 12


def _autobook_run(factory, scan_id, settings, mocker, sites, results, healthy=True):
    _enable_autobook(factory, scan_id)
    mocker.patch("core.runner.check_availability", return_value=sites)
    mocker.patch("core.runner.sidecar_healthy", return_value=healthy)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_available")
    mocker.patch("core.runner.notify_cart_results")
    mocker.patch("core.runner.attempt_cart_add_batch", return_value=results)
    run_scan(scan_id, factory, settings)


DISABLED = {"success": False, "error": "Add to Cart is disabled for these dates"}


def test_cart_failure_reason_is_persisted(factory, scan_id, settings, mocker):
    """cart_added=False alone can't distinguish failure from never-attempted."""
    _autobook_run(factory, scan_id, settings, mocker, [make_site()], [DISABLED])
    with factory() as db:
        row = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert row.cart_added is False
        assert "disabled" in row.cart_error


def test_cart_success_records_no_error(factory, scan_id, settings, mocker):
    _autobook_run(factory, scan_id, settings, mocker, [make_site()],
                  [{"success": True, "error": None}])
    with factory() as db:
        row = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert row.cart_added is True
        assert row.cart_error is None


def test_cart_success_emits_a_structured_event(factory, scan_id, settings, mocker, caplog):
    caplog.set_level("INFO", logger="core.runner")
    _autobook_run(factory, scan_id, settings, mocker, [make_site()],
                  [{"success": True, "error": None, "duration_ms": 18004}])
    line = next(r.message for r in caplog.records if "event=cart_add" in r.message)
    assert "result=success" in line
    assert "duration_ms=18004" in line


def test_cart_failure_event_carries_a_reason_code(factory, scan_id, settings, mocker, caplog):
    caplog.set_level("INFO", logger="core.runner")
    _autobook_run(factory, scan_id, settings, mocker, [make_site()], [DISABLED])
    line = next(r.message for r in caplog.records if "event=cart_add" in r.message)
    assert "result=failure" in line
    assert "reason=button_disabled" in line


def test_cart_event_is_a_single_line(factory, scan_id, settings, mocker, caplog):
    """A multi-line Playwright error would split into several Loki entries."""
    caplog.set_level("INFO", logger="core.runner")
    multiline = {"success": False, "error": "Timeout 45000ms exceeded.\nwaiting for locator"}
    _autobook_run(factory, scan_id, settings, mocker, [make_site()], [multiline])
    line = next(r.message for r in caplog.records if "event=cart_add" in r.message)
    assert "\n" not in line


def test_sites_over_the_cap_are_logged_as_skipped(factory, scan_id, settings, mocker, caplog):
    caplog.set_level("INFO", logger="core.runner")
    settings.cart_add_max_sites = 2
    _autobook_run(factory, scan_id, settings, mocker, _many_sites(7),
                  [{"success": True, "error": None}] * 2)
    line = next(r.message for r in caplog.records
                if "event=cart_add" in r.message and "result=skipped" in r.message)
    assert "reason=over_cap" in line
    assert "found=7" in line


def test_unhealthy_sidecar_is_logged_as_skipped(factory, scan_id, settings, mocker, caplog):
    caplog.set_level("INFO", logger="core.runner")
    _autobook_run(factory, scan_id, settings, mocker, [make_site()], [], healthy=False)
    line = next(r.message for r in caplog.records
                if "event=cart_add" in r.message and "result=skipped" in r.message)
    assert "reason=sidecar_unavailable" in line


def test_notified_only_set_on_available_success(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available", side_effect=RuntimeError("smtp down"))
    run_scan(scan_id, factory, settings)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first()
        assert r is not None and r.notified is False


def test_run_persists_facility_and_area_identifiers(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.notify_available")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.facility_id == "232447"
        assert r.recreation_area_id == "2991"
        assert r.recreation_area == "Yosemite National Park"


PAST_WINDOW = [{
    "start_date": (date.today() - timedelta(days=10)).isoformat(),
    "end_date": (date.today() - timedelta(days=5)).isoformat(),
}]


def test_run_stops_scan_and_notifies_when_all_windows_expired(factory, scan_id, settings, mocker):
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update({"search_windows": PAST_WINDOW})
        db.commit()
    mock_avail = mocker.patch("core.runner.check_availability")
    mock_notify_stopped = mocker.patch("core.runner.notify_scan_stopped")

    run_scan(scan_id, factory, settings)

    mock_avail.assert_not_called()
    mock_notify_stopped.assert_called_once()
    with factory() as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        assert scan.status == "completed"
        run = db.query(ScanRun).filter(ScanRun.scan_id == scan_id).first()
        assert run.outcome == "no_results"
        assert run.sites_found == 0
        assert run.finished_at is not None


def test_run_continues_when_at_least_one_window_still_active(factory, scan_id, settings, mocker):
    future_window = {
        "start_date": (date.today() + timedelta(days=30)).isoformat(),
        "end_date": (date.today() + timedelta(days=33)).isoformat(),
    }
    with factory() as db:
        db.query(Scan).filter(Scan.id == scan_id).update(
            {"search_windows": PAST_WINDOW + [future_window]}
        )
        db.commit()
    mock_avail = mocker.patch("core.runner.check_availability", return_value=[])
    mock_notify_stopped = mocker.patch("core.runner.notify_scan_stopped")

    run_scan(scan_id, factory, settings)

    mock_avail.assert_called_once()
    mock_notify_stopped.assert_not_called()
    with factory() as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        assert scan.status == "active"
