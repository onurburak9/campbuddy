from unittest.mock import MagicMock

import pytest

from core.availability import check_availability


def make_scan(**overrides):
    scan = MagicMock()
    scan.id = 1
    scan.provider = "RecreationDotGov"
    scan.rec_area_ids = [1076]
    scan.campground_ids = None
    scan.campsite_ids = None
    scan.search_windows = [{"start_date": "2026-07-03", "end_date": "2026-07-06"}]
    scan.nights = 3
    scan.weekends_only = False
    scan.days_of_week = None
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
        {"start_date": "2026-07-03", "end_date": "2026-07-06"},
        {"start_date": "2026-07-10", "end_date": "2026-07-13"},
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


def test_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported provider"):
        check_availability(make_scan(provider="UnknownProvider"))
