"""`issues --org` reaches organizations whose code is on a GitLab host."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.errors import NotFoundError
from git_into_gsoc.models import Availability, ContactChannel, IssueCandidate, OrgSummary
from git_into_gsoc.service import GSoCToolkit

GROUP = "https://gitlab.gnome.org/api/v4/groups/GNOME/issues"
GITG = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg/issues/494"


def _toolkit(monkeypatch: pytest.MonkeyPatch, source_code: str) -> GSoCToolkit:
    toolkit = GSoCToolkit()
    org = OrgSummary(
        name="GNOME Foundation",
        github_orgs=[],
        source_code=source_code,
        channels=[ContactChannel(kind="chat", value="https://matrix.to/#/#newcomers:gnome.org")],
    )
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: org)
    # The GitHub side of the search is not under test; it would read the official list.
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **kwargs: ({}, [], ""))
    return toolkit


def _listing(label: str, web_url: str) -> Any:
    """A GitLab issues page with one issue, returned only for `label`."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("labels") != label:
            return httpx.Response(200, json=[])
        updated = (datetime.now(UTC) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "iid": int(web_url.rsplit("/", 1)[1]),
                    "title": "Change the application ID suffix",
                    "description": "The suffix should follow the new naming.",
                    "state": "opened",
                    "assignees": [],
                    "author": {"username": "maintainer"},
                    "labels": [label],
                    "user_notes_count": 0,
                    "created_at": updated,
                    "updated_at": updated,
                    "web_url": web_url,
                }
            ],
        )

    return respond


_by_label = _listing("4. Newcomers", "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")


def test_an_organization_on_gitlab_is_searched_there(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = _toolkit(monkeypatch, "https://gitlab.gnome.org/")
    with respx.mock(assert_all_called=False) as api:
        api.get(url__regex=rf"{GROUP}.*").mock(side_effect=_by_label)
        api.get(f"{GITG}/related_merge_requests").mock(return_value=httpx.Response(200, json=[]))
        data: dict[str, Any] = toolkit.find_issues(org="GNOME Foundation")
    assert data["count"] == 1
    issue = data["issues"][0]
    assert issue["repo"] == "gitlab.gnome.org/GNOME/gitg" and issue["number"] == 494
    assert issue["availability"] == "available"
    assert issue["gsoc_org"] == "GNOME Foundation"
    assert data["note"].startswith("Searching GNOME Foundation on gitlab.gnome.org/GNOME ")
    assert "GitLab's public API" in data["note"]
    assert data["labels_used"][0] == "4. Newcomers"
    assert data["next_steps"] == []


def test_no_issues_on_gitlab_says_where_to_look(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = _toolkit(monkeypatch, "https://gitlab.gnome.org/")
    with respx.mock(assert_all_called=False) as api:
        api.get(url__regex=rf"{GROUP}.*").mock(return_value=httpx.Response(200, json=[]))
        data = toolkit.find_issues(org="GNOME Foundation", label="Newcomers")
    assert data["count"] == 0 and data["labels_used"] == ["Newcomers"]
    assert any("gitlab.gnome.org/GNOME" in step for step in data["next_steps"])
    assert any("matrix.to" in step for step in data["next_steps"])


def test_a_host_that_is_not_gitlab_keeps_the_old_error(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = _toolkit(monkeypatch, "https://code.example.org/foo")
    with respx.mock(assert_all_called=False) as api:
        api.get(url__regex=r"https://code\.example\.org/.*").mock(
            return_value=httpx.Response(200, text="<html>not an api</html>")
        )
        with pytest.raises(NotFoundError) as caught:
            toolkit.find_issues(org="GNOME Foundation")
    assert "outside GitHub" in str(caught.value)
    assert (caught.value.hint or "").startswith("Open https://code.example.org/foo ")


def test_a_bare_host_with_no_known_group_keeps_the_old_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _toolkit(monkeypatch, "https://invent.kde.org")
    with pytest.raises(NotFoundError) as caught:
        toolkit.find_issues(org="GNOME Foundation")
    assert (caught.value.hint or "").startswith("Open https://invent.kde.org ")


def test_own_gitlab_issues_come_before_linked_github_projects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # QEMU's ideas page names rust-vmm and coconut-svsm on GitHub; its own issues are on
    # gitlab.com/qemu-project/qemu and were never searched.
    toolkit = _toolkit(monkeypatch, "https://gitlab.com/qemu-project/qemu")
    monkeypatch.setattr(
        toolkit,
        "_gsoc_owners",
        lambda name, language=None: (
            [],
            ["rust-vmm"],
            "Searching GNOME Foundation: it lists no GitHub organization, so the GitHub "
            "projects its ideas page names: rust-vmm.",
        ),
    )
    on_github = IssueCandidate(
        repo="rust-vmm/vhost",
        number=1,
        title="x",
        url="https://github.com/rust-vmm/vhost/issues/1",
        availability=Availability.AVAILABLE,
        beginner_score=99,
    )
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **kwargs: [on_github])
    qemu = "https://gitlab.com/api/v4/projects/qemu-project%2Fqemu/issues"
    with respx.mock(assert_all_called=False) as api:
        api.get(url__regex=r"https://gitlab\.com/api/v4/groups/.*").mock(
            return_value=httpx.Response(404, json={"message": "404 Group Not Found"})
        )
        api.get(url__regex=rf"{qemu}\?.*").mock(
            side_effect=_listing(
                "good first issue", "https://gitlab.com/qemu-project/qemu/-/issues/7"
            )
        )
        api.get(f"{qemu}/7/related_merge_requests").mock(return_value=httpx.Response(200, json=[]))
        data = toolkit.find_issues(org="GNOME Foundation")
    assert [i["repo"] for i in data["issues"]] == ["gitlab.com/qemu-project/qemu", "rust-vmm/vhost"]
    assert "gitlab.com/qemu-project/qemu" in data["note"]
    assert "Its own repositories come first" in data["note"]
