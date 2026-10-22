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
    # `repos` reads recent pull requests of its top candidates; none here.
    api.get(url__regex=r"https://api\.github\.com/repos/[\w.-]+/[\w.-]+/pulls.*").mock(
        return_value=httpx.Response(200, json=[])
    )


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


def _without_owners(toolkit: GSoCToolkit, source_code: str | None = None) -> None:
    """Make SymPy look like the PSF: a GSoC organization that lists no GitHub owner."""
    real = toolkit.gsoc.get_organization

    def lookup(name: str, year: int | None = None) -> Any:
        org = real(name, year=year)
        update: dict[str, Any] = {"github_orgs": []}
        if source_code:
            update["source_code"] = source_code
        return org.model_copy(update=update) if org else None

    toolkit.gsoc.get_organization = lookup  # type: ignore[method-assign]


def _discover_without_owners(page: str, source_code: str | None = None) -> dict[str, Any]:
    with respx.mock(assert_all_called=False) as api:
        _mock_sources(api)
        api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=page))
        api.get(url__regex=r"https://api\.github\.com/(orgs|users)/[\w.-]+/repos.*").mock(
            side_effect=_repos
        )
        api.get(url__regex=r"https://api\.github\.com/search/issues.*").mock(
            return_value=httpx.Response(200, json={"total_count": 0, "items": []})
        )
        toolkit = GSoCToolkit()
        _without_owners(toolkit, source_code)
        return toolkit.discover_repos("SymPy", limit=10)


def test_an_org_without_github_owners_is_found_through_its_ideas_page() -> None:
    page = (
        "# Sub-organizations\n\n"
        "- [Zeta](https://github.com/zeta-org)\n"
        "- [Eta tools](https://github.com/eta-tools/eta)\n"
        "- [Theta](https://theta.example.org/contribute)\n"
    )
    data = _discover_without_owners(page)
    assert data["org"] == "SymPy"
    assert {"zeta-org", "eta-tools"} <= set(data["github_owners"])
    assert {"zeta-org/core", "eta-tools/core"} <= {r["full_name"] for r in data["repos"]}


def test_an_org_without_github_anywhere_gets_a_clear_error() -> None:
    import pytest

    from git_into_gsoc.errors import NotFoundError

    with pytest.raises(NotFoundError, match="lists no GitHub organization") as caught:
        _discover_without_owners("# Ideas\n\nAll our code is on https://gitlab.example.org.\n")
    assert caught.value.hint and "ideas page" in caught.value.hint


def test_repositories_the_ideas_page_names_under_other_owners_are_ranked() -> None:
    # Open Robotics (2026-10-21): its ideas page names colcon/colcon-mixin and
    # open-rmf/crossflow, but `repos` listed only openrobotics/osrf repositories.
    page = (
        "# Ideas\n\n## Mixins\nWork in https://github.com/colcon/colcon-mixin to add mixins.\n"
        "Mentor: https://github.com/jdoe\n"
        "Inspired by https://github.com/someone/personal-bench (a personal repo).\n"
    )

    def repo_meta(request: httpx.Request) -> httpx.Response:
        owner, name = request.url.path.split("/")[2:4]
        kind = "User" if owner == "someone" else "Organization"
        return httpx.Response(
            200,
            json={
                "full_name": f"{owner}/{name}",
                "html_url": f"https://github.com/{owner}/{name}",
                "owner": {"login": owner, "type": kind},
                "language": "Python",
                "stargazers_count": 50,
                "pushed_at": datetime.now(UTC).isoformat(),
                "archived": False,
                "fork": False,
            },
        )

    with respx.mock(assert_all_called=False) as api:
        _mock_sources(api)
        api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=page))
        api.get(url__regex=r"https://api\.github\.com/orgs/[\w.-]+/repos.*").mock(
            side_effect=_repos
        )
        api.get(url__regex=r"https://api\.github\.com/repos/[\w.-]+/[\w.-]+$").mock(
            side_effect=repo_meta
        )
        api.get(url__regex=r"https://api\.github\.com/search/issues.*").mock(
            return_value=httpx.Response(200, json={"total_count": 0, "items": []})
        )
        data = GSoCToolkit().discover_repos("SymPy", limit=10)
    names = {r["full_name"] for r in data["repos"]}
    assert "colcon/colcon-mixin" in names
    assert "someone/personal-bench" not in names  # a person's repository, not a project
    mixin = next(r for r in data["repos"] if r["full_name"] == "colcon/colcon-mixin")
    assert any("ideas page" in reason for reason in mixin["reasons"])


def test_code_hosted_outside_github_is_named_before_linked_projects() -> None:
    # ns-3 (2026-10-21): its code is on gitlab.com/nsnam/ns-3-dev, and `repos ns-3`
    # showed only DEFIANCE-project repositories its ideas page links to.
    page = "# Ideas\n\n- [DEFIANCE](https://github.com/DEFIANCE-project/ns3-DEFIANCE)\n"
    data = _discover_without_owners(page, source_code="https://gitlab.com/nsnam/ns-3-dev")
    assert data["main_code"] == "https://gitlab.com/nsnam/ns-3-dev"
    assert "outside GitHub" in data["note"]
    on_github = _discover_without_owners(page, source_code="https://github.com/sympy/sympy")
    assert on_github["main_code"] is None


def test_the_no_github_error_points_at_the_code() -> None:
    import pytest

    from git_into_gsoc.errors import NotFoundError

    with pytest.raises(NotFoundError) as caught:
        _discover_without_owners("# Ideas\n\nNo links.\n", source_code="https://gitlab.com/a/b")
    assert caught.value.hint and "https://gitlab.com/a/b" in caught.value.hint
