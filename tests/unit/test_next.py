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
        yield router


def test_next_on_a_fresh_install_points_to_profile_and_orgs(api: respx.MockRouter) -> None:
    data = GSoCToolkit().next_steps(now=NOW)
    assert data["program"]["phase"]["id"]
    assert data["program"]["dates_are_official"] is False
    commands = " ".join(a["command"] for a in data["actions"])
    assert "profile" in commands
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
    search = api.get(f"{GH}/search/issues").mock(
        return_value=httpx.Response(
            200, json={"items": [_search_item(7, "sympy/sympy"), _search_item(8, "sympy/live")]}
        )
    )

    data = GSoCToolkit().next_steps(now=NOW)
    tracked = data["tracked_issues"][0]
    assert tracked["ref"] == "sympy/sympy#5"
    assert tracked["availability"] == "assigned"
    assert tracked["previous"] == "available"
    assert any("sympy/sympy#5" in c and "assigned" in c for c in data["changes"])
    assert {i["repo"] for i in data["new_issues"]} == {"sympy/sympy", "sympy/live"}
    query = search.calls[0].request.url.params["q"]
    assert "repo:sympy/sympy" in query and "created:>" in query
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
