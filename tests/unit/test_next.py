"""The `next` command: tracked issues, deadlines, pull requests, merges, and the actions it
suggests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from conftest import load_fixture
from git_into_gsoc.models import JourneyPhase
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.service import GSoCToolkit

OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
GH = "https://api.github.com"
NOW = datetime(2026, 10, 20, tzinfo=UTC)


def _iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


def _search_item(number: int, repo: str, days_ago: int = 2) -> dict[str, Any]:
    return {
        "id": number,
        "number": number,
        "title": f"New issue {number}",
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"{GH}/repos/{repo}",
        "labels": [{"name": "good first issue"}],
        "state": "open",
        "assignees": [],
        "comments": 0,
        "created_at": _iso(days_ago),
        "updated_at": _iso(days_ago),
        "body": "Steps to reproduce: run it.",
    }


@pytest.fixture
def api() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=_archive_year(2026))
        )
        # Shortlisted orgs' repositories, read for a wiki statement about GSoC.
        router.get(url__regex=r"https://api\.github\.com/orgs/[^/]+/repos").mock(
            return_value=httpx.Response(200, json=[])
        )
        yield router


def test_next_on_a_fresh_install_points_to_start_and_orgs(api: respx.MockRouter) -> None:
    data = GSoCToolkit().next_steps(now=NOW)
    assert data["program"]["phase"]["id"]
    assert data["program"]["dates_are_official"] is False
    commands = " ".join(a["command"] for a in data["actions"])
    assert "start" in commands
    assert "orgs" in commands or "recommend" in commands
    assert data["changes"] == []
    assert data["tracked_issues"] == []
    assert data["new_issues"] == []


def test_next_rechecks_tracked_issues_and_reports_changes(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.set_profile(technologies=["python"], github="alice")
    store.shortlist_org("SymPy")
    store.track_repo("sympy/sympy")
    store.track_issue("https://github.com/sympy/sympy/issues/5")
    store.set_issue_status("sympy/sympy#5", "available")
    store.complete_phase(JourneyPhase.LEARN)

    api.get(f"{GH}/repos/sympy/sympy/issues/5").mock(
        return_value=httpx.Response(
            200,
            json={
                "number": 5,
                "title": "Fix docs",
                "state": "open",
                "html_url": "https://github.com/sympy/sympy/issues/5",
                "assignees": [{"login": "bob"}],
                "updated_at": _iso(1),
            },
        )
    )
    api.get(url__regex=rf"{GH}/repos/sympy/sympy/issues/5/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )

    def search_response(request: httpx.Request) -> httpx.Response:
        if "is:pr" in request.url.params["q"]:
            pr_item = {
                **_search_item(9, "sympy/sympy"),
                "pull_request": {"url": f"{GH}/repos/sympy/sympy/pulls/9"},
            }
            return httpx.Response(200, json={"items": [pr_item]})
        return httpx.Response(
            200, json={"items": [_search_item(7, "sympy/sympy"), _search_item(8, "sympy/live")]}
        )

    search = api.get(f"{GH}/search/issues").mock(side_effect=search_response)
    api.get(f"{GH}/repos/sympy/sympy/pulls/9").mock(
        return_value=httpx.Response(
            200,
            json={
                "number": 9,
                "title": "Fix docs typo",
                "html_url": "https://github.com/sympy/sympy/pull/9",
                "user": {"login": "alice", "type": "User"},
                "draft": False,
                "mergeable_state": "clean",
                "created_at": _iso(10),
                "base": {"ref": "master", "repo": {"full_name": "sympy/sympy"}},
                "head": {"sha": "abc123"},
            },
        )
    )
    api.get(url__regex=rf"{GH}/repos/sympy/sympy/issues/9/timeline.*").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"event": "committed", "author": {"date": _iso(10)}},
                {
                    "event": "commented",
                    "user": {"login": "bob", "type": "User"},
                    "created_at": _iso(3),
                    "body": "Could you add a test?",
                },
            ],
        )
    )
    api.get(url__regex=rf"{GH}/repos/sympy/sympy/commits/abc123/check-runs.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"}]
            },
        )
    )

    data = GSoCToolkit().next_steps(now=NOW)
    prs = data["open_pull_requests"]
    assert [p["ref"] for p in prs] == ["sympy/sympy#9"]
    assert prs[0]["status"] == "needs_you"
    assert prs[0]["summary"].startswith("@bob commented 3 days ago with no reply from you")
    assert data["actions"][0]["title"].startswith("Your pull request sympy/sympy#9 needs you")
    assert "draft review-reply --repo sympy/sympy" in data["actions"][0]["command"]
    tracked = data["tracked_issues"][0]
    assert tracked["ref"] == "sympy/sympy#5"
    assert tracked["availability"] == "assigned"
    assert tracked["previous"] == "available"
    assert any("sympy/sympy#5" in c and "assigned" in c for c in data["changes"])
    assert {i["repo"] for i in data["new_issues"]} == {"sympy/sympy", "sympy/live"}
    queries = [c.request.url.params["q"] for c in search.calls]
    assert any("repo:sympy/sympy" in q and "created:>" in q for q in queries)
    assert any(q.startswith("is:pr is:open author:alice -user:alice") for q in queries)
    assert ProgressStore().load().issue_status["sympy/sympy#5"] == "assigned"
    assert ProgressStore().load().last_checked_at is not None
    commands = " ".join(a["command"] for a in data["actions"])
    assert "issues" in commands


def test_next_suggests_contribution_check_when_proposals_near(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.set_profile(technologies=["python"], github="alice")
    store.shortlist_org("SymPy")
    api.get(f"{GH}/search/issues").mock(return_value=httpx.Response(200, json={"items": []}))
    # Estimated 2027 proposals open mid-March; ten days before, the window is "soon".
    march = datetime(2027, 3, 5, tzinfo=UTC)
    data = GSoCToolkit().next_steps(now=march)
    commands = " ".join(a["command"] for a in data["actions"])
    assert "contributions --github alice" in commands
    assert any(m["days_until"] <= 14 for m in data["deadlines"])


def test_next_survives_a_tracked_pull_request_link(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.track_issue("https://github.com/sympy/sympy/pull/1")
    api.get(f"{GH}/repos/sympy/sympy/issues/1").mock(
        return_value=httpx.Response(
            200, json={"number": 1, "state": "open", "pull_request": {}, "updated_at": _iso(1)}
        )
    )
    api.get(f"{GH}/search/issues").mock(return_value=httpx.Response(200, json={"items": []}))
    data = GSoCToolkit().next_steps(now=NOW)
    tracked = data["tracked_issues"][0]
    assert tracked["availability"] == "unknown"
    assert "pull request" in tracked["reason"]


def test_next_asks_for_public_intro_before_issues(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.set_profile(technologies=["python"])
    store.shortlist_org("SymPy")
    store.track_repo("sympy/sympy")
    api.get(f"{GH}/search/issues").mock(return_value=httpx.Response(200, json={"items": []}))
    data = GSoCToolkit().next_steps(now=NOW)
    titles = [a["title"] for a in data["actions"]]
    assert any("Introduce yourself" in t for t in titles)
    assert not any("Find a beginner issue" in t for t in titles)
    store.complete_phase(JourneyPhase.COMMUNITY)
    data = GSoCToolkit().next_steps(now=NOW)
    assert any("Find a beginner issue" in a["title"] for a in data["actions"])


def test_shortlist_step_uses_the_org_command() -> None:
    from git_into_gsoc.coach import plan_actions
    from git_into_gsoc.models import ProgressState

    state = ProgressState(profile={"technologies": ["python"]})
    actions = plan_actions(state, {"timeline": []}, tracked_issues=[], new_issues=[])
    shortlist = next(a for a in actions if a["title"].startswith("Shortlist"))
    assert "--shortlist" in shortlist["command"]
    assert "shortlist_org" not in shortlist["command"]


def test_a_tracked_issue_counts_as_a_chosen_repository() -> None:
    from git_into_gsoc.coach import plan_actions
    from git_into_gsoc.models import ProgressState

    # A simulated beginner tracked ArduPilot/ardupilot#9828 and `next` still said
    # "Pick the repository to start in at ArduPilot".
    state = ProgressState(
        profile={"technologies": ["c++"]},
        shortlisted_orgs=["ArduPilot"],
        tracked_issues=["https://github.com/ArduPilot/ardupilot/issues/9828"],
    )
    actions = plan_actions(state, {"timeline": []}, tracked_issues=[], new_issues=[])
    assert not any(a["title"].startswith("Pick the repository") for a in actions)


def test_every_hint_in_next_is_a_command_you_can_paste() -> None:
    from git_into_gsoc.coach import plan_actions
    from git_into_gsoc.models import ProgressState

    # A blind beginner run (2026-10-22) pasted "progress complete_phase --phase
    # community" and got a shell error, and ran `repo` without --track, so `next`
    # kept asking it to pick a repository.
    shortlisted = ProgressState(
        profile={"technologies": ["javascript"]}, shortlisted_orgs=["omegaUp"]
    )
    actions = plan_actions(shortlisted, {"timeline": []}, tracked_issues=[], new_issues=[])
    pick = next(a for a in actions if a["title"].startswith("Pick the repository"))
    assert "git-into-gsoc repo owner/name --track" in pick["command"]
    chosen = ProgressState(
        profile={"technologies": ["javascript"]},
        shortlisted_orgs=["omegaUp"],
        tracked_repos=["omegaup/omegaup"],
    )
    actions = plan_actions(chosen, {"timeline": []}, tracked_issues=[], new_issues=[])
    intro = next(a for a in actions if a["title"].startswith("Introduce yourself"))
    assert "git-into-gsoc progress complete_phase --phase community" in intro["why"]


def test_a_tracked_issue_keeps_its_caution(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # `issue` warned about an old claim on ArduPilot/ardupilot#9828; `next` only said
    # "no open PR or recent claim ... It is still free".
    from git_into_gsoc.models import Availability, IssueAssessment
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    assessment = IssueAssessment(
        availability=Availability.AVAILABLE,
        reason="Open, unassigned, no open PR or recent claim",
        caveats=["@someone asked 138d ago with no PR; ask politely in the thread first"],
    )
    monkeypatch.setattr(toolkit.github, "assess", lambda full, n: ({}, assessment))
    status, reason = toolkit._availability_of("ArduPilot/ardupilot", 9828)
    assert status == "available"
    assert "asked 138d ago" in reason


def _merged_item(number: int, repo: str, days_ago: int) -> dict[str, Any]:
    return {
        **_search_item(number, repo, days_ago),
        "title": f"Fix bug {number}",
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "pull_request": {"merged_at": _iso(days_ago)},
    }


def _search_with_merged(items: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    def respond(request: httpx.Request) -> httpx.Response:
        if "is:merged" in request.url.params["q"]:
            return httpx.Response(200, json={"items": items})
        return httpx.Response(200, json={"items": []})

    return respond


def test_next_celebrates_a_first_merged_pull_request_once(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.set_profile(technologies=["python"], github="alice")
    api.get(f"{GH}/search/issues").mock(
        side_effect=_search_with_merged([_merged_item(42, "sympy/sympy", 1)])
    )
    data = GSoCToolkit().next_steps(now=NOW)
    assert [m["ref"] for m in data["merged_pull_requests"]] == ["sympy/sympy#42"]
    assert data["first_merge"] is True
    assert data["actions"][0]["command"].startswith(
        'git-into-gsoc log --done "Merged sympy/sympy#42"'
    )
    assert store.summary()["contributions"] == 1
    # Recorded: the next check does not announce it again.
    again = GSoCToolkit().next_steps(now=NOW + timedelta(hours=1))
    assert again["merged_pull_requests"] == []
    assert again["first_merge"] is False
    assert store.summary()["contributions"] == 1


def test_next_records_old_merges_quietly(api: respx.MockRouter) -> None:
    store = ProgressStore()
    store.set_profile(technologies=["python"], github="alice")
    old = [_merged_item(n, "numpy/numpy", 200 + n) for n in (1, 2, 3)]
    api.get(f"{GH}/search/issues").mock(side_effect=_search_with_merged(old))
    data = GSoCToolkit().next_steps(now=NOW)
    assert data["merged_pull_requests"] == []
    assert data["first_merge"] is False
    assert store.summary()["contributions"] == 3


def test_next_shows_merged_pull_requests_in_the_terminal(api: respx.MockRouter) -> None:
    from typer.testing import CliRunner

    from git_into_gsoc.cli import app

    ProgressStore().set_profile(technologies=["python"], github="alice")
    # The command uses the real clock, so the merge is dated from now.
    item = _merged_item(42, "sympy/sympy", 1)
    item["pull_request"]["merged_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    api.get(f"{GH}/search/issues").mock(side_effect=_search_with_merged([item]))
    result = CliRunner().invoke(app, ["next"])
    assert result.exit_code == 0, result.output
    assert "Merged since your last check" in result.stdout
    assert "sympy/sympy#42" in result.stdout
    words = " ".join(result.stdout.split())
    assert "first merged pull request" in words
    # The one moment worth asking: point to feedback and a friend, once.
    assert "tell a friend" in words
    assert "git-into-gsoc feedback" in words
