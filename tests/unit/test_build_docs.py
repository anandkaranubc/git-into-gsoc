"""The docs are rendered onto the site at deploy time, so every page must exist,
every link written for GitHub must still resolve, and the sitemap must list them."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HREF = re.compile(r'href="([^"#]*)(?:#([^"]*))?"')


def _build(out: Path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_docs.py"), "--out", str(out)], check=True
    )


def _page_for(source: Path) -> Path:
    rel = source.relative_to(ROOT).with_suffix("")
    return rel.parent if rel.name == "README" else rel


def test_every_docs_page_is_rendered_with_its_links_and_anchors(tmp_path: Path) -> None:
    _build(tmp_path)
    for source in (ROOT / "docs").rglob("*.md"):
        assert (tmp_path / _page_for(source) / "index.html").is_file()
    pages = list((tmp_path / "docs").rglob("index.html"))
    for page in [*pages, ROOT / "site" / "index.html"]:
        text = page.read_text(encoding="utf-8")
        origin = page.parent if page.is_relative_to(tmp_path) else tmp_path
        for href, fragment in HREF.findall(text):
            if "docs/" not in href or href.startswith("http"):
                continue
            target = (origin / href).resolve() / "index.html"
            assert target.is_file(), f"{page}: {href}"
            if fragment:
                assert f'id="{fragment}"' in target.read_text(encoding="utf-8"), (
                    f"{page}: #{fragment}"
                )
        # Every relative Markdown link was rewritten to a page.
        assert not re.search(r'href="[^"h][^"]*\.md[#"]', text), page
        # A two-space nested list and a fenced block inside a list item once rendered
        # as literal "- " text and inline code; GitHub renders both as structure.
        assert "<p>- " not in text and "<code>json" not in text, page
    guide = (tmp_path / "docs/guide/01-understand-gsoc/index.html").read_text(encoding="utf-8")
    assert "<title>Understand GSoC | git into gsoc</title>" in guide
    assert 'rel="canonical" href="https://gitintogsoc.me/docs/guide/01-understand-gsoc/"' in guide
    first_paragraph = (
        (ROOT / "docs/guide/01-understand-gsoc.md").read_text("utf-8").split("\n\n")[1]
    )
    assert f'name="description" content="{first_paragraph.replace("**", "")[:40]}' in guide
    assert '"@type": "BreadcrumbList"' in guide


def test_docs_pages_join_the_sitemap_once(tmp_path: Path) -> None:
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://gitintogsoc.me/</loc></url></urlset>\n",
        encoding="utf-8",
    )
    _build(tmp_path)
    _build(tmp_path)
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<loc>https://gitintogsoc.me/</loc>") == 1
    assert sitemap.count("<loc>https://gitintogsoc.me/docs/</loc>") == 1
    assert sitemap.count("<loc>") == 1 + len(list((ROOT / "docs").rglob("*.md")))
    assert sitemap.rstrip().endswith("</urlset>")
