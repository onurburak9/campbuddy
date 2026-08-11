from unittest.mock import patch

from core.services.exceptions import UpstreamError


def test_create_feedback_requires_auth(client):
    resp = client.post("/api/v1/feedback", json={"page_path": "/scans/12", "message": "Broken button"})
    assert resp.status_code == 401


def test_create_feedback_happy_path(auth_client):
    client, _ = auth_client
    with patch("api.routes.feedback.feedback_svc.submit_feedback", return_value=None) as mock_submit:
        resp = client.post("/api/v1/feedback", json={"page_path": "/scans/12", "message": "Broken button"})
    assert resp.status_code == 202
    mock_submit.assert_called_once()
    args = mock_submit.call_args[0]
    assert args[1] == "/scans/12"
    assert args[2] == "Broken button"


def test_create_feedback_upstream_failure_returns_502(auth_client):
    client, _ = auth_client
    with patch("api.routes.feedback.feedback_svc.submit_feedback", side_effect=UpstreamError("both channels down")):
        resp = client.post("/api/v1/feedback", json={"page_path": "/scans/12", "message": "Broken button"})
    assert resp.status_code == 502


def test_create_feedback_rejects_empty_message(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/feedback", json={"page_path": "/scans/12", "message": ""})
    assert resp.status_code == 422


def test_create_feedback_rejects_oversized_message(auth_client):
    client, _ = auth_client
    resp = client.post("/api/v1/feedback", json={"page_path": "/scans/12", "message": "x" * 2001})
    assert resp.status_code == 422
