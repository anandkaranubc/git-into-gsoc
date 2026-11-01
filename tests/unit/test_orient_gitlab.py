"""`orient` reads a project link on a GitLab host."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.service import GSoCToolkit

API = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg"
runner = CliRunner()


def _mock(api: respx.MockRouter) -> None:
    now = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    api.get(url__regex=rf"{API}\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "path_with_namespace": "GNOME/gitg",
                "web_url": "https://gitlab.gnome.org/GNOME/gitg",
                "default_branch": "master",
                "last_activity_at": now,
            },
        )
    )
    api.get(url__regex=rf"{API}/repository/tree.*").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"path": "README.md", "type": "blob", "name": "README.md"},
                {"path": "gitg", "type": "tree", "name": "gitg"},
                {"path": "gitg/main.vala", "type": "blob", "name": "main.vala"},
            ],
        )
    )
    api.get(
        url__regex=rf"{API}/(languages|repository/commits|merge_requests|repository/branches|protected_branches).*"
    ).mock(return_value=httpx.Response(200, json=[]))


def test_orient_accepts_a_gitlab_project_link() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        data = GSoCToolkit().orient_repo("https://gitlab.gnome.org/GNOME/gitg")
    assert data["repo"] == "gitlab.gnome.org/GNOME/gitg"
    assert data["docs"]["readme"] == "README.md"
    assert data["code_map"][0]["path"] == "gitg"
    assert data["maintainers"]["commits_90d"] == 0 and data["example_pr"] is None


def test_orient_renders_a_gitlab_project() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        result = runner.invoke(app, ["orient", "https://gitlab.gnome.org/GNOME/gitg"])
    assert result.exit_code == 0, result.output
    assert "gitlab.gnome.org/GNOME/gitg" in result.stdout and "README.md" in result.stdout
