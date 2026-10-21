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


def test_a_repository_search_says_what_it_leaves_out(monkeypatch: Any) -> None:
    # A simulated run saw `repo` count 38 beginner issues and `issues --repo` show 2.
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ({}, [], ""))
    monkeypatch.setattr(toolkit.github, "list_labels", lambda o, r: [])
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **k: [])
    data = toolkit.find_issues(repo="ArduPilot/ardupilot", max_results=3)
    assert "Left out: issues with an assignee or a linked pull request" in data["note"]


def test_org_accepts_a_gsoc_name_and_its_ideas_page_projects(monkeypatch: Any) -> None:
    # A simulated robotics beginner: Open Robotics lists only openrobotics and osrf as
    # GitHub owners, so ros2 and open-rmf work named on its ideas page was never searched.
    from git_into_gsoc.models import RepoLead

    toolkit = GSoCToolkit()
    robotics = OrgSummary(
        name="Open Robotics",
        github_orgs=["openrobotics", "osrf"],
        ideas_url="https://github.com/osrf/osrf_wiki/wiki/GSoC-2026",
    )
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: robotics)
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ({}, [], ""))
    monkeypatch.setattr("git_into_gsoc.service.fetch_ideas_text", lambda *a: "ideas")
    leads = [
        RepoLead(full_name=f, url=f"https://github.com/{f}", score=1.0)
        for f in ("ros2/rclcpp", "open-rmf/crossflow", "ros2/rclpy")
    ]
    monkeypatch.setattr(toolkit, "_repos_named_on_page", lambda *a, **k: leads)
    seen: dict[str, Any] = {}

    def search(**kwargs: Any) -> list[IssueCandidate]:
        seen.update(kwargs)
        return []

    monkeypatch.setattr(toolkit.github, "find_beginner_issues", search)
    data = toolkit.find_issues(org="Open Robotics", max_results=5)
    assert seen["org"] is None
    assert seen["orgs"] == ["openrobotics", "osrf", "ros2", "open-rmf"]
    assert "Open Robotics" in data["note"] and "ros2" in data["note"]
    assert seen["org_names"]["ros2"] == "Open Robotics"


def test_org_still_takes_a_plain_github_login(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: None)
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ({}, [], ""))
    seen: dict[str, Any] = {}
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **k: seen.update(k) or [])
    toolkit.find_issues(org="ros2", max_results=5)
    assert seen["org"] == "ros2" and seen["orgs"] is None
