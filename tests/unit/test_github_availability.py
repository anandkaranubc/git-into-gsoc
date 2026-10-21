from __future__ import annotations

from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.models import Availability


class StubGitHub(GitHubClient):
    def __init__(self, issue: dict, timeline: list | None = None) -> None:
        self._issue = issue
        self._timeline = timeline or []
        self.settings = type(
            "S",
            (),
            {"github_api_url": "https://api.github.com", "resolve_github_token": lambda self: None},
        )()
        self.token = None
        self.http = None

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return self._issue

    def get_issue_timeline(self, owner: str, repo: str, number: int) -> list:
        return self._timeline


def test_assigned_issue() -> None:
    client = StubGitHub(
        {
            "state": "open",
            "assignee": {"login": "bob"},
            "assignees": [{"login": "bob"}],
            "body": "",
            "comments": 0,
            "updated_at": "2026-10-01T00:00:00Z",
        }
    )
    status, reason = client.check_issue_availability("acme/lib", 1)
    assert status == Availability.ASSIGNED
    assert "bob" in reason


def test_available_issue() -> None:
    client = StubGitHub(
        {
            "state": "open",
            "assignee": None,
            "assignees": [],
            "body": "Please fix the docs path.",
            "comments": 1,
            "updated_at": "2026-10-15T00:00:00Z",
        }
    )
    status, reason = client.check_issue_availability("acme/lib", 2)
    assert status == Availability.AVAILABLE
    assert (
        "unassigned" in reason.lower()
        or "available" in reason.lower()
        or "no linked" in reason.lower()
    )


def test_linked_pr_marks_likely_taken() -> None:
    client = StubGitHub(
        {
            "state": "open",
            "assignee": None,
            "assignees": [],
            "body": "",
            "comments": 2,
            "updated_at": "2026-10-15T00:00:00Z",
        },
        timeline=[
            {
                "event": "cross-referenced",
                "source": {"issue": {"pull_request": {}, "state": "open"}},
            }
        ],
    )
    status, _ = client.check_issue_availability("acme/lib", 3)
    assert status == Availability.LIKELY_TAKEN
