"""`next` lists new beginner issues in tracked GitLab projects and GitLab-hosted orgs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from git_into_gsoc.errors import NotFoundError
from git_into_gsoc.models import Availability, IssueCandidate, OrgSummary, ProgressState
from git_into_gsoc.service import GSoCToolkit


def _candidate(
    repo: str, number: int, days: int, availability: Availability = Availability.AVAILABLE
) -> IssueCandidate:
    return IssueCandidate(
        repo=repo,
        number=number,
        title=f"Issue {number}",
        url=f"https://{repo}/-/issues/{number}",
        labels=["4. Newcomers"],
        created_at=datetime.now(UTC) - timedelta(days=days),
        availability=availability,
    )


def test_new_issues_come_from_tracked_gitlab_projects_and_orgs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = GSoCToolkit()
    gnome = OrgSummary(
        name="GNOME Foundation", github_orgs=[], source_code="https://gitlab.gnome.org/"
    )
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: gnome)
    asked: list[tuple[str, str]] = []

    def search(http: Any, host: str, path: str, **kwargs: Any) -> list[IssueCandidate]:
        asked.append((host, path))
        if path == "GNOME/gitg":
            return [
                _candidate("gitlab.gnome.org/GNOME/gitg", 500, 2),
                _candidate("gitlab.gnome.org/GNOME/gitg", 400, 40),
                _candidate("gitlab.gnome.org/GNOME/gitg", 300, 1, Availability.LIKELY_TAKEN),
            ]
        # The group search finds gitg's new issue again, plus nautilus.
        return [
            _candidate("gitlab.gnome.org/GNOME/nautilus", 9, 1),
            _candidate("gitlab.gnome.org/GNOME/gitg", 500, 2),
        ]

    monkeypatch.setattr("git_into_gsoc.service.search_gitlab_issues", search)
    state = ProgressState(
        tracked_repos=["https://gitlab.gnome.org/GNOME/gitg"],
        shortlisted_orgs=["GNOME Foundation"],
        last_checked_at=datetime.now(UTC) - timedelta(days=7),
    )
    found = toolkit._new_beginner_issues(state, now=datetime.now(UTC))
    assert found is not None
    assert [(i["repo"], i["number"]) for i in found] == [
        ("gitlab.gnome.org/GNOME/nautilus", 9),
        ("gitlab.gnome.org/GNOME/gitg", 500),
    ]  # newest first, once each; the taken one and the 40-day-old one are left out
    assert found[0]["url"] == "https://gitlab.gnome.org/GNOME/nautilus/-/issues/9"
    assert asked == [("gitlab.gnome.org", "GNOME/gitg"), ("gitlab.gnome.org", "GNOME")]


def test_a_gitlab_place_that_does_not_answer_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = GSoCToolkit()

    def down(*args: Any, **kwargs: Any) -> list[IssueCandidate]:
        raise NotFoundError("no answer", status_code=404)

    monkeypatch.setattr("git_into_gsoc.service.search_gitlab_issues", down)
    state = ProgressState(tracked_repos=["https://gitlab.com/qemu-project/qemu"])
    assert toolkit._new_beginner_issues(state, now=datetime.now(UTC)) == []
