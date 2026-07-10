from unittest.mock import patch


def test_recreation_areas_requires_auth(client):
    resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 401


def test_recreation_areas_requires_min_query_length(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/recreation-areas", params={"q": "y"})
    assert resp.status_code == 422


def test_recreation_areas_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_recreation_areas", return_value=[{"id": 2991, "name": "Yosemite", "state": "CA"}]):
        resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 2991, "name": "Yosemite", "state": "CA"}]


def test_recreation_areas_upstream_failure_returns_502(auth_client):
    from core.services.exceptions import UpstreamError
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_recreation_areas", side_effect=UpstreamError("RIDB down")):
        resp = client.get("/api/v1/search/recreation-areas", params={"q": "Yosemite"})
    assert resp.status_code == 502


def test_recreation_areas_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_recreation_areas", return_value=[{"id": 2991, "name": "Yosemite", "state": "CA"}]):
        resp = client.get("/api/v1/search/recreation-areas/resolve", params={"ids": [2991]})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 2991, "name": "Yosemite", "state": "CA"}]


def test_campgrounds_requires_query_or_rec_area_ids(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/campgrounds")
    assert resp.status_code == 422


def test_campgrounds_by_query(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_campgrounds", return_value=[{"id": 1, "name": "Upper Pines", "recreation_area": "Yosemite", "recreation_area_id": 2991}]) as mock_search:
        resp = client.get("/api/v1/search/campgrounds", params={"q": "Upper Pines"})
    assert resp.status_code == 200
    mock_search.assert_called_once_with("Upper Pines", None)


def test_campgrounds_by_rec_area_ids(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.search_campgrounds", return_value=[]) as mock_search:
        resp = client.get("/api/v1/search/campgrounds", params={"rec_area_ids": [2991, 2992]})
    assert resp.status_code == 200
    mock_search.assert_called_once_with(None, [2991, 2992])


def test_campgrounds_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_campgrounds", return_value=[{"id": 1, "name": "Upper Pines", "recreation_area": "Yosemite", "recreation_area_id": 2991}]):
        resp = client.get("/api/v1/search/campgrounds/resolve", params={"ids": [1]})
    assert resp.status_code == 200


def test_campsites_requires_campground_ids(auth_client):
    client, _ = auth_client
    resp = client.get("/api/v1/search/campsites")
    assert resp.status_code == 422


def test_campsites_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.list_campsites", return_value=[{"id": 1, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]) as mock_list:
        resp = client.get("/api/v1/search/campsites", params={"campground_ids": [232447]})
    assert resp.status_code == 200
    mock_list.assert_called_once_with([232447])


def test_campsites_resolve_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.search.search_svc.resolve_campsites", return_value=[{"id": 1, "name": "Site A1", "loop": "Loop A", "campground_id": 232447}]):
        resp = client.get("/api/v1/search/campsites/resolve", params={"ids": [1]})
    assert resp.status_code == 200
