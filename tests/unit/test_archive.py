"""The official archive: mentor summaries per organization and the `mentors` command."""

from __future__ import annotations

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc.cli import app
from git_into_gsoc.gsoc.archive import ArchiveClient, github_repo_of, summarize_mentors

runner = CliRunner()
ARCHIVE = "https://summerofcode.withgoogle.com/api/archive"


def test_github_repo_of_handles_hosts() -> None:
    assert github_repo_of("https://github.com/sympy/sympy/pull/100") == "sympy/sympy"
    assert github_repo_of("https://github.com/sympy/sympy_doc") == "sympy/sympy_doc"
    assert github_repo_of("https://gist.github.com/x/abc") is None
    assert github_repo_of("https://medium.com/@x/post") is None
    assert github_repo_of(None) is None


def test_summarize_mentors_aggregates_years_projects_and_repos() -> None:
    fixture = load_fixture("archive_projects.json")
    projects = {int(y): items for y, items in fixture.items()}
    summary = summarize_mentors(projects, org_slug="sympy", org_name="SymPy")
    assert summary["projects"] == 4
    assert summary["years_covered"] == [2024, 2025]
    alice = summary["mentors"][0]
    assert alice["name"] == "Alice Mentor"
    assert alice["years"] == [2024, 2025] and alice["projects"] == 3
    assert alice["recent_projects"][0]["year"] == 2025
    assert summary["mentors_per_year"] == {"2024": 2, "2025": 3}
    assert summary["repos_touched"][0] == {"repo": "sympy/sympy", "projects": 1}
    assert {"tag": "python", "projects": 4} in summary["top_tech_tags"]
    assert summary["returning_mentors"] == 1


def test_summarize_mentors_unknown_org_is_empty() -> None:
    summary = summarize_mentors({2025: []}, org_slug="nope", org_name="Nope")
    assert summary["projects"] == 0 and summary["mentors"] == []


@pytest.fixture
def api() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ARCHIVE}/programs/").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_programs.json"))
        )
        fixture = load_fixture("archive_projects.json")
        for year, items in fixture.items():
            router.get(f"{ARCHIVE}/programs/{year}/projects/").mock(
                return_value=httpx.Response(200, json=items)
            )
        router.get(f"{ARCHIVE}/programs/2023/projects/").mock(return_value=httpx.Response(404))
        yield router


def test_archive_client_reads_recent_years(api: respx.MockRouter) -> None:
    client = ArchiveClient()
    assert client.archived_years()[:2] == [2025, 2024]
    projects = client.projects_by_year(years=3)
    assert list(projects) == [2025, 2024, 2023]  # fetched side by side, still newest first
    assert len(projects[2025]) == 2 and projects[2023] == []


def test_cli_mentors_table(api: respx.MockRouter) -> None:
    official = "https://summerofcode.withgoogle.com/api/program"
    api.get(f"{official}/2027/organizations/").mock(return_value=httpx.Response(404))
    api.get(f"{official}/2026/organizations/").mock(
        return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
    )
    api.get("https://api.gsocorganizations.dev/organizations.json").mock(
        return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
    )
    result = runner.invoke(app, ["mentors", "SymPy"])
    assert result.exit_code == 0, result.output
    assert "Alice Mentor" in result.stdout
    assert "sympy/sympy" in result.stdout
    assert "2024" in result.stdout and "2025" in result.stdout
