"""`issues` searches the organizations that fit the person's interests, not just a language."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.models import IssueCandidate, OrgSummary
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.service import GSoCToolkit

ORGS = [
    OrgSummary(name="Apache", github_orgs=["apache"], match_reasons=["Uses c++"]),
    OrgSummary(name="ArduPilot", github_orgs=["ArduPilot"], match_reasons=["Topic: robotics"]),
    OrgSummary(name="Open Robotics", github_orgs=["osrf"], match_reasons=["Topic: robotics"]),
    OrgSummary(
        name="JdeRobot", github_orgs=["JdeRobot"], match_reasons=["Related topic: robotics"]
    ),
]


def _issue(repo: str, number: int) -> IssueCandidate:
    url = f"https://github.com/{repo}/issues/{number}"
    return IssueCandidate(repo=repo, number=number, title="x", url=url)


def _toolkit(monkeypatch: Any, found: list[list[IssueCandidate]]) -> tuple[GSoCToolkit, list[Any]]:
    toolkit = GSoCToolkit()
    searched: list[Any] = []
    monkeypatch.setattr(toolkit.gsoc, "search_organizations", lambda **k: (None, list(ORGS)))
    catalog = type("Catalog", (), {"year": 2026})()
    monkeypatch.setattr(toolkit.gsoc, "catalog", lambda year=None: (catalog, ORGS))

    def search(**kwargs: Any) -> list[IssueCandidate]:
        searched.append(kwargs["orgs"])
        return found.pop(0)

    monkeypatch.setattr(toolkit.github, "find_beginner_issues", search)
    return toolkit, searched


def test_profile_interests_pick_the_orgs_that_are_searched(monkeypatch: Any) -> None:
    # A simulated C++ + robotics beginner got only Apache and LLVM issues.
    ProgressStore().set_profile(technologies=["c++"], interests=["robotics"])
    hits = [_issue("ArduPilot/ardupilot", n) for n in (1, 2, 3)]
    toolkit, searched = _toolkit(monkeypatch, [hits])
    data = toolkit.find_issues(max_results=3)
    assert searched == [["ArduPilot", "osrf", "JdeRobot"]]
    assert "match your interests (robotics)" in data["note"]


def test_too_few_interest_matches_are_kept_first_and_filled_from_the_language(
    monkeypatch: Any,
) -> None:
    ProgressStore().set_profile(technologies=["c++"], interests=["robotics"])
    toolkit, searched = _toolkit(monkeypatch, [[_issue("osrf/rocker", 1)], [_issue("apache/x", 2)]])
    data = toolkit.find_issues(max_results=3)
    assert searched[1][0] == "apache"
    assert [i["repo"] for i in data["issues"]] == ["osrf/rocker", "apache/x"]  # interests first
    assert "Only 1 issue(s) came from those" in data["note"]
