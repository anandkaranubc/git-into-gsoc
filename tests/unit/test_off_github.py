"""Organizations whose code lives outside GitHub, and GitHub mirrors of such code.

30 of the 183 GSoC 2026 organizations list no GitHub owner (GNOME, KDE, Debian,
QEMU, ...). A simulated run on 2026-10-21 found GNOME/gitg's GitHub mirror graded F,
its GitLab issue reported as a misspelled name, and `issues --org "GNOME Foundation"`
rejected as an invalid GitHub login.
"""

from __future__ import annotations

from typing import Any

import pytest

from git_into_gsoc.errors import NotFoundError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.repos import mirror_source
from git_into_gsoc.models import OrgSummary, RepoLead
from git_into_gsoc.service import GSoCToolkit

GITG = {
    "full_name": "GNOME/gitg",
    "description": "Read-only mirror of https://gitlab.gnome.org/GNOME/gitg",
    "has_issues": False,
    "homepage": "https://gitlab.gnome.org/GNOME/gitg",
    "owner": {"type": "Organization"},
}


def test_mirrors_are_recognised_without_false_alarms() -> None:
    assert mirror_source(GITG) == "https://gitlab.gnome.org/GNOME/gitg"
    no_url = {"description": "Mirror of the official repository", "homepage": "https://x.org"}
    assert mirror_source(no_url) == "https://x.org"
    assert mirror_source({"description": "A tool to create a mirror of a website"}) is None
    assert mirror_source({"description": "PyPI mirror client", "has_issues": True}) is None
    assert mirror_source({"description": "", "has_issues": False}) is None


def test_a_mirror_is_not_graded(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: GITG)

    def never(*a: Any, **k: Any) -> None:
        raise AssertionError("a mirror's health must not be computed")

    monkeypatch.setattr(toolkit.github, "repo_health", never)
    data = toolkit.evaluate_repo("GNOME/gitg")
    assert data["health"] is None and data["mirror_of"] == "https://gitlab.gnome.org/GNOME/gitg"
    assert data["recommendation"].startswith("Not graded")


def test_an_issue_on_a_mirror_points_to_the_real_project(monkeypatch: Any) -> None:
    client = GitHubClient()

    def missing(*a: Any, **k: Any) -> dict[str, Any]:
        raise NotFoundError("GNOME/gitg has no issue or pull request #494", status_code=404)

    monkeypatch.setattr(client, "get_issue", missing)
    monkeypatch.setattr(client, "get_repo", lambda o, r: GITG)
    with pytest.raises(NotFoundError) as found:
        client.assess("GNOME/gitg", 494)
    assert "read-only mirror" in str(found.value)
    assert found.value.hint and "https://gitlab.gnome.org/GNOME/gitg" in found.value.hint


def test_an_org_off_github_gets_a_clear_answer(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    gnome = OrgSummary(
        name="GNOME Foundation",
        source_code="https://gitlab.gnome.org/",
        ideas_url="https://gsoc.gnome.org/2026/",
    )
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: gnome)
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ({}, [], ""))
    monkeypatch.setattr("git_into_gsoc.service.fetch_ideas_text", lambda *a: "ideas")
    monkeypatch.setattr(toolkit, "_repos_named_on_page", lambda *a, **k: [])
    with pytest.raises(NotFoundError) as found:
        toolkit.find_issues(org="GNOME Foundation")
    assert "outside GitHub (https://gitlab.gnome.org/)" in str(found.value)
    assert "Invalid organization" not in str(found.value)


def test_an_umbrella_without_a_github_owner_searches_its_linked_projects(
    monkeypatch: Any,
) -> None:
    toolkit = GSoCToolkit()
    psf = OrgSummary(name="Python Software Foundation", ideas_url="https://python-gsoc.org")
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: psf)
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ({}, [], ""))
    monkeypatch.setattr("git_into_gsoc.service.fetch_ideas_text", lambda *a: "ideas")
    leads = [RepoLead(full_name="vacanza/holidays", url="https://github.com/vacanza/holidays")]
    monkeypatch.setattr(toolkit, "_repos_named_on_page", lambda *a, **k: leads)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **k: seen.update(k) or [])
    data = toolkit.find_issues(org="Python Software Foundation")
    assert seen["orgs"] == ["vacanza"]
    assert seen["org_names"]["vacanza"] == "named on the Python Software Foundation ideas page"
    assert "lists no GitHub organization" in data["note"]


def test_ideas_page_links_to_mirrors_are_skipped(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: GITG)
    page = "See https://github.com/GNOME/gitg for the code."
    assert toolkit._repos_named_on_page(page, [], language=None) == []


def test_progress_keeps_links_on_other_code_hosts() -> None:
    from git_into_gsoc.progress.store import ProgressStore, other_host_link

    store = ProgressStore()
    store.track_repo("https://gitlab.gnome.org/GNOME/gitg.git/")
    store.track_issue("https://gitlab.gnome.org/GNOME/gitg/-/issues/494")
    state = store.load()
    assert state.tracked_repos == ["https://gitlab.gnome.org/GNOME/gitg"]
    assert state.tracked_issues == ["https://gitlab.gnome.org/GNOME/gitg/-/issues/494"]
    assert other_host_link("https://github.com/sympy/sympy") is None
    assert other_host_link("https://gitlab.gnome.org/") is None  # a host, not a project
    from git_into_gsoc.errors import InputError

    with pytest.raises(InputError) as refused:
        store.track_issue("https://gitlab.gnome.org/GNOME/gitg")  # a project, not an issue
    assert refused.value.hint and "another code host" in refused.value.hint


def test_next_moves_on_for_an_org_whose_code_is_elsewhere() -> None:
    from git_into_gsoc.coach import plan_actions
    from git_into_gsoc.models import ProgressState

    program = {"phase": {"id": "org_exploration"}, "timeline": []}
    state = ProgressState(shortlisted_orgs=["GNOME Foundation"], profile={"technologies": ["c"]})
    first = plan_actions(
        state,
        program,
        tracked_issues=[],
        new_issues=[],
        code_elsewhere={"GNOME Foundation": "https://gitlab.gnome.org/"},
    )[0]
    assert "progress track_repo --value LINK" in first["why"]
    state = state.model_copy(
        update={
            "tracked_repos": ["https://gitlab.gnome.org/GNOME/gitg"],
            "phases": {"community": True},
        }
    )
    second = plan_actions(state, program, tracked_issues=[], new_issues=[])[0]
    assert second["title"] == "Find a newcomer issue in https://gitlab.gnome.org/GNOME/gitg"
    assert "issues --repo" not in second["command"]
    link = "https://gitlab.gnome.org/GNOME/gitg/-/issues/494"
    tracked = [{"ref": link, "url": link, "availability": "unknown", "off_github": True}]
    third = plan_actions(state, program, tracked_issues=tracked, new_issues=[])[0]
    assert third["command"] == link and "cannot check it" in third["why"]


def test_a_language_search_names_the_organizations_it_could_not_search(monkeypatch: Any) -> None:
    # `issues --language c` skipped GNOME, FFmpeg, and VideoLAN without a word.
    toolkit = GSoCToolkit()
    ranked = [
        OrgSummary(name="Apache", github_orgs=["apache"]),
        OrgSummary(name="GNOME Foundation", source_code="https://gitlab.gnome.org/"),
        OrgSummary(name="FFmpeg"),
    ]
    monkeypatch.setattr(toolkit.gsoc, "search_organizations", lambda **k: (None, ranked))
    note = toolkit._skipped_off_github("c", year=None)
    assert "outside GitHub: GNOME Foundation, FFmpeg." in note
    assert "Apache" not in note


def test_a_named_organization_does_not_list_other_organizations_off_github(
    monkeypatch: Any,
) -> None:
    # `issues --org CERN-HSF --language python` said "Not searched, because their code is
    # outside GitHub: Python Software Foundation, The ns-3 Network Simulator Project,
    # SageMath" (a launch audit, 0.23.0): organizations nobody asked about.
    toolkit = GSoCToolkit()
    cern = OrgSummary(name="CERN-HSF", github_orgs=["HSF"])
    monkeypatch.setattr(
        toolkit.gsoc, "get_organization", lambda name, **k: cern if "cern" in name.lower() else None
    )
    monkeypatch.setattr(toolkit.github, "search_issues", lambda *a, **k: [])
    monkeypatch.setattr(
        toolkit,
        "gsoc_github_orgs",
        lambda **k: ({"psf": "PSF"}, ["psf"], "Searching GitHub orgs of GSoC organizations."),
    )
    monkeypatch.setattr(toolkit, "_skipped_off_github", lambda language, year=None: " OFF-GITHUB")
    named = toolkit.find_issues(org="CERN-HSF", language="python")
    assert "OFF-GITHUB" not in named["note"]
    # Without an organization, the note still names the ones it could not search.
    assert "OFF-GITHUB" in toolkit.find_issues(language="python")["note"]
