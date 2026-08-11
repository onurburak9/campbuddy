import logging
from datetime import datetime, timezone

from core import notifier
from core.services import github_client
from core.services.exceptions import UpstreamError

logger = logging.getLogger(__name__)


def submit_feedback(user, page_path: str, message: str, settings) -> None:
    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = f"Feedback from {user.email}"
    body = (
        f"**Page:** {page_path}\n"
        f"**User:** {user.email} (user_id={user.id})\n"
        f"**Submitted:** {submitted_at}\n\n"
        f"---\n{message}\n"
    )
    try:
        github_client.create_issue(
            settings.github_feedback_repo, settings.github_token, title, body, labels=["feedback"],
        )
        return
    except github_client.GitHubIssueError as e:
        logger.warning("GitHub issue creation failed, falling back to email: %s", e)

    try:
        notifier.send_feedback_email(
            settings.feedback_notify_email or settings.smtp_user, page_path, user.email, message, settings,
        )
    except Exception as e:
        raise UpstreamError(f"Failed to deliver feedback via GitHub or email: {e}") from e
