import httpx
import pytest
from unittest.mock import MagicMock
from core.booking import attempt_cart_add, attempt_cart_add_batch, sidecar_healthy


def make_settings(url="http://playwright:8001"):
    s = MagicMock()
    s.playwright_service_url = url
    return s


CALL = ("https://rec.gov/site/1", "u@e.com", "pw", make_settings(), "06-01-2026", "06-02-2026")


def test_returns_true_on_success(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    assert attempt_cart_add(*CALL) is True


def test_returns_false_on_service_failure(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": False, "error": "Login failed"})
    )
    assert attempt_cart_add(*CALL) is False


def test_returns_false_on_http_500(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(500)
    )
    assert attempt_cart_add(*CALL) is False


def test_returns_false_on_connection_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert attempt_cart_add(*CALL) is False


def test_returns_false_on_non_json_body(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, content=b"<html>Bad Gateway</html>")
    )
    assert attempt_cart_add(*CALL) is False


SITES = [
    {"booking_url": "https://rec.gov/1", "check_in": "07-11-2026", "check_out": "07-13-2026"},
    {"booking_url": "https://rec.gov/2", "check_in": "07-11-2026", "check_out": "07-13-2026"},
]


def test_batch_returns_aligned_results(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart-batch").mock(
        return_value=httpx.Response(200, json={"results": [
            {"success": True, "error": None}, {"success": False, "error": "x"},
        ]})
    )
    out = attempt_cart_add_batch(SITES, "u@e.com", "pw", make_settings())
    assert [r["success"] for r in out] == [True, False]


def test_batch_all_false_on_transport_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart-batch").mock(
        side_effect=httpx.ConnectError("refused")
    )
    out = attempt_cart_add_batch(SITES, "u@e.com", "pw", make_settings())
    assert all(r["success"] is False for r in out) and len(out) == 2


def test_batch_all_false_on_http_500(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart-batch").mock(
        return_value=httpx.Response(500)
    )
    out = attempt_cart_add_batch(SITES, "u@e.com", "pw", make_settings())
    assert all(r["success"] is False for r in out) and len(out) == 2


def test_batch_all_false_on_result_count_mismatch(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart-batch").mock(
        return_value=httpx.Response(200, json={"results": [{"success": True, "error": None}]})
    )
    out = attempt_cart_add_batch(SITES, "u@e.com", "pw", make_settings())
    assert all(r["success"] is False for r in out) and len(out) == 2


def test_sidecar_healthy_true(respx_mock):
    respx_mock.get("http://playwright:8001/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    assert sidecar_healthy(make_settings()) is True


def test_sidecar_healthy_false_on_error(respx_mock):
    respx_mock.get("http://playwright:8001/health").mock(side_effect=httpx.ConnectError("x"))
    assert sidecar_healthy(make_settings()) is False


def test_sidecar_healthy_false_on_http_500(respx_mock):
    respx_mock.get("http://playwright:8001/health").mock(return_value=httpx.Response(500))
    assert sidecar_healthy(make_settings()) is False
