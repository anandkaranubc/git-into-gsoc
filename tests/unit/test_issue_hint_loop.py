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


def test_the_advice_links_the_issues_and_the_organizations_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A launch audit (2026-10-23) was told to read ML4SCI/DeepLense's issues and to ask
    # in the project's channel, with neither link, though ML4SCI lists its Gitter room.
    from git_into_gsoc.models import ContactChannel

    chat = "https://app.gitter.im/#/room/#ML4SCI_general:gitter.im"
    org = OrgSummary(
        name="Machine Learning for Science (ML4SCI)",
        slug="ml4sci",
        github_orgs=["ML4SCI"],
        channels=[
            ContactChannel(kind="mailingList", value="ml4-sci@cern.ch"),
            ContactChannel(kind="chat", value=chat),
        ],
    )
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "snapshot_organizations", lambda: [org])
    found = toolkit._public_channel(["ml4sci"])
    assert found is not None and found.value == chat  # its chat before its mailing list
    assert toolkit._public_channel(["someone-else"]) is None
    assert toolkit._public_channel([]) is None

    steps = _when_no_issues(None, org=None, repo="ML4SCI/DeepLense", chat=found)
    assert "(https://github.com/ML4SCI/DeepLense/issues)" in steps[0]
    assert (
        steps[1] == f"Ask in the project's public channel which small task would help most: {chat}"
    )
    assert _when_no_issues(None, org=None, repo="acme/lib")[1].endswith("would help most.")
    org_steps = _when_no_issues(None, org="ML4SCI", repo=None, gsoc_org=True, chat=found)
    assert any(
        step.endswith(f"ask the mentors in its chat how to start: {chat}") for step in org_steps
    )


def test_a_mailing_list_is_not_called_a_chat_and_a_pasted_link_is_a_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A post-merge audit (2026-10-23): a mailing list was offered as "ask the mentors in
    # its chat", and a pasted repository link reached the advice as is.
    from git_into_gsoc.models import ContactChannel

    mail = ContactChannel(kind="mailingList", value="dev@lists.example.org")
    steps = _when_no_issues(None, org="Example", repo=None, gsoc_org=True, chat=mail)
    assert any("ask the mentors on its mailing list how to start" in s for s in steps)
    assert not any("in its chat" in s for s in steps)

    toolkit = _toolkit(monkeypatch, [_repo("r"), _repo("tools")], ["o"])
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **_: ({}, [], ""))
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **_: [])
    monkeypatch.setattr(toolkit.github, "list_labels", lambda *_: [])
    monkeypatch.setattr(toolkit.github, "get_repo", lambda *_: {"has_issues": True})
    data = toolkit.find_issues(repo="https://github.com/o/r")
    text = " ".join(data["next_steps"])
    assert "(https://github.com/o/r/issues)" in text
    assert "git-into-gsoc repos o" in text and "https:" not in text.replace(
        "https://github.com/o/r/issues", ""
    )
