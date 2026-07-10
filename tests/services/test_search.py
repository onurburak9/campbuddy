import pytest
from unittest.mock import MagicMock
from core.services import search
from core.services.exceptions import UpstreamError


@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    yield


@pytest.fixture
def mock_provider(mocker):
    provider = MagicMock()
    mocker.patch("core.services.search._get_provider", return_value=provider)
    return provider


def test_search_recreation_areas_normalizes_results(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA"}]
    mock_provider.find_recreation_areas.assert_called_once_with(search_string="Yosemite")


def test_search_recreation_areas_skips_malformed_items(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        {"missing": "required fields"},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert len(results) == 1


def test_search_recreation_areas_handles_missing_address(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 5, "RecAreaName": "No Address Area", "RECAREAADDRESS": []},
    ]
    results = search.search_recreation_areas("No Address")
    assert results == [{"id": 5, "name": "No Address Area", "state": None}]


def test_search_recreation_areas_caches_by_query(mock_provider):
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    search.search_recreation_areas("Yosemite")
    search.search_recreation_areas("Yosemite")
    assert mock_provider.find_recreation_areas.call_count == 1


def test_search_recreation_areas_wraps_upstream_failure(mock_provider):
    mock_provider.find_recreation_areas.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_recreation_areas("Yosemite-fail")


def test_resolve_recreation_areas_normalizes_results(mock_provider):
    mock_provider.get_ridb_data.return_value = {
        "RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}],
    }
    results = search.resolve_recreation_areas([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA"}]
    mock_provider.get_ridb_data.assert_called_once_with(path="recareas/2991", params={"full": True})


def test_resolve_recreation_areas_skips_failed_ids(mock_provider):
    mock_provider.get_ridb_data.side_effect = [
        {"RecAreaID": 1, "RecAreaName": "Area One", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        ConnectionError("not found"),
    ]
    results = search.resolve_recreation_areas([1, 999])
    assert results == [{"id": 1, "name": "Area One", "state": "CA"}]
