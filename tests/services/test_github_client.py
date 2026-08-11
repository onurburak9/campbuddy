import httpx
import pytest

from core.services.github_client import GitHubIssueError, create_issue

ISSUES_URL = "https://api.github.com/repos/onurburak9/campbuddy/issues"


def test_create_issue_returns_response_json(respx_mock):
    respx_mock.post(ISSUES_URL).mock(
        return_value=httpx.Response(201, json={"number": 42, "html_url": "https://github.com/onurburak9/campbuddy/issues/42"})
    )
    result = create_issue("onurburak9/campbuddy", "ghp_token", "Feedback from a@b.c", "body text", labels=["feedback"])
    assert result["number"] == 42


def test_create_issue_sends_expected_payload_and_headers(respx_mock):
    route = respx_mock.post(ISSUES_URL).mock(return_value=httpx.Response(201, json={"number": 1}))
    create_issue("onurburak9/campbuddy", "ghp_token", "Title", "Body", labels=["feedback"])
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer ghp_token"
    assert request.headers["Accept"] == "application/vnd.github+json"
    import json
    payload = json.loads(request.content)
    assert payload == {"title": "Title", "body": "Body", "labels": ["feedback"]}


def test_create_issue_raises_on_empty_token():
    with pytest.raises(GitHubIssueError):
        create_issue("onurburak9/campbuddy", "", "Title", "Body", labels=["feedback"])


def test_create_issue_raises_on_http_error_status(respx_mock):
    respx_mock.post(ISSUES_URL).mock(return_value=httpx.Response(401, json={"message": "Bad credentials"}))
    with pytest.raises(GitHubIssueError):
        create_issue("onurburak9/campbuddy", "bad_token", "Title", "Body", labels=["feedback"])


def test_create_issue_raises_on_connection_error(respx_mock):
    respx_mock.post(ISSUES_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(GitHubIssueError):
        create_issue("onurburak9/campbuddy", "ghp_token", "Title", "Body", labels=["feedback"])
