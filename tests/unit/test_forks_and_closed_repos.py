"""Forks, and repositories that take no pull requests or keep no issues on GitHub.

A live check of 0.24.0 on 2026-10-22 graded a SymPy contributor's own fork "F, Poor
fit, choose a healthier repository" without naming sympy/sympy, graded a person's
old fork of psf/requests F for "nothing pushed for 936 days", and graded
torvalds/linux, which has pull requests turned off. `issues --repo` on the fork
said "read its open issues yourself" while the fork has issues off.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.github.repos import fork_parent, is_personal
from git_into_gsoc.models import ContributionGuide, RepoHealth
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()

# Shaped like GET /repos for a contributor's fork, with a made-up account.
PERSONAL_FORK: dict[str, Any] = {
    "full_name": "example-contributor/sympy",
    "fork": True,
    "has_issues": False,
    "has_pull_requests": True,
    "owner": {"login": "example-contributor", "type": "User"},
    "parent": {"full_name": "sympy/sympy"},
    "source": {"full_name": "sympy/sympy"},
}
# Organizations do work in forks; this one is made up.
ORG_FORK: dict[str, Any] = {
    **PERSONAL_FORK,
    "full_name": "example-org/editor",
    "owner": {"login": "example-org", "type": "Organization"},
    "parent": {"full_name": "upstream-dev/editor"},
    "source": {"full_name": "upstream-dev/editor"},
}
NO_PULL_REQUESTS: dict[str, Any] = {
    "full_name": "example-kernel/kernel",
    "fork": False,
    "has_issues": False,
    "has_pull_requests": False,
    "owner": {"login": "example-kernel", "type": "User"},
}


def _never(*a: Any, **k: Any) -> None:
    raise AssertionError("an ungraded repository's health must not be computed")


def test_fork_parent_and_owner_kind() -> None:
    assert fork_parent(PERSONAL_FORK) == "sympy/sympy"
    assert fork_parent({**PERSONAL_FORK, "parent": None}) == "sympy/sympy"
    assert fork_parent({"fork": True}) is None  # a list endpoint has no parent
    assert fork_parent({"fork": False, "parent": {"full_name": "a/b"}}) is None
    assert is_personal(PERSONAL_FORK) and not is_personal(ORG_FORK)


def test_a_persons_fork_is_not_graded_and_names_the_project(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: PERSONAL_FORK)
    monkeypatch.setattr(toolkit.github, "repo_health", _never)
    data = toolkit.evaluate_repo("example-contributor/sympy")
    assert data["health"] is None and data["fork_of"] == "sympy/sympy"
    assert data["recommendation"].startswith("Not graded")
    assert "Pull requests for the project go to sympy/sympy" in data["recommendation"]
    assert data["next_step"] == "git-into-gsoc repo sympy/sympy"


def test_a_repository_without_pull_requests_is_not_graded(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: NO_PULL_REQUESTS)
    monkeypatch.setattr(toolkit.github, "repo_health", _never)
    data = toolkit.evaluate_repo("example-kernel/kernel")
    assert data["health"] is None and data["pull_requests_off"] is True
    assert "pull requests turned off" in data["recommendation"]
    # A server that does not report the setting (an older GitHub Enterprise) is graded.
    unknown = {k: v for k, v in NO_PULL_REQUESTS.items() if k != "has_pull_requests"}
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: unknown)
    health = RepoHealth(full_name="example-kernel/kernel", url="https://github.com/x")
    monkeypatch.setattr(toolkit.github, "repo_health", lambda name: health)
    monkeypatch.setattr(
        toolkit.github, "contribution_guide", lambda name: ContributionGuide(repo=name)
    )
    assert toolkit.evaluate_repo("example-kernel/kernel")["health"] is not None


def test_an_organizations_fork_is_graded_and_names_the_original(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: ORG_FORK)
    health = RepoHealth(full_name="example-org/editor", url="https://github.com/x", grade="B")
    monkeypatch.setattr(toolkit.github, "repo_health", lambda name: health)
    monkeypatch.setattr(
        toolkit.github, "contribution_guide", lambda name: ContributionGuide(repo=name)
    )
    data = toolkit.evaluate_repo("example-org/editor")
    assert data["health"]["grade"] == "B" and data["fork_of"] == "upstream-dev/editor"
    assert data["recommendation"].startswith("This is example-org's fork of upstream-dev/editor")
    assert data["recommendation"].endswith("check that maintainers reply.")


def test_repo_command_explains_a_fork_and_tracks_the_project(monkeypatch: Any) -> None:
    from git_into_gsoc import cli
    from git_into_gsoc.progress.store import ProgressStore

    class Fake:
        progress = ProgressStore()

        def evaluate_repo(self, name: str) -> dict[str, Any]:
            toolkit = GSoCToolkit()
            monkeypatch.setattr(toolkit.github, "get_repo", lambda o, r: PERSONAL_FORK)
            return toolkit.evaluate_repo(name)

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["repo", "example-contributor/sympy", "--track"])
    assert result.exit_code == 0, result.output
    assert "a fork" in result.output and "Repo health" not in result.output
    assert "Saved sympy/sympy to your progress" in result.output
    assert "Next: git-into-gsoc repo sympy/sympy" in result.output
    assert Fake.progress.load().tracked_repos == ["sympy/sympy"]


def _no_issues_found(repo: str, raw: dict[str, Any]) -> list[str]:
    owner, name = repo.split("/")
    respx.get(url__startswith="https://summerofcode.withgoogle.com/").mock(
        return_value=httpx.Response(503)
    )
    respx.get(url__startswith="https://api.gsocorganizations.dev/").mock(
        return_value=httpx.Response(503)
    )
    respx.get(f"https://api.github.com/repos/{owner}/{name}/labels").mock(
        return_value=httpx.Response(200, json=[{"name": "good first issue"}])
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get(f"https://api.github.com/repos/{owner}/{name}").mock(
        return_value=httpx.Response(200, json=raw)
    )
    # The owner has another active repository, so "pick another" stays a fair step.
    recent = datetime.now(UTC).isoformat()
    other = {"name": "other", "pushed_at": recent, "fork": False, "archived": False}
    respx.get(f"https://api.github.com/orgs/{owner}/repos").mock(
        return_value=httpx.Response(200, json=[other])
    )
    data = GSoCToolkit().find_issues(repo=repo, max_results=3)
    assert data["count"] == 0
    steps: list[str] = data["next_steps"]
    return steps


@respx.mock
def test_no_issues_on_a_fork_points_to_the_projects_issues() -> None:
    steps = _no_issues_found("example-contributor/sympy", PERSONAL_FORK)
    assert steps == [
        "example-contributor/sympy is a fork, a copy of sympy/sympy; the project's issues "
        "are there: git-into-gsoc issues --repo sympy/sympy"
    ]


@respx.mock
def test_no_issues_where_issues_are_off_says_so() -> None:
    steps = _no_issues_found("example-kernel/kernel", NO_PULL_REQUESTS)
    assert steps[0].startswith("example-kernel/kernel has issues turned off on GitHub")
    assert not any("open issues yourself" in step for step in steps)


@respx.mock
def test_no_issues_in_an_ordinary_repository_keeps_the_usual_steps() -> None:
    raw = {"full_name": "acme/lib", "fork": False, "has_issues": True}
    steps = _no_issues_found("acme/lib", raw)
    assert steps[0].startswith("Read acme/lib's open issues yourself")
