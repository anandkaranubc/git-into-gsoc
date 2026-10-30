"""A list cut short by GitHub's request limit says so, with when it resets and the fix."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx

from git_into_gsoc.errors import RateLimitError, reset_phrase
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.models import Availability, IssueCandidate, OrgSummary
from git_into_gsoc.service import GSoCToolkit

ORGS = [OrgSummary(name="Acme", github_orgs=["acme"], match_reasons=["Uses Go"])]


def _candidate(number: int, status: Availability) -> IssueCandidate:
    url = f"https://github.com/acme/lib/issues/{number}"
    return IssueCandidate(repo="acme/lib", number=number, title="x", url=url, availability=status)


def _toolkit(monkeypatch: Any, found: list[IssueCandidate], limit: RateLimitError | None):
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "search_organizations", lambda **k: (None, list(ORGS)))
    catalog = type("Catalog", (), {"year": 2026})()
    monkeypatch.setattr(toolkit.gsoc, "catalog", lambda year=None: (catalog, ORGS))

    def search(**kwargs: Any) -> list[IssueCandidate]:
        toolkit.github.rate_limited = limit  # as a timeline read would
        return found

    monkeypatch.setattr(toolkit.github, "find_beginner_issues", search)
    return toolkit


def _limit() -> RateLimitError:
    reset = datetime.now(UTC) + timedelta(minutes=21, seconds=30)
    return RateLimitError("GitHub API rate limit exceeded", reset_at=reset)


def test_unchecked_issues_say_the_limit_ran_out_and_how_to_fix_it(monkeypatch: Any) -> None:
    # A real no-token run (2026-10-22) ran out halfway through `issues --language go`:
    # 5 of 10 issues read "unknown" and nothing said why.
    found = [
        _candidate(1, Availability.AVAILABLE),
        *(_candidate(n, Availability.UNKNOWN) for n in (2, 3)),
    ]
    data = _toolkit(monkeypatch, found, _limit()).find_issues(language="go")
    note = data["note"]
    assert note.startswith(
        "GitHub's request limit ran out, so 2 issue(s) marked unknown were not checked "
        "for claims or pull requests. It resets in 22 minutes ("
    )
    assert "gh auth login" in note
    assert "Searching" in note  # the usual note follows


def test_no_note_when_every_issue_was_checked(monkeypatch: Any) -> None:
    found = [_candidate(1, Availability.AVAILABLE)]
    data = _toolkit(monkeypatch, found, _limit()).find_issues(language="go")
    assert "request limit" not in data["note"]


def test_a_limit_from_an_earlier_search_is_forgotten(monkeypatch: Any) -> None:
    # The MCP server keeps one client for many calls. Here the timeline read failed for
    # another reason, so the limit hit by the previous search must not be blamed.
    toolkit = _toolkit(monkeypatch, [], None)
    monkeypatch.setattr(
        toolkit.github,
        "find_beginner_issues",
        lambda **kwargs: [_candidate(1, Availability.UNKNOWN)],
    )
    toolkit.github.rate_limited = _limit()
    assert "request limit" not in toolkit.find_issues(language="go")["note"]


def test_the_reset_time_is_a_countdown() -> None:
    soon = datetime.now(UTC) + timedelta(seconds=30)
    assert reset_phrase(soon) == f"resets in 1 minute ({soon:%H:%M} UTC)"
    assert reset_phrase(None) == ""


@respx.mock
def test_a_timeline_read_that_hits_the_limit_is_remembered() -> None:
    reset = int(time.time()) + 600
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/lib/issues/7/timeline.*").mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        )
    )
    client = GitHubClient()
    assert client.get_issue_timeline("acme", "lib", 7) is None
    assert client.rate_limited is not None
    assert "resets in 10 minutes" in str(client.rate_limited)


@respx.mock
def test_the_remaining_count_is_never_read_from_the_cache() -> None:
    route = respx.get("https://api.github.com/rate_limit").mock(
        side_effect=[
            httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 60}}}),
            httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 3}}}),
        ]
    )
    client = GitHubClient()
    assert client.rate_limit()["remaining"] == 60
    assert client.rate_limit()["remaining"] == 3
    assert route.call_count == 2
