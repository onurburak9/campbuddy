import pytest
from unittest.mock import MagicMock
from core.services import search
from core.services.exceptions import UpstreamError


@pytest.fixture(autouse=True)
def clear_caches():
    search.search_recreation_areas.cache_clear()
    search._search_campgrounds_cached.cache_clear()
    search._list_campsites_cached.cache_clear()
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


def make_facility(**overrides):
    facility = MagicMock()
    facility.facility_id = overrides.get("facility_id", 232447)
    facility.facility_name = overrides.get("facility_name", "Upper Pines")
    facility.recreation_area = overrides.get("recreation_area", "Yosemite National Park")
    facility.recreation_area_id = overrides.get("recreation_area_id", 2991)
    return facility


def test_search_campgrounds_by_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.search_campgrounds("Upper Pines", None)
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(search_string="Upper Pines")


def test_search_campgrounds_by_rec_area_ignores_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds("ignored text", [2991])
    mock_provider.find_campgrounds.assert_called_once_with(rec_area_id=[2991])


def test_search_campgrounds_caches_by_query_and_rec_area_ids(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds(None, [2991, 2992])
    search.search_campgrounds(None, [2992, 2991])  # same set, different order
    assert mock_provider.find_campgrounds.call_count == 1


def test_search_campgrounds_wraps_upstream_failure(mock_provider):
    mock_provider.find_campgrounds.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_campgrounds("fail-query", None)


def test_resolve_campgrounds_normalizes_results(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.resolve_campgrounds([232447])
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(campground_id=[232447])


def test_resolve_campgrounds_skips_failed_ids(mock_provider):
    mock_provider.find_campgrounds.side_effect = [
        [make_facility(facility_id=1, facility_name="Found")],
        ConnectionError("not found"),
    ]
    results = search.resolve_campgrounds([1, 999])
    assert len(results) == 1
    assert results[0]["id"] == 1


def make_campsite(**overrides):
    site = MagicMock()
    site.campsite_id = overrides.get("campsite_id", 12345)
    site.name = overrides.get("name", "Site A1")
    site.loop = overrides.get("loop", "Loop A")
    return site


def test_list_campsites_normalizes_results(mock_provider):
    mock_provider.paginate_recdotgov_campsites.return_value = [make_campsite()]
    results = search.list_campsites([232447])
    assert results == [{"id": 12345, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]
    mock_provider.paginate_recdotgov_campsites.assert_called_once_with(facility_id=232447)


def test_list_campsites_flattens_multiple_campgrounds(mock_provider):
    mock_provider.paginate_recdotgov_campsites.side_effect = [
        [make_campsite(campsite_id=1)],
        [make_campsite(campsite_id=2)],
    ]
    results = search.list_campsites([111, 222])
    assert [r["id"] for r in results] == [1, 2]


def test_list_campsites_caches_by_campground_ids(mock_provider):
    mock_provider.paginate_recdotgov_campsites.return_value = [make_campsite()]
    search.list_campsites([232447])
    search.list_campsites([232447])
    assert mock_provider.paginate_recdotgov_campsites.call_count == 1


def test_list_campsites_wraps_upstream_failure(mock_provider):
    mock_provider.paginate_recdotgov_campsites.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.list_campsites([999])


def test_resolve_campsites_normalizes_results(mock_provider):
    response = MagicMock(CampsiteID=12345, CampsiteName="Site A1", Loop="Loop A", FacilityID=232447)
    mock_provider.get_campsite_by_id.return_value = response
    results = search.resolve_campsites([12345])
    assert results == [{"id": 12345, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]
    mock_provider.get_campsite_by_id.assert_called_once_with(campsite_id=12345)


def test_resolve_campsites_skips_failed_ids(mock_provider):
    found = MagicMock(CampsiteID=1, CampsiteName="Found", Loop="Loop A", FacilityID=111)
    mock_provider.get_campsite_by_id.side_effect = [found, Exception("not found")]
    results = search.resolve_campsites([1, 999])
    assert len(results) == 1
    assert results[0]["id"] == 1
