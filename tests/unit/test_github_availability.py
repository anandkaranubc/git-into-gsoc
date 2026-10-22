"""Whether an issue is free: the timeline rules, claim phrasings from real comments, releases,
grants, and the issue search that uses them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
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


def test_closed_unmerged_pr_is_reported_as_an_earlier_attempt() -> None:
    issue: dict[str, Any] = {"state": "open", "updated_at": NOW.isoformat()}
    abandoned = {
        "event": "cross-referenced",
        "created_at": (NOW - timedelta(days=40)).isoformat(),
        "source": {
            "issue": {
                "number": 12,
                "html_url": "https://github.com/o/r/pull/12",
                "state": "closed",
                "user": {"login": "someone"},
                "pull_request": {"merged_at": None},
            }
        },
    }
    assessment = assess_issue(issue, [abandoned], now=NOW)
    assert assessment.availability == Availability.AVAILABLE
    assert any(
        c.startswith("#12 tried this and was closed without merging") for c in assessment.caveats
    )
    reopened = {
        **abandoned,
        "source": {"issue": {**abandoned["source"]["issue"], "number": 13, "state": "open"}},
    }
    still_open = assess_issue(issue, [abandoned, reopened], now=NOW)
    assert still_open.availability == Availability.LIKELY_TAKEN
    assert not any("closed without merging" in c for c in still_open.caveats)


def test_a_long_idle_open_pr_says_how_to_ask() -> None:
    issue: dict[str, Any] = {"state": "open", "updated_at": NOW.isoformat()}

    def linked(days_idle: int) -> dict[str, Any]:
        return {
            "event": "cross-referenced",
            "created_at": (NOW - timedelta(days=200)).isoformat(),
            "source": {
                "issue": {
                    "number": 30,
                    "html_url": "https://github.com/o/r/pull/30",
                    "state": "open",
                    "user": {"login": "someone"},
                    "updated_at": (NOW - timedelta(days=days_idle)).isoformat(),
                    "pull_request": {"merged_at": None},
                }
            },
        }

    stale = assess_issue(issue, [linked(120)], now=NOW)
    assert stale.availability == Availability.LIKELY_TAKEN
    assert stale.reason == "Open PR #30 by @someone references it; it has been idle for 120 days"
    assert any("ask in the issue" in c for c in stale.caveats)
    fresh = assess_issue(issue, [linked(5)], now=NOW)
    assert fresh.reason == "Open PR #30 by @someone references it"
    assert not any("ask in the issue" in c for c in fresh.caveats)


@respx.mock
def test_one_big_org_cannot_fill_the_whole_list() -> None:
    def item(number: int, repo: str) -> dict[str, Any]:
        return {
            "id": number,
            "number": number,
            "title": f"Fix {number}",
            "html_url": f"https://github.com/{repo}/issues/{number}",
            "repository_url": f"https://api.github.com/repos/{repo}",
            "labels": [{"name": "good first issue"}],
            "state": "open",
            "assignees": [],
            "comments": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "body": "Expected: works. Steps to reproduce: run it.",
        }

    # On 2026-10-21 every result of a plain `issues` run came from apache/*.
    items = [item(n, f"apache/repo{n}") for n in range(1, 7)]
    items += [item(10, "sympy/sympy"), item(11, "zulip/zulip")]
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": items})
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/.*/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    results = GitHubClient().find_beginner_issues(orgs=["apache", "sympy", "zulip"], max_results=6)
    owners = [r.repo.split("/")[0] for r in results]
    assert owners.count("apache") <= 3
    assert {"sympy", "zulip"} <= set(owners)


@respx.mock
def test_javascript_and_typescript_are_searched_together() -> None:
    search = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    GitHubClient().find_beginner_issues(language="JS", orgs=["jitsi"], max_results=3)
    GitHubClient().find_beginner_issues(language="python", orgs=["sympy"], max_results=3)
    js, py = (call.request.url.params["q"] for call in search.calls)
    assert "(language:javascript OR language:typescript)" in js
    assert "language:python" in py and "OR language" not in py


@respx.mock
def test_a_single_repository_search_is_not_capped_at_two() -> None:
    # A simulated run asked `issues --repo ArduPilot/ardupilot -n 40` and got 2.
    def item(number: int) -> dict[str, Any]:
        return {
            "id": number,
            "number": number,
            "title": f"Fix {number}",
            "html_url": f"https://github.com/acme/lib/issues/{number}",
            "repository_url": "https://api.github.com/repos/acme/lib",
            "labels": [{"name": "good first issue"}],
            "state": "open",
            "assignees": [],
            "comments": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "body": "Expected: works. Steps to reproduce: run it.",
        }

    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [item(n) for n in range(1, 7)]})
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/.*/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    results = GitHubClient().find_beginner_issues(repo="acme/lib", max_results=5)
    assert len(results) == 5


def test_an_issue_held_for_discussion_is_not_open_for_claims() -> None:
    # learning-unlimited/ESP-Website#2157 (2026-10-21): labelled "Idea for Discussion",
    # and the project's bot told claimants it "is not currently available for
    # assignment". `issue` still said "available", and `draft claim` wrote a claim.
    issue = _issue(labels=[{"name": "Starter"}, {"name": "Idea for Discussion"}])
    labelled = assess_issue(issue, [], now=NOW)
    assert labelled.availability == Availability.NOT_OPEN
    assert "Idea for Discussion" in labelled.reason

    bot = {
        "event": "commented",
        "created_at": _iso(40),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "body": "Sorry @someone, this issue is labeled **idea for discussion** and is not "
        "currently available for assignment.",
    }
    told = assess_issue(_issue(), [bot], now=NOW)
    assert told.availability == Availability.NOT_OPEN
    assert "not currently available for assignment" in told.reason


def test_an_approved_plan_and_a_maintainer_follow_up_keep_a_claim() -> None:
    # processing/p5.sound.js#57 (2026-10-21) showed "available" at the top of a list:
    # a member said "this sounds good" to a claimant 31 days ago, the claimant said
    # "I'd be happy to work on this", and the member checked in on them 4 days ago.
    timeline = [
        _comment("abhishek", "If this is still up for grabs I'd like to pick it up.", 59),
        _comment(
            "member", "hi @abhishek, this sounds good, can you still work on it?", 31, "MEMBER"
        ),
        _comment("abhishek", "Yes, absolutely! I'd be happy to work on this.", 31),
        _comment("member", "heya @abhishek are you still working on this?", 4, "MEMBER"),
    ]
    found = assess_issue(_issue(), timeline, now=NOW)
    assert found.availability == Availability.CLAIMED
    assert "approved @abhishek" in found.reason and "last active 4d ago" in found.reason
    assert is_claim("I'd be happy to work on this.")
    assert is_grant("Your plan looks good.")


def test_a_comment_pointing_at_an_open_pr_marks_the_issue_taken() -> None:
    # CircuitVerse/cv-frontend-vue#1411: two comments say open PR #1293 covers it,
    # but the PR never links the issue, so the timeline has no cross-reference.
    issue = _issue(number=1411, html_url="https://github.com/acme/app/issues/1411")
    timeline = [
        _comment("someone", "I think this is already covered by #1293.", 8, "CONTRIBUTOR"),
        _comment("other", "Could you confirm PR #1293 addresses this? See #12 too.", 2),
    ]
    looked_up: list[tuple[str, int]] = []

    def pull(repo: str, number: int) -> dict[str, Any] | None:
        looked_up.append((repo, number))
        if number != 1293:
            return None
        return {"number": 1293, "state": "open", "user": {"login": "author"}, "updated_at": _iso(8)}

    found = assess_issue(issue, timeline, now=NOW, pull_lookup=pull)
    assert found.availability == Availability.LIKELY_TAKEN
    assert found.reason == "A comment says open PR #1293 by @author covers it"
    # "#12 too" is not a PR mention; each pull request is read once
    assert looked_up == [("acme/app", 1293)]
    # Without a way to look pull requests up, nothing changes.
    assert assess_issue(issue, timeline, now=NOW).availability == Availability.AVAILABLE


def test_a_closed_pr_in_a_comment_does_not_count() -> None:
    issue = _issue(number=5, html_url="https://github.com/acme/app/issues/5")
    timeline = [
        _comment("a", "Fixed in #7 maybe?", 3),
        _comment("b", "Like https://github.com/other/lib/pull/9 did.", 2),
    ]
    looked_up: list[tuple[str, int]] = []

    def pull(repo: str, number: int) -> dict[str, Any] | None:
        looked_up.append((repo, number))
        return {"number": number, "state": "closed"}

    found = assess_issue(issue, timeline, now=NOW, pull_lookup=pull)
    assert found.availability == Availability.AVAILABLE
    assert looked_up == [("acme/app", 7), ("other/lib", 9)]


def test_an_open_pr_in_another_repository_named_in_a_comment_counts() -> None:
    # A Haskell security-advisories issue read "available" (2026-10-21) although a
    # collaborator wrote that it was "Completed in the pending" pull request in the
    # tool that consumes the advisories, a different repository.
    issue = _issue(number=215, html_url="https://github.com/acme/advisories/issues/215")
    timeline = [
        _comment(
            "helper",
            "Completed in the pending https://github.com/someone/audit-tool/pull/77",
            30,
            "COLLABORATOR",
        )
    ]

    def pull(repo: str, number: int) -> dict[str, Any] | None:
        assert (repo, number) == ("someone/audit-tool", 77)
        return {"number": 77, "state": "open", "user": {"login": "someone"}, "updated_at": _iso(9)}

    found = assess_issue(issue, timeline, now=NOW, pull_lookup=pull)
    assert found.availability == Availability.LIKELY_TAKEN
    # "#77" alone would send people to this repository's #77, a different pull request.
    assert found.reason == "A comment says open PR someone/audit-tool#77 by @someone covers it"


def test_a_pr_from_another_repository_is_named_with_its_repository() -> None:
    issue = _issue(number=3, html_url="https://github.com/acme/app/issues/3")
    # A fork keeps the project's name, and a sibling repository has the same owner:
    # their pull requests can fix the issue.
    for source in (
        "https://github.com/dev/app/pull/12",
        "https://github.com/acme/app-docs/pull/12",
    ):
        other = _pr(12, "open", "dev")
        other["source"]["issue"]["html_url"] = source
        found = assess_issue(issue, [other], now=NOW)
        where = source.split("github.com/")[1].split("/pull")[0]
        assert found.reason == f"Open PR {where}#12 by @dev references it", source


def test_a_pr_in_an_unrelated_project_that_mentions_the_issue_is_not_a_fix() -> None:
    # This tool's own repository once named a CircuitVerse issue in a merged pull
    # request, and `issue` then said "A merged PR references this issue; it may already
    # be partly fixed".
    issue = _issue(
        number=1411, html_url="https://github.com/CircuitVerse/cv-frontend-vue/issues/1411"
    )
    mention = _pr(154, "closed", "anandkaranubc", merged=True)
    mention["source"]["issue"]["html_url"] = (
        "https://github.com/anandkaranubc/git-into-gsoc/pull/154"
    )
    mention["source"]["issue"]["repository"] = {"full_name": "anandkaranubc/git-into-gsoc"}
    found = assess_issue(issue, [mention], now=NOW)
    assert found.availability == Availability.AVAILABLE
    assert found.linked_prs == []
    assert not any("may already be partly fixed" in c for c in found.caveats)
    assert any("anandkaranubc/git-into-gsoc#154" in c for c in found.caveats)


@pytest.mark.parametrize(
    "label",
    [
        "status: needs discussion",
        "needs:discussion",
        "needs-discussion",
        "Needs: Community Discussion",
        "further discussion required",
        "type: discussion",
        "status: in discussion",
        "todo: needs decisions",
        "status:needs design decision",
        "needs:design",
        "issue/design required",
        "status: blocked",
        "state: blocked",
        "blocked: upstream",
        "temporarily-blocked-from-assignment",
        "status: on hold",
    ],
)
def test_labels_that_hold_an_issue_back_count_however_they_are_spelled(label: str) -> None:
    # Measured on 24,779 labels from the top repositories of 144 GSoC organizations'
    # GitHub owners (2026-10-21). An App Inventor issue labelled "status: needs discussion" read
    # "available" because only the exact name "needs discussion" counted.
    found = assess_issue(_issue(labels=[{"name": "help wanted"}, {"name": label}]), [], now=NOW)
    assert found.availability == Availability.NOT_OPEN
    assert label in found.reason


@pytest.mark.parametrize(
    "label",
    ["blocker", "priority:blocker", "design", "redesign", "lifecycle/frozen", "unblocked"],
)
def test_labels_that_only_sound_like_a_hold_do_not_count(label: str) -> None:
    # "blocker" is a priority, "design" a topic, and "lifecycle/frozen" only stops a
    # bot from closing the issue.
    found = assess_issue(
        _issue(labels=[{"name": "good first issue"}, {"name": label}]), [], now=NOW
    )
    assert found.availability == Availability.AVAILABLE


@pytest.mark.parametrize(
    "body",
    [
        "This issue is reserved for gsoc, do not take over it",
        "@someone This issue is currently reserved for GSoC candidates, so I would suggest "
        "not putting work on this.",
        "Hey, this issue is reserved for a GSoC project.",
        "It falls under the GSoC scope, which is reserved for the selected contributor.",
        "This issue will be reserved for Google Summer of Code participation.",
    ],
)
def test_a_maintainer_reserving_an_issue_for_a_gsoc_project_holds_it(body: str) -> None:
    # Real wordings from GitHub comments (2026-10-21). The issue is the GSoC project
    # itself: the contributor selected for it does the work, so a newcomer should not.
    found = assess_issue(_issue(), [_comment("lead", body, 20, "MEMBER")], now=NOW)
    assert found.availability == Availability.NOT_OPEN
    assert "pick another issue" in found.reason


def test_issues_reserved_for_gsoc_applicants_stay_open() -> None:
    # The opposite meaning: these are kept for people preparing to apply.
    for body in [
        "The issues in this repo are reserved for gsoc applicants to solve and get familiar.",
        "We ask that this issue be reserved for those who are interested in applying to GSoC.",
    ]:
        found = assess_issue(_issue(), [_comment("lead", body, 20, "MEMBER")], now=NOW)
        assert found.availability == Availability.AVAILABLE, body
    # A newcomer asking is not the project saying so.
    asked = _comment("new", "Can I try this or is it reserved for GSoC?", 2)
    assert assess_issue(_issue(), [asked], now=NOW).availability != Availability.NOT_OPEN


def test_saying_you_already_tried_a_fix_is_a_claim() -> None:
    # Missed on a JPF issue and an App Inventor issue (2026-10-21): both people had
    # started the work, but the issue still read "available" with no word about them.
    assert is_claim("So I have tried to implement a solution for this issue; I hope it works.")
    assert is_claim("I've been looking into implementing SSE support on the Android side.")
    assert not is_claim("Have you tried to implement it with the old API first?")


def test_a_merged_pr_linked_as_an_example_is_not_said_to_reference_the_issue() -> None:
    # On a JPF issue (2026-10-21) a maintainer linked a sibling repository's merged PR
    # as the change to copy. It does not reference the issue and fixes nothing here.
    issue = _issue(number=8, html_url="https://github.com/jpf/nhandler/issues/8")
    body = "The idea is to apply changes from PR 373 here: https://github.com/jpf/core/pull/373"
    merged = {"number": 373, "state": "closed", "merged_at": _iso(800), "user": {"login": "v"}}
    found = assess_issue(
        issue, [_comment("lead", body, 700, "MEMBER")], now=NOW, pull_lookup=lambda r, n: merged
    )
    assert found.availability == Availability.AVAILABLE
    assert found.caveats == [
        "A comment links merged PR jpf/core#373; read it first, it may already fix this or "
        "show how to fix it"
    ]


C = "\u2019"  # the curly apostrophe phone keyboards type


def test_a_claim_typed_with_a_curly_apostrophe_counts() -> None:
    # OWASP/SecurityShepherd#411 (2026-10-21) showed as available: its only comment,
    # "I'd like to take this one", was typed with a curly apostrophe (C).
    assert is_claim(f"I{C}d like to take this one.")
    assert is_claim(f"I{C}m working on this")
    assert is_claim(f"I{C}ll take this")
    assert is_grant(f"That{C}s fine, go ahead")
    found = assess_issue(
        _issue(), [_comment("aadi", f"I{C}d like to take this one. Plan: ...", 10)], now=NOW
    )
    assert found.availability == Availability.CLAIMED


# Phrasings from real comments on beginner issues in GSoC organizations
# (2026-10-21, usernames removed). The older patterns caught 69% of the claims in a
# held-out half of 280 labelled comments; these forms were among the misses.
REAL_CLAIMS = [
    "Hi! I'm a new contributor and would like to work on this issue.",
    "I would like to be assigned to this issue",
    "Working on this",
    "I'm actively working on it.",
    "Can you please assign the issue to me",
    "I am interested in working on this issue.",
    "Is this issue still open for contribution",
    "I would love to take a stab at this issue",
    "can i try to add this along with its tutorial?",
    "I'd also like to work on this issue.",
    "id like to work on this",
    "please assign #826 to me",
]
NOT_CLAIMS = [
    "@someone let us know if u r still working on this issue",
    "Currently @someone is working on this issue. If anything changes, we will let you know!",
    "@someone let us know if you're still interested in working on this",
    "so you are open to work on this once the fix lands",
    "> I would like to work on this issue, if it is still available.\nThanks, merged.",
    "I can reproduce this on Linux too.",
]


def test_real_claim_phrasings_count_and_others_do_not() -> None:
    assert [text for text in REAL_CLAIMS if not is_claim(text)] == []
    assert [text for text in NOT_CLAIMS if is_claim(text)] == []


# A second sample: 333 comments from 20 other GSoC organizations (2026-10-21).
MORE_CLAIMS = [
    "Would love an assignment",
    "kindly delegate it to me",
    "I am still actively working on extending this",
    "I am planning to benchmark the two tools first",
    "Will get started right away.",
    "i wanna take it over",
    "I have the change ready",
    "I'd be interested in contributing to #2605.",
    "take",
    "Taking this one.",
    "I want to fix this issue",
]
MORE_NOT_CLAIMS = [
    "Thanks! Unfortunately I am not able to set up the environment, so could you please "
    "un-assign me so someone else can take it?",
    "How can I fix this in the code? I tried the template override.",
    "We'd like to add your quickstart to the docs website too.",
    "Should I add this to the main docs repo or keep it in the quickstart repo?",
]


def test_more_real_phrasings() -> None:
    assert [text for text in MORE_CLAIMS if not is_claim(text)] == []
    assert [text for text in MORE_NOT_CLAIMS if is_claim(text)] == []


def test_a_report_about_someone_else_does_not_cancel_a_claim() -> None:
    # "Since the current assignee is no longer working on this, I'm interested in
    # taking it up. Could you assign it to me?" was dropped as a release.
    text = (
        "Since the current assignee is no longer working on this, I'm interested in taking it"
        " up. Could you assign it to me?"
    )
    found = assess_issue(_issue(), [_comment("newcomer", text, 3)], now=NOW)
    assert found.availability == Availability.CLAIMED


# A third sample: 387 comments from 20 more GSoC organizations (2026-10-21). Checkstyle
# contributors split large issues with "I am on it" and "I'll cover <part>".
THIRD_SAMPLE_CLAIMS = [
    "I am on it",
    "I m on it",
    "I'll cover the remaining checks in this module",
    "I will take the last one",
    "I'm taking over this one",
    "Can this issue be assigned to me please?",
    "could I claim this one?",
    "I really want to work on this issue",
    "I'd be glad to submit a fix",
    "I was just working on this issue",
    "Would you mind if I tried working on this?",
    "should I submit a PR related to this?",
]
THIRD_SAMPLE_NOT_CLAIMS = [
    "I have raised a PR for this issue. If you have suggestions, I'd be glad to make changes.",
    "Is anyone working on it?",
]


def test_third_sample_phrasings() -> None:
    assert [text for text in THIRD_SAMPLE_CLAIMS if not is_claim(text)] == []
    assert [text for text in THIRD_SAMPLE_NOT_CLAIMS if is_claim(text)] == []


def test_many_old_requests_say_how_many_people_asked() -> None:
    # A cBioPortal issue had three requests over two years (2026-10-21). That is not
    # contested, but a beginner should know they would be the fourth.
    timeline = [
        _comment("a", "Can I work on this?", 300),
        _comment("b", "I'd like to work on this.", 200),
        _comment("c", "Is this still open for work?", 100),
    ]
    found = assess_issue(_issue(), timeline, now=NOW)
    assert found.availability == Availability.AVAILABLE
    assert found.caveats == [
        "3 people asked to work on this, the latest 100d ago, and none opened a PR; post a "
        "concrete plan instead of another request, or pick another issue"
    ]


@pytest.mark.parametrize(
    "text",
    [
        # Missed in the first three samples of real comments (2026-10-22).
        "yes i am working on it",
        "Happy to help with this one!",
        "Interested in helping here.",
        "Okay, I'll take.",
        "I would love to on this, so may i?",
        "I will update you on my progress shortly.",
        "If it is open I will love to fix it",
        "I am porting the script to PowerShell.",
        "I'll working on the parser part",
        "Also taking the Javadoc checks.",
        "please assigned it to me",
        "Would it be okay if I handle the second half?",
        "I'm willing to contribute to this.",
        "I would be happy to explore the implementation.",
        "/attempt",
    ],
)
def test_more_ways_of_taking_an_issue_count(text: str) -> None:
    assert is_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "I'll take a look at the logs tomorrow.",
        "I am on Windows 11 with Python 3.12.",
        "Taking the example above, the output is wrong.",
        "I've made the changes you asked for in the PR.",
        "Please review it before I proceed with the remaining parts.",
    ],
)
def test_near_misses_are_not_claims(text: str) -> None:
    assert not is_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        # From a fourth sample of real comments in 17 new organizations (2026-10-22).
        "Picking this up",
        "Happy to pick this up",
        "Can I pick this issue up?",
        "i am starting on it",
        "assign this task to me",
        "Interested, Please assign",
        "i would like work on this issue.",
        "im interested to work in this issue",
        "I'm thinking of giving this a shot.",
        "I will raise the PR",
        "still on this one",
        "In Progress",
        "PR soon.",
    ],
)
def test_forms_from_new_organizations_count(text: str) -> None:
    assert is_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "Could you update the issue so that someone else can pick it up?",
        "Thanks for picking this up. I'll step back to avoid duplicating your work.",
        "@someone are you still working on it?",
        "Is anyone still on this?",
    ],
)
def test_talking_about_someone_else_is_not_a_claim(text: str) -> None:
    assert not is_claim(text)


def test_a_pr_merged_before_the_issue_was_opened_is_not_its_fix() -> None:
    # An MDAnalysis issue (blind beginner test, 2026-10-22) opens with "Follow-up on PR
    # #1695", merged 26 minutes earlier; `issue` still said that PR "may already fix this".
    issue = _issue(
        number=1721,
        html_url="https://github.com/acme/lib/issues/1721",
        created_at=_iso(400),
    )
    before = {"number": 1695, "state": "closed", "merged_at": _iso(401), "user": {"login": "a"}}
    linked = _pr(1700, "closed", merged=True)
    linked["source"]["issue"]["pull_request"]["merged_at"] = _iso(402)
    found = assess_issue(
        issue,
        [linked, _comment("b", "I've read PR #1695 and its review comments.", 30)],
        now=NOW,
        pull_lookup=lambda r, n: before,
    )
    assert not any("may already" in c for c in found.caveats)
    # The same pull request merged after the issue opened still raises the question.
    after = {**before, "merged_at": _iso(10)}
    later = assess_issue(
        issue, [_comment("b", "See PR #1695.", 5)], now=NOW, pull_lookup=lambda r, n: after
    )
    assert any("may already fix this or show how to fix it" in c for c in later.caveats)


def test_a_second_person_asking_to_work_together_is_a_claim() -> None:
    # A maintainer told two newcomers to collaborate on an MDAnalysis issue; the second
    # one's "we could work together" was not seen.
    assert is_claim("Sure, if possible we could work together @spyke7. Thank you.")
    assert not is_claim("Could you work together with the docs team on this?")


def test_claims_from_a_fifth_sample_of_new_organizations() -> None:
    # Forms from the tuning half of a fifth sample (568 comments from 21 organizations
    # never sampled before, labelled blind, 2026-10-22).
    claims = [
        "I shall work on it",
        "may I address this issue?",
        "please let me work on this",
        "Please assign it.",
        "could you please add me as a co-assignee",
        "I can take up this issue",
        "I will open PR soon.",
        "I have just implemented it and I'm raising the PR.",
        "I started implementing the requested mode",
        "taking this up as discussed on Slack!",
        "I have self assigned this issue.",
        "I have made minimal changes to fix this.",
        "My work is ready for PR",
        "Can we both collab?",
        "I will take a look into this issue.",
        "I am interested",
        "@openwisp-companion assign",
        "C:/Program Files/Git/assign",  # Git Bash on Windows rewrote "/assign"
    ]
    for text in claims:
        assert is_claim(text), text
    not_claims = [
        "Please assign it to someone who knows the parser.",
        "I am interested in how this works internally.",
        "Can we both agree this is a duplicate?",
        "I will take a look at the logs tomorrow and report the error.",
        "@reviewer please take another look",
    ]
    for text in not_claims:
        assert not is_claim(text), text


def _merged_pr(number: int, body: str, *, merged_days_ago: int = 1) -> dict[str, Any]:
    event = _pr(number, "closed", merged=True)
    event["source"]["issue"]["body"] = body
    event["source"]["issue"]["title"] = "Remove dead config"
    event["source"]["issue"]["pull_request"]["merged_at"] = _iso(merged_days_ago)
    return event


def test_a_merged_pr_that_says_it_fixes_the_issue_makes_it_likely_taken() -> None:
    # mofa's issue 671 stayed open for seven months after "- Fixes issue #671" was
    # merged: GitHub closes issues only for "Fixes #671". `recommend` showed it as free.
    issue = _issue(number=671, html_url="https://github.com/acme/lib/issues/671")
    found = assess_issue(issue, [_merged_pr(672, "Summary\n- Fixes issue #671\n")], now=NOW)
    assert found.availability == Availability.LIKELY_TAKEN
    assert found.reason.startswith("Merged PR #672 says it fixes this, though the issue is still")
    assert not any("partly fixed" in c for c in found.caveats)
    # A merged PR that only mentions the issue is still a caveat, as before.
    mention = assess_issue(issue, [_merged_pr(673, "Related to #671.")], now=NOW)
    assert mention.availability == Availability.AVAILABLE
    assert any("partly fixed" in c for c in mention.caveats)


def test_which_words_say_a_pr_fixes_an_issue() -> None:
    from git_into_gsoc.github.availability import says_it_fixes

    for text in (
        "Fixes #671",
        "fixes issue #671",
        "Closes acme/lib#671",
        "Resolved: #671",
        "Fix for #671's crash",
        "fixes https://github.com/acme/lib/issues/671",
    ):
        assert says_it_fixes(text, "acme/lib", 671), text
    for text in (
        "Related to #671",
        "Fixes #6710",
        "Fixes #12. Mentioned in #671",
        "See #671; this fixes the docs",
        "Fixes #671",
        "",
    ):
        number = 999 if text == "Fixes #671" else 671
        assert not says_it_fixes(text, "acme/lib", number), text


def test_a_real_issue_fixed_by_an_unlinked_merge_is_likely_taken() -> None:
    # Recorded from mofa's issue 671 (names replaced): "- Fixes issue #671" was merged
    # in March 2026, GitHub never closed the issue, and `recommend` offered it as free.
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "issue_fixed_by_unlinked_merge.json").read_text()
    )
    found = assess_issue(data["issue"], data["timeline"], now=NOW)
    assert found.availability == Availability.LIKELY_TAKEN
    assert "Merged PR #672 says it fixes this" in found.reason


def test_a_sibling_repos_bare_issue_number_is_its_own_issue() -> None:
    # A frontend pull request saying "Fixes #671" fixes the frontend's issue 671; it
    # must name "acme/lib#671" or link the issue to count for acme/lib.
    from git_into_gsoc.github.availability import says_it_fixes

    assert not says_it_fixes("Fixes #671", "acme/lib", 671, pr_repo="acme/frontend")
    assert says_it_fixes("Fixes acme/lib#671", "acme/lib", 671, pr_repo="acme/frontend")
    assert not says_it_fixes("Fixes other/lib#671", "acme/lib", 671, pr_repo="acme/lib")
    issue = _issue(number=671, html_url="https://github.com/acme/lib/issues/671")
    sibling = _merged_pr(90, "Fixes #671")
    sibling["source"]["issue"]["html_url"] = "https://github.com/acme/frontend/pull/90"
    sibling["source"]["issue"]["repository"] = {"full_name": "acme/frontend"}
    assert assess_issue(issue, [sibling], now=NOW).availability == Availability.AVAILABLE


def test_a_fix_merged_before_the_issue_was_opened_does_not_count() -> None:
    issue = _issue(
        number=671, created_at=_iso(10), html_url="https://github.com/acme/lib/issues/671"
    )
    old = _merged_pr(500, "Fixes #671", merged_days_ago=40)
    found = assess_issue(issue, [old], now=NOW)
    assert found.availability == Availability.AVAILABLE
    assert not any(p.fixes for p in found.linked_prs)
