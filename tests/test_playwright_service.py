from unittest.mock import MagicMock

import playwright_service.browser as browser


def test_add_all_loops_and_aggregates(mocker):
    mocker.patch.object(browser, "_add_single", side_effect=[
        {"success": True, "error": None},
        {"success": False, "error": "boom"},
    ])
    page = MagicMock()
    sites = [
        {"booking_url": "u1", "check_in": "07-11-2026", "check_out": "07-13-2026"},
        {"booking_url": "u2", "check_in": "07-11-2026", "check_out": "07-13-2026"},
    ]
    results = browser._add_all(page, sites)
    assert results == [
        {"success": True, "error": None},
        {"success": False, "error": "boom"},
    ]


def test_add_all_continues_after_exception(mocker):
    mocker.patch.object(browser, "_add_single", side_effect=[
        RuntimeError("nav failed"),
        {"success": True, "error": None},
    ])
    page = MagicMock()
    sites = [
        {"booking_url": "u1", "check_in": "07-11-2026", "check_out": "07-13-2026"},
        {"booking_url": "u2", "check_in": "07-11-2026", "check_out": "07-13-2026"},
    ]
    results = browser._add_all(page, sites)
    assert results[0]["success"] is False and "nav failed" in results[0]["error"]
    assert results[1]["success"] is True


def test_batch_endpoint(mocker):
    from fastapi.testclient import TestClient
    import playwright_service.main as main
    mocker.patch.object(main, "add_to_cart_batch", return_value=[{"success": True, "error": None}])
    client = TestClient(main.app)
    resp = client.post("/add-to-cart-batch", json={
        "email": "u@e.com", "password": "pw",
        "sites": [{"booking_url": "u1", "check_in": "07-11-2026", "check_out": "07-13-2026"}],
    })
    assert resp.status_code == 200
    assert resp.json() == {"results": [{"success": True, "error": None}]}
