"""`repos` ranks a GitLab group's projects for organizations whose code is there."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.errors import NotFoundError
from git_into_gsoc.models import OrgSummary
from git_into_gsoc.service import GSoCToolkit

PROJECTS = "https://gitlab.gnome.org/api/v4/groups/GNOME/projects"


def _toolkit(monkeypatch: pytest.MonkeyPatch, source_code: str) -> GSoCToolkit:
    toolkit = GSoCToolkit()
    org = OrgSummary(name="GNOME Foundation", github_orgs=[], source_code=source_code)
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: org)
    return toolkit


def _project(path: str, stars: int) -> dict[str, Any]:
    return {
        "name": path.rsplit("/", 1)[1],
        "path_with_namespace": path,
        "web_url": f"https://gitlab.gnome.org/{path}",
        "description": f"{path}",
        "star_count": stars,
        "last_activity_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "archived": False,
    }


def test_repos_lists_a_gitlab_groups_projects(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = _toolkit(monkeypatch, "https://gitlab.gnome.org/")
    with respx.mock(assert_all_called=False) as api:
        api.get(url__regex=rf"{PROJECTS}.*").mock(
            return_value=httpx.Response(
                200, json=[_project("GNOME/gtk", 300), _project("GNOME/gitg", 20)]
            )
        )
        api.get(url__regex=r"https://gitlab\.gnome\.org/api/v4/projects/.*/languages").mock(
            return_value=httpx.Response(200, json={"C": 90.0, "Python": 10.0})
        )
        data = toolkit.discover_repos("GNOME Foundation", limit=5)
    assert [r["full_name"] for r in data["repos"]] == ["GNOME/gtk", "GNOME/gitg"]
    assert data["github_owners"] == ["gitlab.gnome.org/GNOME"]
    assert data["repos"][0]["language"] == "C" and data["repos"][0]["url"].startswith("https://")
    assert "GitLab" in data["note"]
    assert 'issues --org "GNOME Foundation"' in data["next_step"]
    assert "repo https://gitlab.gnome.org/GNOME/gtk grades it" in data["next_step"]
    assert data["main_code"] == "https://gitlab.gnome.org/"


def test_a_bare_host_with_no_known_group_keeps_the_old_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _toolkit(monkeypatch, "https://invent.kde.org")
    with pytest.raises(NotFoundError) as caught:
        toolkit.discover_repos("GNOME Foundation", limit=5)
    assert "lists no GitHub organization" in str(caught.value)
    assert (caught.value.hint or "").startswith("Its code is at https://invent.kde.org;")
