"""Look-alike pull requests that never link the issue: real matches and real false alarms."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.errors import GigError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.related import same_work, title_words
from git_into_gsoc.models import Availability, IssueAssessment, LinkedPullRequest
from git_into_gsoc.service import GSoCToolkit


def _pull(number: int, title: str, body: str = "", **extra: Any) -> dict[str, Any]:
    return {"number": number, "title": title, "body": body, "state": "open", **extra}


@pytest.mark.parametrize(
    ("issue", "number", "pull"),
    [
        # Each pair was reviewed by hand on 2026-10-22 and is the same work.
        ("Illegal reflective access warning", 8, "Fix illegal reflective access warnings"),
        (
            "Rename project from countvote to agora",
            20,
            "Renamed project references from countvote to agora",
        ),
        (
            "Workflow to differentiate in Dev and Production mode.",
            6,
            "Added:Workflow to differentiate in Dev and Production mode",
        ),
        (
            "SDP should have a more general linear operator constraint",
            72,
            "Add more general linear operator constraint to sdp",
        ),
    ],
)
def test_pull_requests_doing_the_same_work_match(issue: str, number: int, pull: str) -> None:
    assert same_work(number, title_words(issue), _pull(1, pull))


@pytest.mark.parametrize(
    ("issue", "number", "pull"),
    [
        # Real false alarms of a looser rule: two shared words, or another issue's work.
        (
            "Masonry: stale doc comment on Palette describes a component that no longer exists",
            877,
            "#843 | feat(masonry): show a brick's tooltip on hover in the palette",
        ),
        (
            "[Template] Create a AWS architecture template",
            12500,
            "Data Flow Diagram (DFD) Level 1 Architecture Template",
        ),
        (
            "[Feature Request]: Migrate acceptance tests for logged-in-user from Puppeteer to Playwright",
            26832,
            "Fix part of #26838: Migrate site-moderator acceptance test to Playwright",
        ),
    ],
)
def test_look_alikes_from_other_work_do_not_match(issue: str, number: int, pull: str) -> None:
    assert not same_work(number, title_words(issue), _pull(1, pull))


def test_a_title_of_common_words_alone_is_never_matched() -> None:
    # "Documentation (README) update" says nothing a README pull request would not.
    assert title_words("Documentation (README) update") == []


@respx.mock
def test_the_search_asks_for_newer_pull_requests_with_the_title_words() -> None:
    issue = {
        "number": 20,
        "title": "Rename project from countvote to agora",
        "created_at": "2025-01-05T00:00:00Z",
    }
    pulls = [
        _pull(
            22,
            "Renamed project references from countvote to agora",
            pull_request={"merged_at": None},
        ),
        _pull(23, "Rename the voting module", pull_request={"merged_at": None}),
    ]
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": pulls})
    )
    found = GitHubClient().unlinked_pulls("acme", "agora", issue)
    query = route.calls[0].request.url.params["q"]
    assert query.startswith("repo:acme/agora is:pr created:>=2025-01-05 ")
    assert [p["number"] for p in found] == [22]


def _status(
    monkeypatch: Any, pulls: list[dict[str, Any]] | Exception, linked: tuple[int, ...] = ()
) -> list[str]:
    toolkit = GSoCToolkit()
    found = IssueAssessment(
        availability=Availability.AVAILABLE,
        reason="Open",
        linked_prs=[LinkedPullRequest(number=n, state="closed") for n in linked],
    )
    issue = {"title": "x", "html_url": "https://github.com/acme/lib/issues/9", "labels": []}
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: {})

    def unlinked(owner: str, name: str, raw: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(pulls, Exception):
            raise pulls
        return pulls

    monkeypatch.setattr(toolkit.github, "unlinked_pulls", unlinked)
    return toolkit.issue_status("acme/lib#9")["assessment"]["caveats"]


def test_each_kind_of_look_alike_gets_advice(monkeypatch: Any) -> None:
    caveats = _status(
        monkeypatch,
        [
            _pull(
                13,
                "Fix illegal reflective access warnings",
                state="closed",
                pull_request={"merged_at": "2025-01-01T00:00:00Z"},
            ),
            _pull(22, "Renamed project references", pull_request={"merged_at": None}),
        ],
    )
    assert caveats == [
        'Merged PR #13 "Fix illegal reflective access warnings" looks like the same work but '
        "does not link this issue; it may already be fixed, so ask in the thread before you start",
        'Open PR #22 "Renamed project references" looks like the same work but does not link '
        "this issue; read it before you start, someone may already be on it",
    ]
    closed = _status(
        monkeypatch, [_pull(5, "Old try", state="closed", pull_request={"merged_at": None})]
    )
    assert closed == [
        'PR #5 "Old try" tried what looks like the same work and was closed without merging; '
        "read its review comments first"
    ]


def test_already_linked_or_unreadable_adds_nothing(monkeypatch: Any) -> None:
    assert _status(monkeypatch, [_pull(22, "Same work")], linked=(22,)) == []
    assert _status(monkeypatch, GigError("search failed")) == []


def test_a_search_cut_short_by_the_limit_says_so(monkeypatch: Any) -> None:
    # 0.17.0 on 2026-10-22: a busy token hit GitHub's secondary search limit, and `issue`
    # silently showed no look-alike pull requests, which read as "there are none".
    from datetime import UTC, datetime, timedelta

    from git_into_gsoc.errors import RateLimitError

    toolkit = GSoCToolkit()
    found = IssueAssessment(availability=Availability.AVAILABLE, reason="Open")
    issue = {"title": "x", "html_url": "https://github.com/acme/lib/issues/9", "labels": []}
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: {})
    reset = datetime.now(UTC) + timedelta(seconds=50)

    def limited(owner: str, name: str, raw: dict[str, Any]) -> list[dict[str, Any]]:
        toolkit.github.rate_limited = RateLimitError("limit", reset_at=reset, resource="search")
        return []

    monkeypatch.setattr(toolkit.github, "unlinked_pulls", limited)
    caveats = toolkit.issue_status("acme/lib#9")["assessment"]["caveats"]
    assert caveats == [
        "GitHub's search limit stopped the check for pull requests that look like the same "
        f"work; it resets in 1 minute ({reset:%H:%M} UTC), so run this again then"
    ]


@respx.mock
def test_the_client_remembers_a_limited_search() -> None:
    issue = {"number": 20, "title": "Rename project from countvote to agora"}
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            403,
            json={"message": "You have exceeded a secondary rate limit."},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-resource": "search"},
        )
    )
    client = GitHubClient()
    assert client.unlinked_pulls("acme", "agora", issue) == []
    assert client.rate_limited is not None
