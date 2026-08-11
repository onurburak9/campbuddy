import httpx

GITHUB_API_URL = "https://api.github.com"


class GitHubIssueError(Exception):
    pass


def create_issue(
    repo: str, token: str, title: str, body: str, labels: list[str], timeout: float = 10.0
) -> dict:
    if not token:
        raise GitHubIssueError("GitHub token not configured")
    try:
        resp = httpx.post(
            f"{GITHUB_API_URL}/repos/{repo}/issues",
            json={"title": title, "body": body, "labels": labels},
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise GitHubIssueError(str(e)) from e
    if not resp.is_success:
        raise GitHubIssueError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()
