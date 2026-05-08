import httpx
import pytest
from unittest.mock import MagicMock
from core.booking import attempt_cart_add


def make_settings(url="http://playwright:8001"):
    s = MagicMock()
    s.playwright_service_url = url
    return s


def test_returns_true_on_success(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is True


def test_returns_false_on_service_failure(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, json={"success": False, "error": "Login failed"})
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False


def test_returns_false_on_http_500(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(500)
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False


def test_returns_false_on_connection_error(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False


def test_returns_false_on_non_json_body(respx_mock):
    respx_mock.post("http://playwright:8001/add-to-cart").mock(
        return_value=httpx.Response(200, content=b"<html>Bad Gateway</html>")
    )
    assert attempt_cart_add("https://rec.gov/site/1", "u@e.com", "pw", make_settings()) is False
