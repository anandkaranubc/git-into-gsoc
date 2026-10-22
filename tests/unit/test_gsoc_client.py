"""The organization client: the official list, the embedded snapshot, the archive fallbacks, and
past projects."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from conftest import load_fixture
from git_into_gsoc.gsoc.client import GSoCClient, github_refs, normalize_name
from git_into_gsoc.scoring.org_match import expand_terms

OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


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
        yield router


def test_unannounced_year_falls_back_to_latest_official(api: respx.MockRouter) -> None:
    catalog, orgs = GSoCClient().catalog(2027)
    assert catalog.year == 2026
    assert catalog.source == "official"
    assert "not announced" in catalog.note
    assert len(orgs) == 5
    assert all(o.official for o in orgs)


def test_official_orgs_carry_history_and_links(api: respx.MockRouter) -> None:
    _, orgs = GSoCClient().catalog(2027)
    radio = next(o for o in orgs if o.name == "GNU Radio")
    assert len(radio.years_active) >= 10
    assert radio.projects_by_year[2026] >= 1
    assert radio.ideas_url
    assert radio.github_orgs
    assert {c.kind for c in radio.channels} & {"chat", "mailingList", "email"}


def test_python_science_ranking(api: respx.MockRouter) -> None:
    _, ranked = GSoCClient().search_organizations(
        technologies=["python"], topics=["astronomy"], year=2027
    )
    assert ranked[0].name == "OpenAstronomy"
    assert any("python" in r.lower() for r in ranked[0].match_reasons)


def test_single_letter_language_needs_exact_tag(api: respx.MockRouter) -> None:
    _, ranked = GSoCClient().search_organizations(technologies=["c"], year=2027, limit=20)
    assert ranked
    for org in ranked:
        assert "c" in expand_terms(org.technologies) | expand_terms(org.topics)


def test_aliases_match(api: respx.MockRouter) -> None:
    client = GSoCClient()
    _, via_alias = client.search_organizations(technologies=["py"], year=2027)
    _, direct = client.search_organizations(technologies=["python"], year=2027)
    assert [o.name for o in via_alias] == [o.name for o in direct]


def test_unknown_query_returns_nothing(api: respx.MockRouter) -> None:
    _, ranked = GSoCClient().search_organizations(query="zzzunlikelyterm", year=2027)
    assert ranked == []


def test_org_details_include_recent_projects(api: respx.MockRouter) -> None:
    org = GSoCClient().get_organization("sympy", year=2027)
    assert org is not None
    assert org.name == "SymPy"
    assert org.recent_projects
    assert org.recent_projects[0].year >= org.recent_projects[-1].year


def test_org_details_fall_back_to_archive_history(api: respx.MockRouter) -> None:
    org = GSoCClient().get_organization("3DTK", year=2027)
    assert org is not None
    assert not org.official
    assert org.years_active


def test_past_project_search(api: respx.MockRouter) -> None:
    projects = GSoCClient().search_projects("astropy", limit=5)
    assert projects
    assert all("astropy" in (p.title + p.summary).lower() for p in projects)


def test_archive_fallback_when_official_site_down() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith=OFFICIAL).mock(return_value=httpx.Response(503))
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=_archive_year(2026))
        )
        catalog, orgs = GSoCClient().catalog(2027)
    assert catalog.source == "archive"
    assert catalog.year == 2026
    assert any(o.name == "SymPy" for o in orgs)


def test_github_refs() -> None:
    orgs, repos = github_refs(
        "https://github.com/mapeditor/tiled",
        "https://github.com/rapid7/metasploit-framework/wiki/GSoC",
        "https://docs.google.com/document/d/x",
        "https://sympy.github.io/",
        "https://github.com/orgs/foo",
    )
    assert orgs == ["mapeditor", "rapid7", "sympy"]
    assert repos == ["mapeditor/tiled"]


def test_normalize_name() -> None:
    assert normalize_name("GNU Radio") == normalize_name("gnu-radio") == "gnuradio"


def test_catalog_uses_embedded_history_without_fetching_the_archive() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        archive = router.get(f"{ARCHIVE}/organizations.json").mock(return_value=httpx.Response(500))
        _, orgs = GSoCClient().catalog(2027)
    sympy = next(o for o in orgs if o.name == "SymPy")
    assert len(sympy.years_active) >= 10  # from the embedded snapshot
    assert not archive.called


def test_snapshot_serves_catalog_when_every_source_is_down() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith=OFFICIAL).mock(return_value=httpx.Response(503))
        router.get(url__startswith=ARCHIVE).mock(return_value=httpx.Response(503))
        catalog, orgs = GSoCClient().catalog(2027)
    assert catalog.source == "snapshot"
    assert catalog.year >= 2026
    assert len(orgs) > 100
    assert "snapshot" in catalog.note and "Verify" in catalog.note
    assert any(o.name == "SymPy" and o.ideas_url for o in orgs)


def test_snapshot_files_are_fresh_and_complete() -> None:
    from git_into_gsoc.gsoc.snapshot import build_history, load_history, load_official

    history = load_history()
    official = load_official()
    assert len(history["organizations"]) > 400
    assert len(official["organizations"]) > 100
    assert str(official["year"]) in history["organizations"]["SymPy"]["years"]
    compact = build_history(load_fixture("archive_organizations.json"))
    assert set(compact["SymPy"]["years"]["2026"]) == {"num_projects"}
    assert compact["SymPy"]["years"]["2026"]["num_projects"] >= 1


def _archive_org(name: str, titles: list[str]) -> dict[str, Any]:
    projects = [{"title": t, "short_description": "", "project_url": None} for t in titles]
    return {"name": name, "years": {"2025": {"num_projects": len(titles), "projects": projects}}}


def test_org_past_projects_never_borrow_from_similar_names() -> None:
    archive = [
        _archive_org("Git", ["Refactor git-submodule"]),
        _archive_org("GitLab", ["GitLab runner metrics"]),
        _archive_org("Cuneiform Digital Library Initiative (CDLI)", ["Digital tablets"]),
    ]
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=archive)
        )
        projects = GSoCClient().search_projects(org="Git")
    assert [p.org for p in projects] == ["Git"]


def test_official_names_find_their_archive_history_without_filler_words() -> None:
    # The archive calls it "The Apache Software Foundation"; without this the
    # official list showed a veteran organization as a first-year one.
    hist = GSoCClient()._history_for("Apache Software Foundation")
    assert hist is not None
    assert hist["name"] == "The Apache Software Foundation"
    assert len(hist["years"]) >= 5
    assert GSoCClient()._history_for("Apache DataFusion")["name"] == "Apache DataFusion"


def test_lookup_by_one_word_and_unknown_names(api: respx.MockRouter) -> None:
    client = GSoCClient()
    radio = client.get_organization("radio", year=2027)
    assert radio is not None and radio.name == "GNU Radio"
    assert client.get_organization("Meta", year=2027) is None  # not inside "Metasploit"
    similar, _ = client.suggest_organizations("Metaspolit", year=2027)
    assert similar[0] == "Metasploit"
