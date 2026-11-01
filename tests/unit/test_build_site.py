"""The organization explorer is generated from the bundled snapshot, so it must
cover every official organization and never let data text break the HTML."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_site import build, ideas_line  # noqa: E402


def test_builds_one_page_per_official_organization(tmp_path: Path) -> None:
    official = json.loads(
        (ROOT / "src/git_into_gsoc/data/official_orgs.json").read_text(encoding="utf-8")
    )
    slugs = build(tmp_path)
    assert len(slugs) == len(official["organizations"])
    index = (tmp_path / "orgs/index.html").read_text(encoding="utf-8")
    for org in official["organizations"]:
        assert (tmp_path / "orgs" / org["slug"] / "index.html").is_file()
        assert f'href="{org["slug"]}/"' in index
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<loc>") == len(slugs) + 4


def test_start_page_ships_the_package_and_asks_the_four_questions(tmp_path: Path) -> None:
    build(tmp_path)
    start = tmp_path / "start"
    page = (start / "index.html").read_text(encoding="utf-8")
    for question in ("1 of 4", "2 of 4", "3 of 4", "4 of 4"):
        assert question in page
    for level in ("new", "some", "experienced"):
        assert f'value="{level}"' in page
    assert 'data-topic="science"' in page
    assert "../orgs/" in page
    worker = (start / "worker.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net/pyodide/v" in worker
    assert "pydantic_settings-" in worker
    assert (start / "page.py").read_text(encoding="utf-8") == (
        ROOT / "scripts/start_page.py"
    ).read_text(encoding="utf-8")
    data = json.loads((start / "orgs.json").read_text(encoding="utf-8"))
    assert data["year"] and len(data["orgs"]) == len(data["descriptions"])
    with zipfile.ZipFile(start / "pkg.zip") as archive:
        names = archive.namelist()
    assert "git_into_gsoc/matching/rank.py" in names
    assert "git_into_gsoc/models.py" in names
    assert all(n.endswith(".py") or n.endswith("py.typed") for n in names)


def test_data_text_is_escaped_and_odd_slugs_are_refused(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    orgs = [
        {
            "name": "Ampersand & <Co>",
            "slug": "ampersand-co",
            "tagline": 'Says "hi"',
            "categories": ["Web"],
            "tech_tags": ["c++"],
            "topic_tags": [],
            "ideas_link": "https://example.org/ideas?a=1&b=2",
        },
        {"name": "Escapee", "slug": "../escapee", "categories": [], "tech_tags": []},
    ]
    (data / "official_orgs.json").write_text(
        json.dumps({"year": 2026, "generated": "2026-10-23", "organizations": orgs})
    )
    (data / "org_signals.json").write_text(json.dumps({"organizations": {}}))
    (data / "org_history.json").write_text(
        json.dumps(
            {"organizations": {"Ampersand & <Co>": {"years": {"2025": {"num_projects": 2}}}}}
        )
    )
    out = tmp_path / "site"
    assert build(out, data) == ["ampersand-co"]
    page = (out / "orgs/ampersand-co/index.html").read_text(encoding="utf-8")
    assert "Ampersand &amp; &lt;Co&gt;" in page
    assert 'href="https://example.org/ideas?a=1&amp;b=2"' in page
    assert "In GSoC since 2025, 1 year." in page
    assert not (tmp_path / "escapee").exists()


def test_ideas_line_matches_the_cli_evidence_wording() -> None:
    ideas = {"count": 6, "difficulty": {"easy": 4, "medium": 2}, "size": {"small": 3}, "mentors": 1}
    assert ideas_line(ideas, 2026) == (
        "6 ideas on its 2026 ideas page; of the 6 that state a difficulty: 4 easy, 2 medium. "
        "Sizes: 3 small. 1 mentor named."
    )
    assert ideas_line({}, 2026).startswith("Its ideas page could not be split")
