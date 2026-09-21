from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.availability import check_availability

FUTURE_START = date.today() + timedelta(days=30)
FUTURE_END = FUTURE_START + timedelta(days=3)


def make_scan(**overrides):
    scan = MagicMock()
    scan.id = 1
    scan.provider = "RecreationDotGov"
    scan.rec_area_ids = [1076]
    scan.campground_ids = None
    scan.campsite_ids = None
    scan.search_windows = [
        {"start_date": FUTURE_START.isoformat(), "end_date": FUTURE_END.isoformat()}
    ]
    scan.nights = 3
    scan.weekends_only = False
    scan.days_of_week = None
    scan.equipment_types = None
    for k, v in overrides.items():
        setattr(scan, k, v)
    return scan


def patch_provider(mocker, mock_cls):
    """Replace the RecreationDotGov entry in PROVIDER_MAP with a mock class."""
    mocker.patch.dict("core.availability.PROVIDER_MAP", {"RecreationDotGov": mock_cls})


def test_returns_matching_sites(mocker):
    mock_site = MagicMock()
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [mock_site]
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    result = check_availability(make_scan())

    assert result == [mock_site]
    mock_search.get_matching_campsites.assert_called_once_with(continuous=False)


def test_returns_empty_on_no_availability(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    patch_provider(mocker, MagicMock(return_value=mock_search))

    assert check_availability(make_scan()) == []


def test_multiple_search_windows_passed(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    scan = make_scan(search_windows=[
        {"start_date": FUTURE_START.isoformat(), "end_date": FUTURE_END.isoformat()},
        {
            "start_date": (FUTURE_START + timedelta(days=7)).isoformat(),
            "end_date": (FUTURE_END + timedelta(days=7)).isoformat(),
        },
    ])
    check_availability(scan)

    windows = mock_cls.call_args.kwargs["search_window"]
    assert len(windows) == 2


def test_optional_targets_passed_when_set(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    check_availability(make_scan(
        campground_ids=[12345],
        campsite_ids=[98363],
        days_of_week=[5, 6],  # Sat, Sun
    ))

    kwargs = mock_cls.call_args.kwargs
    assert kwargs["campgrounds"] == [12345]
    assert kwargs["campsites"] == [98363]
    assert kwargs["days_of_the_week"] == [5, 6]


def test_no_equipment_types_omits_equipment_kwarg(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    check_availability(make_scan())

    assert "equipment" not in mock_cls.call_args.kwargs


def test_camply_native_equipment_types_passed_through(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    check_availability(make_scan(equipment_types=["tent", "rv"]))

    equipment = mock_cls.call_args.kwargs["equipment"]
    assert set(equipment) == {("tent", None), ("rv", None)}


def test_horse_equipment_type_not_passed_to_camply(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    check_availability(make_scan(equipment_types=["horse"]))

    assert "equipment" not in mock_cls.call_args.kwargs


def test_horse_equipment_type_filters_sites_by_permitted_equipment(mocker):
    horse_site = MagicMock(permitted_equipment=[SimpleNamespace(equipment_name="Horse", max_length=0.0)])
    tent_site = MagicMock(permitted_equipment=[SimpleNamespace(equipment_name="Tent", max_length=0.0)])
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [horse_site, tent_site]
    patch_provider(mocker, MagicMock(return_value=mock_search))

    result = check_availability(make_scan(equipment_types=["horse"]))

    assert result == [horse_site]


def test_sites_missing_permitted_equipment_excluded_when_horse_requested(mocker):
    no_equipment_site = MagicMock(permitted_equipment=None)
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [no_equipment_site]
    patch_provider(mocker, MagicMock(return_value=mock_search))

    result = check_availability(make_scan(equipment_types=["horse"]))

    assert result == []


def test_horse_combined_with_native_equipment_type(mocker):
    horse_site = MagicMock(permitted_equipment=[SimpleNamespace(equipment_name="Horse", max_length=0.0)])
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = [horse_site]
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    result = check_availability(make_scan(equipment_types=["tent", "horse"]))

    assert mock_cls.call_args.kwargs["equipment"] == [("tent", None)]
    assert result == [horse_site]


def test_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported provider"):
        check_availability(make_scan(provider="UnknownProvider"))


def test_no_targeting_ids_raises():
    with pytest.raises(ValueError, match="at least one of"):
        check_availability(make_scan(
            rec_area_ids=None, campground_ids=None, campsite_ids=None
        ))


PAST_START = date.today() - timedelta(days=10)
PAST_END = date.today() - timedelta(days=5)


def test_expired_windows_excluded_from_search(mocker):
    mock_search = MagicMock()
    mock_search.get_matching_campsites.return_value = []
    mock_cls = MagicMock(return_value=mock_search)
    patch_provider(mocker, mock_cls)

    scan = make_scan(search_windows=[
        {"start_date": PAST_START.isoformat(), "end_date": PAST_END.isoformat()},
        {"start_date": FUTURE_START.isoformat(), "end_date": FUTURE_END.isoformat()},
    ])
    check_availability(scan)

    windows = mock_cls.call_args.kwargs["search_window"]
    assert len(windows) == 1
    assert windows[0].start_date == FUTURE_START


def test_returns_empty_without_calling_provider_when_all_windows_expired(mocker):
    mock_cls = MagicMock()
    patch_provider(mocker, mock_cls)

    scan = make_scan(search_windows=[
        {"start_date": PAST_START.isoformat(), "end_date": PAST_END.isoformat()},
    ])

    assert check_availability(scan) == []
    mock_cls.assert_not_called()
