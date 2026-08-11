from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.services.exceptions import UpstreamError
from core.services.feedback import submit_feedback
from core.services.github_client import GitHubIssueError


def make_user():
    return SimpleNamespace(id=7, email="alice@example.com")


def make_settings(**overrides):
    s = MagicMock()
    s.github_token = "ghp_token"
    s.github_feedback_repo = "onurburak9/campbuddy"
    s.feedback_notify_email = ""
    s.smtp_user = "owner@example.com"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_submit_feedback_creates_github_issue_on_success(mocker):
    create_issue = mocker.patch("core.services.feedback.github_client.create_issue", return_value={"number": 1})
    send_email = mocker.patch("core.services.feedback.notifier.send_feedback_email")
    submit_feedback(make_user(), "/scans/12", "Button does nothing", make_settings())
    create_issue.assert_called_once()
    args, kwargs = create_issue.call_args
    assert args[0] == "onurburak9/campbuddy"
    assert args[1] == "ghp_token"
    assert kwargs["labels"] == ["feedback"]
    assert "/scans/12" in args[3]
    assert "alice@example.com" in args[3]
    assert "Button does nothing" in args[3]
    send_email.assert_not_called()


def test_submit_feedback_falls_back_to_email_on_github_failure(mocker):
    mocker.patch("core.services.feedback.github_client.create_issue", side_effect=GitHubIssueError("401"))
    send_email = mocker.patch("core.services.feedback.notifier.send_feedback_email")
    settings = make_settings()
    submit_feedback(make_user(), "/scans/12", "Button does nothing", settings)
    send_email.assert_called_once_with("owner@example.com", "/scans/12", "alice@example.com", "Button does nothing", settings)


def test_submit_feedback_uses_feedback_notify_email_when_set(mocker):
    mocker.patch("core.services.feedback.github_client.create_issue", side_effect=GitHubIssueError("401"))
    send_email = mocker.patch("core.services.feedback.notifier.send_feedback_email")
    settings = make_settings(feedback_notify_email="specific-owner@example.com")
    submit_feedback(make_user(), "/scans/12", "Button does nothing", settings)
    send_email.assert_called_once_with("specific-owner@example.com", "/scans/12", "alice@example.com", "Button does nothing", settings)


def test_submit_feedback_raises_upstream_error_when_both_fail(mocker):
    mocker.patch("core.services.feedback.github_client.create_issue", side_effect=GitHubIssueError("401"))
    mocker.patch("core.services.feedback.notifier.send_feedback_email", side_effect=RuntimeError("smtp down"))
    with pytest.raises(UpstreamError):
        submit_feedback(make_user(), "/scans/12", "Button does nothing", make_settings())
