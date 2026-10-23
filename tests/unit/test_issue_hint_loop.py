"""An empty `issues --repo` never sends the person in a loop back to the same repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from git_into_gsoc.errors import HttpError
from git_into_gsoc.models import OrgSummary
from git_into_gsoc.service import GSoCToolkit, _other_active_repos, _when_no_issues

RECENT = (datetime.now(UTC) - timedelta(days=10)).isoformat()
OLD = (datetime.now(UTC) - timedelta(days=500)).isoformat()


def _repo(name: str, pushed: str = RECENT, **extra: Any) -> dict[str, Any]:
    return {"name": name, "pushed_at": pushed, "fork": False, "archived": False, **extra}


# Shaped like ucsc-ospo on 2026-10-23: its website, a 2024 fork, and a repository quiet
# since June 2024. `repos ucsc-ospo` showed only the website, so "pick another of its
# repositories" led straight back to it (a launch audit).
OSPO = [
    _repo("ucsc-ospo.github.io"),
    _repo("symposium2024", fork=True),
    _repo("symposium2023", pushed=OLD),
]


def test_forks_archived_and_quiet_repositories_are_not_others() -> None:
    assert _other_active_repos(OSPO, "ucsc-ospo/ucsc-ospo.github.io") == 0
    assert _other_active_repos([*OSPO, _repo("tools")], "ucsc-ospo/ucsc-ospo.github.io") == 1
    assert _other_active_repos([_repo("lib", archived=True)], "acme/site") == 0


def _toolkit(monkeypatch: pytest.MonkeyPatch, repos: Any, owners: list[str]) -> GSoCToolkit:
    toolkit = GSoCToolkit()

    def listed(owner: str, **_: object) -> list[dict[str, Any]]:
        if isinstance(repos, Exception):
            raise repos
        return list(repos)

    org = OrgSummary(name="UC OSPO", slug="uc-ospo", github_orgs=owners)
    monkeypatch.setattr(toolkit.github, "list_owner_repos", listed)
    monkeypatch.setattr(toolkit.gsoc, "snapshot_organizations", lambda: [org])
    return toolkit


def test_the_only_active_repository_points_to_the_ideas_not_back_to_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _toolkit(monkeypatch, OSPO, ["uccross", "ucsc-ospo"])
    repo = "ucsc-ospo/ucsc-ospo.github.io"
    steps = toolkit._repo_alternatives(repo, _when_no_issues(None, org=None, repo=repo))
    assert not any("git-into-gsoc repos ucsc-ospo" in s for s in steps)
    assert any('git-into-gsoc ideas "UC OSPO"' in s for s in steps)
    assert steps[0].startswith("Read ucsc-ospo/ucsc-ospo.github.io's open issues yourself")


def test_an_owner_with_other_active_repositories_keeps_the_repos_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _toolkit(monkeypatch, [*OSPO, _repo("tools")], ["ucsc-ospo"])
    repo = "ucsc-ospo/ucsc-ospo.github.io"
    steps = toolkit._repo_alternatives(repo, _when_no_issues(None, org=None, repo=repo))
    assert any("git-into-gsoc repos ucsc-ospo" in s for s in steps)
    assert any('git-into-gsoc ideas "UC OSPO"' in s for s in steps)


def test_an_unread_listing_keeps_the_usual_steps_and_a_non_gsoc_owner_gets_no_ideas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _toolkit(monkeypatch, HttpError("rate limit"), ["someone-else"])
    repo = "acme/site"
    usual = _when_no_issues(None, org=None, repo=repo)
    assert toolkit._repo_alternatives(repo, usual) == usual
