"""An umbrella organization's repositories come from the projects its index links to."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import respx

from conftest import load_fixture
from git_into_gsoc.service import GSoCToolkit, _linked_github_projects

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ideas" / "umbrella_links_index.md"
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
# SymPy's ideas page in the fixture data stands in for an umbrella index here.
SYMPY_RAW = "https://raw.githubusercontent.com/wiki/sympy/sympy/GSoC-Ideas.md"


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


def _mock_sources(api: respx.MockRouter) -> None:
    api.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
    api.get(f"{OFFICIAL}/2026/organizations/").mock(
        return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
    )
    api.get(f"{ARCHIVE}/organizations.json").mock(
        return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
    )
    api.get(f"{ARCHIVE}/2026.json").mock(return_value=httpx.Response(200, json=_archive_year(2026)))


def _repos(request: httpx.Request) -> httpx.Response:
    owner = request.url.path.split("/")[2]
    return httpx.Response(
        200,
        json=[
            {
                "full_name": f"{owner}/core",
                "html_url": f"https://github.com/{owner}/core",
                "description": "the main package",
                "language": "Python",
                "stargazers_count": 10,
                "pushed_at": datetime.now(UTC).isoformat(),
                "archived": False,
                "fork": False,
                "has_issues": True,
            }
        ],
    )


def test_linked_projects_come_from_github_links_only() -> None:
    pages = [
        {"title": "Alpha Lab", "url": "https://github.com/alpha-lab/alpha/wiki/GSoC-2026-Projects"},
        {"title": "Gamma", "url": "https://gamma-solver.ai/dev/#google_summer_of_code"},
        {"title": "Alpha again", "url": "https://github.com/alpha-lab/other/wiki/GSoC"},
        {"title": "Topics", "url": "https://github.com/topics/gsoc"},
        {"title": "Umbrella itself", "url": "https://github.com/sympy/gsoc/wiki/GSoC"},
    ]
    owners, repos = _linked_github_projects(pages, exclude=["sympy"])
    assert owners == [("alpha-lab", "Alpha Lab")]
    assert repos == {"alpha-lab/alpha", "alpha-lab/other", "sympy/gsoc"}


def test_umbrella_org_repos_include_member_projects() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock_sources(api)
        api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=FIXTURE.read_text()))
        api.get(url__regex=r"https://api\.github\.com/orgs/[\w.-]+/repos.*").mock(
            side_effect=_repos
        )
        api.get(url__regex=r"https://api\.github\.com/search/issues.*").mock(
            return_value=httpx.Response(200, json={"total_count": 0, "items": []})
        )
        data = GSoCToolkit().discover_repos("SymPy", limit=10)
    assert data["github_owners"][0] == "sympy"
    assert {"alpha-lab", "beta-toolkit", "delta-stats", "epsilon-viz"} <= set(data["github_owners"])
    assert data["linked_projects"][0] == {"owner": "alpha-lab", "title": "Alpha Lab"}
    names = {r["full_name"] for r in data["repos"]}
    assert {"sympy/core", "alpha-lab/core"} <= names
    alpha = next(r for r in data["repos"] if r["full_name"] == "alpha-lab/core")
    assert any("umbrella ideas page (Alpha Lab)" in reason for reason in alpha["reasons"])
