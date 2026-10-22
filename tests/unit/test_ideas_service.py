"""The `ideas` command: pages, umbrella sub-pages, issue trackers, past proposals, and the one
reader the snapshot shares."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc.cli import app
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ideas"
SYMPY_RAW = "https://raw.githubusercontent.com/wiki/sympy/sympy/GSoC-Ideas.md"
PG_PAGE = "https://wiki.postgresql.org/wiki/GSoC_2026"


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


def test_org_ideas_parses_wiki_and_ranks_by_profile(api: respx.MockRouter) -> None:
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=_read("wiki_headings.md")))
    data = GSoCToolkit().org_ideas("SymPy", skills=["sphinx"], difficulty="easy")
    assert data["found"] and data["layout"] == "headings"
    assert data["fetched_url"] == SYMPY_RAW
    assert data["ideas"][0]["title"].startswith("Project 2")
    assert data["ideas"][0]["match_reasons"]
    assert any("disclose" in s.lower() for s in data["ai_policy"])
    assert "next_step" in data


def test_org_ideas_follows_umbrella_sub_pages(api: respx.MockRouter) -> None:
    api.get(PG_PAGE).mock(return_value=httpx.Response(200, text=_read("umbrella_index.md")))
    api.get("https://alpha.example.org/gsoc/ideas").mock(
        return_value=httpx.Response(200, text=_read("bullet_labels.md"))
    )
    api.get("https://raw.githubusercontent.com/wiki/beta/beta/GSoC-2026-Ideas.md").mock(
        return_value=httpx.Response(404)
    )
    # A 404 for the raw file makes the reader try the page itself; it is gone too.
    api.get("https://github.com/beta/beta/wiki/GSoC-2026-Ideas").mock(
        return_value=httpx.Response(404)
    )
    api.get("https://gamma.example.org/summer-of-code").mock(
        return_value=httpx.Response(200, text="# Gamma\n\nNothing here yet.\n")
    )
    data = GSoCToolkit().org_ideas("PostgreSQL")
    assert data["layout"] == "index"
    assert data["count"] == 2
    assert {i["section"] for i in data["ideas"]} == {"Sub-project Alpha"}
    assert [p["title"] for p in data["followed"]] == ["Sub-project Alpha"]
    assert "Umbrella" in data["note"]


def test_org_ideas_uses_prose_blocks_when_links_lead_nowhere(api: respx.MockRouter) -> None:
    body = " ".join(["The goal is a faster importer that handles broken files gracefully."] * 5)
    page = "# Projects\n\n"
    for name in ("Importer", "Exporter", "Indexer"):
        page += f"### {name} rewrite\n\n{body}\n\n"
        page += f"Discussion: https://forum.example.org/{name.lower()}\n\n"
    api.get(PG_PAGE).mock(return_value=httpx.Response(200, text=page))
    api.get(url__regex=r"https://forum\.example\.org/.*").mock(return_value=httpx.Response(404))
    data = GSoCToolkit().org_ideas("PostgreSQL")
    assert data["layout"] == "headings"
    titles = {i["title"] for i in data["ideas"]}
    assert titles == {"Importer rewrite", "Exporter rewrite", "Indexer rewrite"}
    assert data["followed"] == [] and data["sub_pages"] == []


def test_org_ideas_unreachable_is_honest(api: respx.MockRouter) -> None:
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(403))
    data = GSoCToolkit().org_ideas("SymPy")
    assert data["layout"] == "unreachable"
    assert data["ideas"] == []


def test_org_ideas_unknown_org(api: respx.MockRouter) -> None:
    data = GSoCToolkit().org_ideas("no-such-org-xyz")
    assert data["found"] is False


def test_ideas_from_issue_tracker(api: respx.MockRouter) -> None:
    search = api.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "number": 7,
                        "title": "Idea: better exporter",
                        "html_url": "https://github.com/o/r/issues/7",
                        "body": "Build a faster exporter.\n\nSkills: Go",
                        "labels": [{"name": "GSoC 2026"}],
                    },
                    {"number": 8, "title": "a pr", "html_url": "x", "pull_request": {}},
                ]
            },
        )
    )
    doc = GSoCToolkit()._ideas_from_issues(
        "https://github.com/o/r/issues?q=label%3A%22GSoC+2026%22", "o/r", "GSoC 2026"
    )
    assert doc is not None and doc.layout == "issues"
    assert [i.title for i in doc.ideas] == ["Idea: better exporter"]
    assert 'label:"GSoC 2026"' in search.calls[0].request.url.params["q"]


def test_cli_ideas_table(api: respx.MockRouter) -> None:
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=_read("wiki_headings.md")))
    result = runner.invoke(app, ["ideas", "SymPy", "--skills", "python"])
    assert result.exit_code == 0, result.output
    assert "trajectory" in result.stdout
    assert "350" in result.stdout
    assert "AI" in result.stdout or "disclose" in result.stdout


def test_past_proposal_folders_match_org_names() -> None:
    from git_into_gsoc.gsoc.archive import proposal_folders

    trees = {
        "SammanSarkar/GSoC_archive_2025": [
            {"path": "SymPy", "type": "tree"},
            {"path": "SymPy/proposal-a.pdf", "type": "blob"},
            {"path": "SymPy/proposal-b.pdf", "type": "blob"},
            {"path": "Sugar Labs", "type": "tree"},
            {"path": "Sugar Labs/x.pdf", "type": "blob"},
        ],
        "pavanjoshi914/GSoC_archive": [
            {"path": "2024", "type": "tree"},
            {"path": "2024/sympy", "type": "tree"},
            {"path": "2024/sympy/one.pdf", "type": "blob"},
        ],
        # Archives sorted by year name each file "Org - Year - Author".
        "COPS-IITBHU/GSoC-Accepted-Proposals": [
            {"path": "2024", "type": "tree"},
            {"path": "2024/SymPy - 2024 - Someone.pdf", "type": "blob"},
            {"path": "2024/Other Org - 2024 - Someone Else.pdf", "type": "blob"},
            {"path": "2023", "type": "tree"},
            {"path": "2023/sympy-2023-proposal.pdf", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ],
    }
    found = proposal_folders(lambda owner, repo: trees.get(f"{owner}/{repo}", []), "SymPy")
    assert [(f["repo"], f["path"], f["files"]) for f in found] == [
        ("SammanSarkar/GSoC_archive_2025", "SymPy", 2),
        ("COPS-IITBHU/GSoC-Accepted-Proposals", "2023", 1),
        ("COPS-IITBHU/GSoC-Accepted-Proposals", "2024", 1),
        ("pavanjoshi914/GSoC_archive", "2024/sympy", 1),
    ]
    assert found[0]["url"].endswith("/tree/HEAD/SymPy")
    assert proposal_folders(lambda o, r: [], "SymPy") == []


def test_org_ideas_links_past_proposals(api: respx.MockRouter) -> None:
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=_read("wiki_headings.md")))
    api.get(url__regex=r"https://api\.github\.com/repos/.*/git/trees/HEAD.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "tree": [{"path": "SymPy", "type": "tree"}, {"path": "SymPy/p.pdf", "type": "blob"}]
            },
        )
    )
    data = GSoCToolkit().org_ideas("SymPy")
    assert data["past_proposals"]
    assert data["past_proposals"][0]["files"] == 1
    assert "never copy" in data["past_proposals_note"].lower()


def test_org_ideas_says_when_the_page_is_from_last_year(api: respx.MockRouter) -> None:
    # The target year is 2027 and only the 2026 list exists, so the page is 2026's.
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=_read("wiki_headings.md")))
    data = GSoCToolkit().org_ideas("SymPy")
    assert data["page_year"] == 2026
    assert data["note"].startswith("This is the ideas page from GSoC 2026.")
    assert "2027" in data["note"]
    current = GSoCToolkit().org_ideas("SymPy", year=2026)
    assert "from GSoC 2026" not in current["note"]


def test_the_snapshot_reads_an_ideas_page_as_ideas_does(api: respx.MockRouter) -> None:
    # The monthly snapshot had its own way of following links: it listed two headings
    # for ML4SCI ("Projects in 2026") where `ideas` found 70 ideas. One reader now.
    from git_into_gsoc.matching import signals

    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=_read("wiki_headings.md")))
    api.get(PG_PAGE).mock(return_value=httpx.Response(200, text=_read("umbrella_index.md")))
    api.get("https://alpha.example.org/gsoc/ideas").mock(
        return_value=httpx.Response(200, text=_read("bullet_labels.md"))
    )
    api.get("https://raw.githubusercontent.com/wiki/beta/beta/GSoC-2026-Ideas.md").mock(
        return_value=httpx.Response(404)
    )
    api.get("https://github.com/beta/beta/wiki/GSoC-2026-Ideas").mock(
        return_value=httpx.Response(404)
    )
    api.get("https://gamma.example.org/summer-of-code").mock(
        return_value=httpx.Response(200, text="# Gamma\n\nNothing here yet.\n")
    )
    toolkit = GSoCToolkit()
    for name in ("SymPy", "PostgreSQL"):
        shown = toolkit.org_ideas(name, limit=500)
        url = toolkit.gsoc.get_organization(name).ideas_url
        doc, _ = toolkit.read_ideas_page(url)
        assert doc is not None
        assert sorted(i.title for i in doc.ideas) == sorted(i["title"] for i in shown["ideas"])
        snapshot = signals._ideas_for(toolkit, {"ideas_link": url}, 10)
        expected = signals.summarize_ideas(shown["ideas"], layout=shown["layout"], url=url)
        assert snapshot is not None
        assert (snapshot["layout"], snapshot["count"]) == (shown["layout"], expected["count"])
