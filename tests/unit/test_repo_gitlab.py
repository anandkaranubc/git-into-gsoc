"""`repo` grades a project link on a GitLab host."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.models import OrgSummary
from git_into_gsoc.service import GSoCToolkit

API = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg"
runner = CliRunner()


def _iso(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _mock_project(api: respx.MockRouter) -> None:
    api.get(url__regex=rf"{API}\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "path_with_namespace": "GNOME/gitg",
                "web_url": "https://gitlab.gnome.org/GNOME/gitg",
                "default_branch": "master",
                "star_count": 61,
                "last_activity_at": _iso(1),
                "license": {"name": "GPL-2.0+"},
            },
        )
    )
    api.get(url__regex=rf"{API}/repository/tree.*").mock(
        return_value=httpx.Response(200, json=[{"name": ".gitlab-ci.yml", "type": "blob"}])
    )
    api.get(url__regex=rf"{API}/users.*").mock(
        return_value=httpx.Response(200, json=[{"username": "maintainer"}])
    )
    api.get(url__regex=rf"{API}/merge_requests.*").mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=[
                {
                    "iid": 1,
                    "author": {"username": "newcomer"},
                    "created_at": _iso(4),
                    "merged_at": _iso(2),
                    "closed_at": None,
                }
            ]
            if request.url.params.get("state") == "merged"
            else [],
        )
    )
    api.get(url__regex=rf"{API}/(languages|issues_statistics).*").mock(
        return_value=httpx.Response(200, json={})
    )


def test_repo_grades_a_gitlab_project_and_names_the_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = GSoCToolkit()
    orgs = [
        OrgSummary(name="GNOME Foundation", source_code="https://gitlab.gnome.org/"),
        OrgSummary(
            name="GNU Image Manipulation Program",
            source_code="https://gitlab.gnome.org/GNOME/gimp/",
        ),
    ]
    monkeypatch.setattr(toolkit.gsoc, "snapshot_organizations", lambda: orgs)
    with respx.mock(assert_all_called=False) as api:
        _mock_project(api)
        data: dict[str, Any] = toolkit.evaluate_repo("https://gitlab.gnome.org/GNOME/gitg")
    health = data["health"]
    assert health["full_name"] == "gitlab.gnome.org/GNOME/gitg" and health["pr_source"] == "gitlab"
    assert health["has_ci"] and health["outsider_merge_rate"] == 1.0
    assert health["grade"] in "ABCDEF"
    assert 'issues --org "GNOME Foundation"' in data["next_step"]
    assert data["contribution_guide"]["repo"] == "gitlab.gnome.org/GNOME/gitg"
    assert "recommendation" in data


def test_track_saves_the_gitlab_link(monkeypatch: pytest.MonkeyPatch) -> None:
    found = {
        "health": {
            "full_name": "gitlab.gnome.org/GNOME/gitg",
            "url": "https://gitlab.gnome.org/GNOME/gitg",
            "pr_source": "gitlab",
            "grade": "B",
            "health_score": 80.0,
            "signals": [],
            "warnings": [],
            "notes": [],
            "points": [],
        },
        "contribution_guide": {"setup_hints": []},
        "recommendation": "Looks healthy.",
        "next_step": "git-into-gsoc issue URL",
        "track_as": "https://gitlab.gnome.org/GNOME/gitg",
    }
    monkeypatch.setattr(GSoCToolkit, "evaluate_repo", lambda self, full_name: found)
    result = runner.invoke(app, ["repo", "https://gitlab.gnome.org/GNOME/gitg", "--track"])
    assert result.exit_code == 0, result.output
    assert GSoCToolkit().progress.load().tracked_repos == ["https://gitlab.gnome.org/GNOME/gitg"]
