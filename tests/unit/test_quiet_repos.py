"""`issue` warns about repositories that will not review the work: archived or long quiet."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.models import Availability, IssueAssessment
from git_into_gsoc.service import GSoCToolkit


def _status(monkeypatch: Any, repo: dict[str, Any], **assessment: Any) -> dict[str, Any]:
    toolkit = GSoCToolkit()
    found = IssueAssessment(
        availability=Availability.AVAILABLE,
        reason="Open, unassigned, no open PR or recent claim",
        **assessment,
    )
    issue = {"title": "x", "html_url": "https://github.com/acme/lib/issues/9", "labels": []}
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: repo)
    return toolkit.issue_status("acme/lib#9")


def _pushed(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def test_an_issue_in_an_archived_repository_is_not_open(monkeypatch: Any) -> None:
    # A FOSSASIA beginner issue (2026-10-22) read "available" and told people to ask in
    # the thread, in a repository archived years ago where nobody can comment.
    data = _status(
        monkeypatch,
        {"archived": True, "pushed_at": _pushed(2200)},
        caveats=["@someone asked 223d ago with no PR; ask politely in the thread first"],
    )
    assert data["availability"] == "not_open"
    assert data["reason"].startswith("The repository is archived, so it is read-only")
    assert data["assessment"]["caveats"] == []


def test_a_repository_quiet_for_over_a_year_gets_a_warning(monkeypatch: Any) -> None:
    # A Processing library issue (2026-10-22): nothing pushed for 28 months.
    data = _status(monkeypatch, {"archived": False, "pushed_at": _pushed(852)})
    assert data["availability"] == "available"
    assert data["assessment"]["caveats"] == [
        "Nothing has been pushed to this repository for 28 months, so a pull request may wait "
        "a long time for review; ask the project whether it is still maintained before you start"
    ]


def test_an_active_repository_gets_no_warning(monkeypatch: Any) -> None:
    data = _status(monkeypatch, {"archived": False, "pushed_at": _pushed(20)})
    assert data["assessment"]["caveats"] == []


def test_a_repository_that_says_it_is_deprecated_is_mentioned(monkeypatch: Any) -> None:
    data = _status(
        monkeypatch,
        {"archived": False, "pushed_at": _pushed(20), "description": "Deprecated: use lib2"},
    )
    assert data["availability"] == "available"
    assert data["assessment"]["caveats"] == [
        "The repository's description says 'Deprecated'; ask the project whether it still "
        "takes work"
    ]


def test_an_unreadable_repository_changes_nothing(monkeypatch: Any) -> None:
    from git_into_gsoc.errors import GigError

    toolkit = GSoCToolkit()
    found = IssueAssessment(availability=Availability.AVAILABLE, reason="Open")
    issue = {"title": "x", "html_url": "https://github.com/acme/lib/issues/9", "labels": []}
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))

    def fail(owner: str, name: str) -> dict[str, Any]:
        raise GigError("down")

    monkeypatch.setattr(toolkit.github, "get_repo", fail)
    data = toolkit.issue_status("acme/lib#9")
    assert data["availability"] == "available"
    assert data["assessment"]["caveats"] == []


def test_the_start_list_leaves_out_quiet_repositories(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    repos = {
        "acme/live": {"pushed_at": _pushed(10)},
        "acme/quiet": {"pushed_at": _pushed(500)},
        "acme/old": {"archived": True, "pushed_at": _pushed(10)},
    }
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, n: repos[f"{o}/{n}"])
    kept = toolkit._without_retired_repos([{"repo": r} for r in repos])
    assert [i["repo"] for i in kept] == ["acme/live"]
