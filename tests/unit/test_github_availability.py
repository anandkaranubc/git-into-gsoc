from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx

from git_into_gsoc.github.availability import assess_issue, is_claim, is_grant
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.models import Availability

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def _iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _issue(**overrides: Any) -> dict[str, Any]:
    base = {
        "state": "open",
        "assignee": None,
        "assignees": [],
        "body": "Steps to reproduce: ...",
        "comments": 1,
        "updated_at": _iso(3),
    }
    base.update(overrides)
    return base


def _comment(login: str, body: str, days_ago: int, role: str = "NONE") -> dict[str, Any]:
    return {
        "event": "commented",
        "user": {"login": login, "type": "User"},
        "body": body,
        "created_at": _iso(days_ago),
        "author_association": role,
    }


def _pr(number: int, state: str, author: str = "dev", merged: bool = False) -> dict[str, Any]:
    return {
        "event": "cross-referenced",
        "created_at": _iso(2),
        "source": {
            "issue": {
                "number": number,
                "html_url": f"https://github.com/acme/lib/pull/{number}",
                "state": state,
                "user": {"login": author},
                "pull_request": {"merged_at": _iso(1) if merged else None},
            }
        },
    }


def test_available_when_quiet() -> None:
    result = assess_issue(_issue(), [], now=NOW)
    assert result.availability == Availability.AVAILABLE


def test_closed_and_assigned() -> None:
    assert assess_issue(_issue(state="closed"), [], now=NOW).availability == Availability.CLOSED
    assigned = assess_issue(_issue(assignees=[{"login": "bob"}]), [], now=NOW)
    assert assigned.availability == Availability.ASSIGNED
    assert "@bob" in assigned.reason


def test_open_linked_pr_marks_likely_taken() -> None:
    result = assess_issue(_issue(), [_pr(42, "open", "carol")], now=NOW)
    assert result.availability == Availability.LIKELY_TAKEN
    assert "#42" in result.reason and "@carol" in result.reason


def test_closed_pr_does_not_block_but_merged_pr_is_a_caveat() -> None:
    result = assess_issue(_issue(), [_pr(7, "closed"), _pr(8, "closed", merged=True)], now=NOW)
    assert result.availability == Availability.AVAILABLE
    assert any("merged PR" in c for c in result.caveats)


def test_recent_claim_in_comments() -> None:
    timeline = [_comment("dave", "Hi! Can I work on this issue?", 5)]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.CLAIMED
    assert "@dave" in result.reason


def test_maintainer_grant_confirms_claim() -> None:
    timeline = [
        _comment("erin", "I'd like to work on this", 40),
        _comment("maint", "@erin go ahead!", 39, role="MEMBER"),
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.CLAIMED
    assert "approved" in result.reason
    assert result.maintainer_engaged


def test_many_claimants_is_contested() -> None:
    timeline = [
        _comment(f"user{i}", "Please assign this to me", days)
        for i, days in enumerate([50, 41, 33])
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.CONTESTED
    assert len(result.claims) == 3


def test_old_claim_without_pr_is_available_with_caveat() -> None:
    timeline = [_comment("frank", "I will take this", 120)]
    result = assess_issue(_issue(updated_at=_iso(120)), timeline, now=NOW)
    assert result.availability == Availability.AVAILABLE
    assert any("@frank" in c for c in result.caveats)


def test_bots_and_maintainers_are_not_claimants() -> None:
    timeline = [
        {
            **_comment("dependabot[bot]", "I'm working on it", 1),
            "user": {"login": "dependabot[bot]", "type": "Bot"},
        },
        _comment("owner", "I am working on this myself", 1, role="OWNER"),
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.claims == []


def test_stale_without_maintainers() -> None:
    result = assess_issue(_issue(updated_at=_iso(500)), [], now=NOW)
    assert result.availability == Availability.STALE


def test_claim_and_grant_phrases() -> None:
    assert is_claim("Hey, could I please work on this?")
    assert is_claim("I'm working on it now")
    assert not is_claim("This is working on my machine")
    assert is_grant("Sure, go ahead")
    assert not is_grant("Thanks for the report")


@respx.mock
def test_find_beginner_issues_verifies_top_candidates_in_parallel() -> None:
    def search_item(number: int, repo: str) -> dict[str, Any]:
        return {
            "id": number,
            "number": number,
            "title": f"Fix docs {number}",
            "html_url": f"https://github.com/{repo}/issues/{number}",
            "repository_url": f"https://api.github.com/repos/{repo}",
            "labels": [{"name": "good first issue"}],
            "state": "open",
            "assignees": [],
            "comments": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "body": "Expected: link works. Steps to reproduce: click it.",
        }

    items = [search_item(n, "acme/lib") for n in (1, 2, 3)] + [search_item(4, "acme/docs")]
    search = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": items})
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/lib/issues/1/timeline.*").mock(
        return_value=httpx.Response(
            200, json=[{**_pr(9, "open"), "created_at": datetime.now(UTC).isoformat()}]
        )
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/.*/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    results = GitHubClient().find_beginner_issues(
        language="python", org="acme", max_results=3, org_names={"acme": "Acme Org"}
    )
    query = search.calls[0].request.url.params["q"]
    assert "-linked:pr" in query and "archived:false" in query and "org:acme" in query
    assert "stars:" not in query
    assert len(results) == 3
    assert sum(1 for r in results if r.repo == "acme/lib") <= 2
    assert results[0].availability == Availability.AVAILABLE
    assert all(r.gsoc_org == "Acme Org" for r in results)


@respx.mock
def test_assess_reports_unknown_when_the_timeline_cannot_be_read() -> None:
    respx.get("https://api.github.com/repos/acme/lib/issues/7").mock(
        return_value=httpx.Response(
            200,
            json={**_issue(), "number": 7, "html_url": "https://github.com/acme/lib/issues/7"},
        )
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/lib/issues/7/timeline.*").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )
    _, assessment = GitHubClient().assess("acme/lib", 7)
    assert assessment.availability == Availability.UNKNOWN
    assert "timeline" in assessment.reason


def test_bot_command_claims_count_as_claims() -> None:
    for body in ("/assign", "/assign-me", ".take", "@zulipbot claim", "@rustbot claim", "/take"):
        timeline = [_comment("gina", body, 2)]
        result = assess_issue(_issue(), timeline, now=NOW)
        assert result.availability == Availability.CLAIMED, body
        assert result.claims[0].login == "gina"


def test_release_comments_clear_an_earlier_claim() -> None:
    timeline = [
        _comment("hank", "/assign", 10),
        _comment("hank", "/unassign", 5),
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.AVAILABLE
    assert result.claims == []
    assert any("released" in c.lower() for c in result.caveats)


def test_bot_auto_unassign_clears_claim_by_mention() -> None:
    timeline = [
        _comment("ivy", "I'd like to work on this", 20),
        {
            **_comment(
                "helper[bot]",
                "@ivy has been unassigned due to inactivity. The issue is open again.",
                3,
            ),
            "user": {"login": "helper[bot]", "type": "Bot"},
        },
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.AVAILABLE
    assert result.claims == []


def test_unassigned_event_clears_claim() -> None:
    timeline = [
        _comment("jo", "please assign this to me", 8),
        {"event": "assigned", "assignee": {"login": "jo"}, "created_at": _iso(7)},
        {"event": "unassigned", "assignee": {"login": "jo"}, "created_at": _iso(2)},
    ]
    result = assess_issue(_issue(), timeline, now=NOW)
    assert result.availability == Availability.AVAILABLE
    assert result.claims == []


@respx.mock
def test_find_issues_for_one_repo_uses_its_own_beginner_label() -> None:
    from git_into_gsoc.service import GSoCToolkit

    respx.get(url__startswith="https://summerofcode.withgoogle.com/").mock(
        return_value=httpx.Response(503)
    )
    respx.get(url__startswith="https://api.gsocorganizations.dev/").mock(
        return_value=httpx.Response(503)
    )
    respx.get("https://api.github.com/repos/acme/lib/labels").mock(
        return_value=httpx.Response(200, json=[{"name": "Difficulty: Easy"}, {"name": "bug"}])
    )
    search = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    data = GSoCToolkit().find_issues(repo="acme/lib", max_results=3)
    query = search.calls[0].request.url.params["q"]
    assert 'label:"Difficulty: Easy"' in query and 'label:"good first issue"' in query
    assert data["labels_used"][0] == "Difficulty: Easy"


def test_reserved_label_marks_an_issue_as_taken() -> None:
    issue: dict[str, Any] = {
        "state": "open",
        "labels": [{"name": "good first issue"}, {"name": "In Progress"}],
        "updated_at": NOW.isoformat(),
    }
    assessment = assess_issue(issue, [], now=NOW)
    assert assessment.availability == Availability.CLAIMED
    assert "In Progress" in assessment.reason
    free = assess_issue({**issue, "labels": [{"name": "good first issue"}]}, [], now=NOW)
    assert free.availability == Availability.AVAILABLE
    suffixed = assess_issue(
        {**issue, "labels": [{"name": "good first issue (taken)"}]}, [], now=NOW
    )
    assert suffixed.availability == Availability.CLAIMED
    unassigned = assess_issue({**issue, "labels": [{"name": "needs-assignment"}]}, [], now=NOW)
    assert unassigned.availability == Availability.AVAILABLE
