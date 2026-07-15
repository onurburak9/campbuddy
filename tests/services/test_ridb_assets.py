import httpx
import pytest

from core.services.ridb_assets import AssetsSearchError, assets_endpoint_healthy, search_assets

ASSETS_URL = "https://ridb.recreation.gov/api/v1/public/assets"


def test_search_assets_returns_data_list(respx_mock):
    respx_mock.get(ASSETS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}], "total_results": 1},
        )
    )
    results = search_assets("yosemite", "recarea")
    assert results == [{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}]


def test_search_assets_raises_on_http_500(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_connection_error(respx_mock):
    respx_mock.get(ASSETS_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_non_json_body(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, content=b"<html>Bad Gateway</html>"))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_search_assets_raises_on_missing_data_key(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, json={"oops": []}))
    with pytest.raises(AssetsSearchError):
        search_assets("yosemite", "recarea")


def test_assets_endpoint_healthy_true(respx_mock):
    respx_mock.get(ASSETS_URL).mock(return_value=httpx.Response(200, json={"data": [], "total_results": 0}))
    assert assets_endpoint_healthy() is True


def test_assets_endpoint_healthy_false_on_error(respx_mock):
    respx_mock.get(ASSETS_URL).mock(side_effect=httpx.ConnectError("refused"))
    assert assets_endpoint_healthy() is False
