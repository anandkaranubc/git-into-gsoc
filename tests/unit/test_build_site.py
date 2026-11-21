"""The organization explorer is generated from the bundled snapshot, so it must
cover every official organization and never let data text break the HTML."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_site import ANALYTICS, PLAN_PATH, PLAN_YEAR, build, ideas_line, related_orgs  # noqa: E402


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
    assert sitemap.count("<loc>") == len(slugs) + 5


def test_every_page_carries_the_same_page_view_counter(tmp_path: Path) -> None:
    build(tmp_path)
    pages = [tmp_path / "orgs/index.html", tmp_path / "start/index.html"]
    pages += [ROOT / "site" / name for name in ("index.html", "brand.html", "404.html")]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert text.count(ANALYTICS) == 1, page
        assert text.count('track.js" defer') == 1, page


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
            "website_url": "javascript:alert(1)",
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
    assert 'href="https://example.org/ideas?a=1&amp;b=2" data-out="org-link/ideas"' in page
    # A link from the data is only a link when it is a web address.
    assert "javascript:alert(1)" in page and 'href="javascript:' not in page
    assert "1 year in our archive, from 2025." in page
    assert not (tmp_path / "escapee").exists()


def test_ideas_line_matches_the_cli_evidence_wording() -> None:
    ideas = {"count": 6, "difficulty": {"easy": 4, "medium": 2}, "size": {"small": 3}, "mentors": 1}
    assert ideas_line(ideas, 2026) == (
        "6 ideas on its 2026 ideas page; of the 6 that state a difficulty: 4 easy, 2 medium. "
        "Sizes: 3 small. 1 mentor named."
    )
    assert ideas_line({}, 2026).startswith("Its ideas page could not be split")


def test_organization_pages_have_their_own_snippet_breadcrumbs_and_neighbours(
    tmp_path: Path,
) -> None:
    build(tmp_path)
    page = (tmp_path / "orgs/sympy/index.html").read_text(encoding="utf-8")
    title = page.split("<title>")[1].split("</title>")[0]
    description = page.split('name="description" content="')[1].split('"')[0]
    assert title.startswith("SymPy GSoC ")
    assert description.startswith("SymPy in Google Summer of Code ")
    assert len(description) <= 160
    assert "BreadcrumbList" in page
    assert page.count('href="../') >= 5  # the way back plus similar organizations
    descriptions = {
        (p / "index.html").read_text(encoding="utf-8").split('name="description" content="')[1]
        for p in (tmp_path / "orgs").iterdir()
        if p.is_dir()
    }
    assert len(descriptions) > 150  # one snippet per organization, not one for all


def test_related_orgs_skip_the_organization_itself_and_rank_rare_tags_first() -> None:
    orgs = [
        {"slug": "a", "name": "A", "tech_tags": ["python", "rust"]},
        {"slug": "b", "name": "B", "tech_tags": ["python"]},
        {"slug": "c", "name": "C", "tech_tags": ["rust"]},
        {"slug": "d", "name": "D", "tech_tags": ["go"]},
        {"slug": "e", "name": "E", "tech_tags": ["python"]},
    ]
    near = related_orgs(orgs)
    assert [o["slug"] for o in near["a"]] == ["c", "b", "e"]  # rust is rarer than python
    assert near["d"] == []


def test_plan_page_labels_estimates_and_is_linked_from_every_page(tmp_path: Path) -> None:
    build(tmp_path)
    page = (tmp_path / PLAN_PATH / "index.html").read_text(encoding="utf-8")
    assert f"Google Summer of Code {PLAN_YEAR}" in page
    assert "Give or take" in page or "official" in page
    assert "developers.google.com/open-source/gsoc/timeline" in page
    description = page.split('name="description" content="')[1].split('"')[0]
    assert len(description) <= 160
    assert "\u2014" not in page  # no em dashes
    for html in (tmp_path / "orgs/sympy/index.html", ROOT / "site/index.html"):
        assert f'gsoc-{PLAN_YEAR}/"' in html.read_text(encoding="utf-8")


def test_an_organization_page_quotes_its_ai_rules_escaped(tmp_path: Path) -> None:
    # A maintainer asked "is your page right?" must see what applicants are told.
    data = tmp_path / "data"
    data.mkdir()
    org = {"name": "Jenkins", "slug": "jenkins", "categories": [], "tech_tags": []}
    (data / "official_orgs.json").write_text(
        json.dumps({"year": 2026, "generated": "2026-11-21", "organizations": [org]})
    )
    rule = "You may not paste <AI> code."
    ideas = {
        "url": "https://x.org/ideas",
        "count": 0,
        "ai": [rule],
        "ai_url": "https://x.org/ai-policy",
    }
    (data / "org_signals.json").write_text(
        json.dumps({"organizations": {"jenkins": {"ideas": ideas}}})
    )
    (data / "org_history.json").write_text(json.dumps({"organizations": {}}))
    out = tmp_path / "site"
    build(out, data)
    page = (out / "orgs/jenkins/index.html").read_text(encoding="utf-8")
    assert "You may not paste &lt;AI&gt; code." in page
    assert 'href="https://x.org/ai-policy" data-out="org-link/ai-policy"' in page
