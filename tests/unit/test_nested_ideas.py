"""Umbrella ideas pages three levels deep: index, project pages, one link per proposal.

ML4SCI (2026-10-22) lists 18 projects, each with a relative "List of proposals" link,
and each project page lists its proposals as links. `ideas` showed three "ideas" taken
from Google's "how it works" page instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from conftest import load_fixture
from git_into_gsoc.gsoc.project_ideas import html_to_lines
from git_into_gsoc.service import GSoCToolkit

OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ideas"
PAGE = "https://wiki.postgresql.org/wiki/GSoC_2026"  # the fixture org's ideas page
SITE = "https://wiki.postgresql.org"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


@pytest.fixture
def api() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=_archive_year(2026))
        )
        router.get(url__regex=r"https://api\.github\.com/repos/.*/git/trees/HEAD.*").mock(
            return_value=httpx.Response(404)
        )
        yield router


def test_relative_links_are_kept_against_the_page_address() -> None:
    lines = html_to_lines(
        '<html><body><p><a href="/gsoc/projects/2026/project_CMS.html">List of proposals'
        '</a></p><p><a href="#top">Top</a></p></body></html>',
        base_url="https://ml4sci.org/activities/gsoc2026.html",
    )
    assert lines == [
        "List of proposals (https://ml4sci.org/gsoc/projects/2026/project_CMS.html)",
        "Top",
    ]


def test_a_three_level_ideas_page_lists_every_proposal_once(api: respx.MockRouter) -> None:
    api.get(PAGE).mock(return_value=httpx.Response(200, text=_read("nested_index.html")))
    pages = {
        "project_CMS.html": "nested_project_cms.html",
        "project_DEEPLENSE.html": "nested_project_deeplense.html",
        "project_EXXA.html": "nested_project_exxa.html",
    }
    for slug, fixture in pages.items():
        api.get(f"{SITE}/gsoc/projects/2026/{slug}").mock(
            return_value=httpx.Response(200, text=_read(fixture))
        )
    institution = api.get(f"{SITE}/gsoc/institutions/2026/alabama.html").mock(
        return_value=httpx.Response(200, text=_read("nested_institution.html"))
    )
    other_year = api.get(f"{SITE}/activities/gsoc2025.html").mock(
        return_value=httpx.Response(200, text="<html><body><h2>Old idea</h2></body></html>")
    )
    program = api.get(url__startswith="https://summerofcode.withgoogle.com/how-it-works").mock(
        return_value=httpx.Response(
            200, text="<html><body><h3>Apply</h3><h3>Code</h3></body></html>"
        )
    )

    data = GSoCToolkit().org_ideas("PostgreSQL", limit=50)

    titles = [i["title"] for i in data["ideas"]]
    assert (
        len(titles) == len(set(titles)) == 6
    )  # 2 + 3 + 1, the repeat on the institution page dropped
    assert "Gravitational Lens Finding" in titles
    # Each project is named from its row, or from its page name when the sentence before
    # the link does not name it ("The purpose of EXXA is ...").
    assert {i["section"] for i in data["ideas"]} == {"CMS", "DeepLense", "EXXA"}
    assert all(i["links"][0].startswith(f"{SITE}/gsoc/2026/proposal_") for i in data["ideas"])
    # Never the program's own pages, another year's page, or a page that adds nothing new.
    assert not program.called and not other_year.called
    assert institution.called
    assert [p["title"] for p in data["followed"]] == ["CMS", "DeepLense", "EXXA"]


def test_an_index_that_lists_one_link_per_proposal_uses_the_links(api: respx.MockRouter) -> None:
    # CERN-HSF (2026-10-22): "Full List of Proposals" links each proposal page. Opening
    # them read their headings ("Description", "Requirements") as ideas.
    index = (
        "<html><body><h1>Summary of GSoC 2026 Proposals</h1><h2>Full List of Proposals</h2><ul>"
        + "".join(
            f'<li><a href="/gsoc/2026/proposal_{slug}.html">{title}</a></li>'
            for slug, title in [
                ("ATLAS_SPOT", "ATLAS: Automated Software Performance Monitoring"),
                ("Belle2_ARM", "Belle2: Enabling Sustainable ARM Support"),
                ("CLAD", "Clad: Enable automatic differentiation of OpenMP programs"),
            ]
        )
        + "</ul></body></html>"
    )
    api.get(PAGE).mock(return_value=httpx.Response(200, text=index))
    proposal = api.get(url__startswith=f"{SITE}/gsoc/2026/proposal_").mock(
        return_value=httpx.Response(200, text="<html><body><h2>Description</h2></body></html>")
    )
    data = GSoCToolkit().org_ideas("PostgreSQL", limit=50)
    assert sorted(i["title"] for i in data["ideas"]) == [  # ranking may reorder them
        "ATLAS: Automated Software Performance Monitoring",
        "Belle2: Enabling Sustainable ARM Support",
        "Clad: Enable automatic differentiation of OpenMP programs",
    ]
    assert not proposal.called
