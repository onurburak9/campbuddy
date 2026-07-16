import pytest
from unittest.mock import MagicMock
from core.services import search
from core.services.exceptions import UpstreamError
from core.services.ridb_assets import AssetsSearchError


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


def test_search_recreation_areas_uses_assets_search(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"},
    ])
    resolve_mock = mocker.patch(
        "core.services.search.resolve_recreation_areas",
        return_value=[{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}],
    )
    results = search.search_recreation_areas("Yosemite")
    resolve_mock.assert_called_once_with([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}]


def test_search_recreation_areas_skips_non_numeric_asset_ids(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "AP26168", "name": "Some Activity Pass", "type": "Activity Pass"},
        {"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"},
    ])
    resolve_mock = mocker.patch("core.services.search.resolve_recreation_areas", return_value=[])
    search.search_recreation_areas("Yosemite")
    resolve_mock.assert_called_once_with([2991])


def test_search_recreation_areas_caches_by_query(mocker, mock_provider):
    assets_mock = mocker.patch(
        "core.services.search.search_assets",
        return_value=[{"id": "2991", "name": "Yosemite National Park", "type": "Rec Area"}],
    )
    mocker.patch("core.services.search.resolve_recreation_areas", return_value=[])
    search.search_recreation_areas("Yosemite")
    search.search_recreation_areas("Yosemite")
    assert assets_mock.call_count == 1


def test_search_recreation_areas_falls_back_when_assets_unavailable(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": None}]
    mock_provider.find_recreation_areas.assert_called_once_with(search_string="Yosemite")


def test_search_recreation_areas_fallback_skips_malformed_items(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.return_value = [
        {"RecAreaID": 2991, "RecAreaName": "Yosemite National Park", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        {"missing": "required fields"},
    ]
    results = search.search_recreation_areas("Yosemite")
    assert len(results) == 1


def test_search_recreation_areas_fallback_wraps_upstream_failure(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("RIDB assets down"))
    mock_provider.find_recreation_areas.side_effect = ConnectionError("RIDB is down")
    with pytest.raises(UpstreamError):
        search.search_recreation_areas("Yosemite-fail")


def test_resolve_recreation_areas_normalizes_results(mock_provider):
    mock_provider.get_ridb_data.return_value = {
        "RecAreaID": 2991, "RecAreaName": "Yosemite National Park",
        "RECAREAADDRESS": [{"AddressStateCode": "CA"}],
        "ORGANIZATION": [{"OrgName": "National Park Service"}],
    }
    results = search.resolve_recreation_areas([2991])
    assert results == [{"id": 2991, "name": "Yosemite National Park", "state": "CA", "type": "National Park Service"}]
    mock_provider.get_ridb_data.assert_called_once_with(path="recareas/2991", params={"full": True})


def test_resolve_recreation_areas_skips_failed_ids(mock_provider):
    mock_provider.get_ridb_data.side_effect = [
        {"RecAreaID": 1, "RecAreaName": "Area One", "RECAREAADDRESS": [{"AddressStateCode": "CA"}]},
        ConnectionError("not found"),
    ]
    results = search.resolve_recreation_areas([1, 999])
    assert results == [{"id": 1, "name": "Area One", "state": "CA", "type": None}]


def make_facility(**overrides):
    facility = MagicMock()
    facility.facility_id = overrides.get("facility_id", 232447)
    facility.facility_name = overrides.get("facility_name", "Upper Pines")
    facility.recreation_area = overrides.get("recreation_area", "Yosemite National Park")
    facility.recreation_area_id = overrides.get("recreation_area_id", 2991)
    return facility


def test_search_campgrounds_filters_to_campground_type(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", return_value=[
        {"id": "232447", "name": "Upper Pines Campground", "type": "Campground"},
        {"id": "245093", "name": "Boardstand /Military Road", "type": "Facility"},
    ])
    resolve_mock = mocker.patch(
        "core.services.search.resolve_campgrounds",
        return_value=[{
            "id": 232447, "name": "Upper Pines",
            "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
        }],
    )
    results = search.search_campgrounds("Upper Pines", None)
    resolve_mock.assert_called_once_with([232447])
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]


def test_search_campgrounds_by_rec_area_ignores_query(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds("ignored text", [2991])
    mock_provider.find_campgrounds.assert_called_once_with(rec_area_id=[2991])


def test_search_campgrounds_caches_by_query_and_rec_area_ids(mock_provider):
    mock_provider.find_campgrounds.return_value = [make_facility()]
    search.search_campgrounds(None, [2991, 2992])
    search.search_campgrounds(None, [2992, 2991])  # same set, different order
    assert mock_provider.find_campgrounds.call_count == 1


def test_search_campgrounds_falls_back_when_assets_unavailable(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("down"))
    mock_provider.find_campgrounds.return_value = [make_facility()]
    results = search.search_campgrounds("Upper Pines", None)
    assert results == [{
        "id": 232447, "name": "Upper Pines",
        "recreation_area": "Yosemite National Park", "recreation_area_id": 2991,
    }]
    mock_provider.find_campgrounds.assert_called_once_with(search_string="Upper Pines")


def test_search_campgrounds_fallback_wraps_upstream_failure(mocker, mock_provider):
    mocker.patch("core.services.search.search_assets", side_effect=AssetsSearchError("down"))
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
