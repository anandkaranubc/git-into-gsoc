"""Render the Markdown docs as pages on the site.

    python3 scripts/build_docs.py              # writes site/docs/ and adds the pages to site/sitemap.xml
    python3 scripts/build_docs.py --out DIR    # writes somewhere else (tests)

docs/ stays the only copy of the text. This writes an HTML view of it at deploy time
so a search like "how to find GSoC organizations" can land on the guide itself: search
engines rarely rank a GitHub blob page, and the project site had no indexable text
beyond the home page. The Pages workflow runs this after build_site.py, and the output
is not committed.
"""

from __future__ import annotations

import argparse
import json
import re
from html import escape
from pathlib import Path

from build_site import FOOT, REPO_URL, SITE_URL, _head
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LINK = re.compile(r"(?<!!)\]\(([^)\s]+)\)")
# Markup to drop when a paragraph becomes a meta description: link text is kept.
INLINE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
SKIP_BLOCK = re.compile(r"^(?:#|\||```|>|[-*] |\d+\. )")
DESCRIPTION_CHARS = 155


def slugify(value: str) -> str:
    """GitHub's heading anchor, so links written for GitHub keep working on the site."""
    text = re.sub(r"[^\w\- ]", "", value.strip().lower())
    return text.replace(" ", "-")


def to_html(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Markdown to HTML by CommonMark rules with tables, as GitHub renders the docs.

    Also returns the page's second-level headings (anchor, text) for a table of contents.
    Python-Markdown was tried first and follows older rules: a two-space nested list
    flattened and a fenced block inside a list item became inline code.
    """
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(text)
    sections: list[tuple[str, str]] = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            children = tokens[i + 1].children or []
            # shortcut: no dedupe of repeated headings, add GitHub's -1 suffix if a page gets one
            heading = "".join(c.content for c in children)
            token.attrSet("id", slugify(heading))
            if token.tag == "h2":
                sections.append((slugify(heading), heading))
    return md.renderer.render(tokens, md.options, {}), sections


# A page with fewer sections than this reads faster without a table of contents.
TOC_MIN = 3


def toc(sections: list[tuple[str, str]]) -> str:
    if len(sections) < TOC_MIN:
        return ""
    items = "".join(f'<li><a href="#{escape(a)}">{escape(t)}</a></li>' for a, t in sections)
    return f'<nav class="toc" aria-label="On this page"><p>On this page</p><ol>{items}</ol></nav>\n'


def page_path(source: Path) -> str:
    """Site path for a docs file: docs/README.md -> docs/, docs/guide/x.md -> docs/guide/x/."""
    rel = source.relative_to(ROOT).with_suffix("")
    if rel.name == "README":
        rel = rel.parent
    return f"{rel.as_posix()}/"


def rewrite_links(text: str, source: Path, root: str) -> str:
    """Point relative links at the rendered page, or at GitHub for files outside docs/."""

    def replace(match: re.Match[str]) -> str:
        target = match.group(1)
        if re.match(r"(?:https?:|mailto:|#)", target):
            return match.group(0)
        file_part, _, fragment = target.partition("#")
        dest = (source.parent / file_part).resolve()
        if dest.suffix == ".md" and dest.is_relative_to(DOCS):
            href = root + page_path(dest)
        else:
            href = f"{REPO_URL}/blob/main/{dest.relative_to(ROOT).as_posix()}"
        return f"]({href}{'#' + fragment if fragment else ''})"

    return LINK.sub(replace, text)


def description(text: str) -> str:
    """The first prose paragraph, plain and cut to a search snippet at a word boundary."""
    for block in text.split("\n\n")[1:]:
        line = block.strip()
        if line and not SKIP_BLOCK.match(line):
            plain = (
                INLINE_LINK.sub(r"\1", line.replace("\n", " ")).replace("**", "").replace("`", "")
            )
            if len(plain) <= DESCRIPTION_CHARS:
                return plain
            return plain[:DESCRIPTION_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return ""


def render(source: Path) -> str:
    """One docs page as a full HTML document."""
    text = source.read_text(encoding="utf-8")
    heading = re.match(r"# (.+)", text)
    title = re.sub(r"^\d+\. ", "", heading.group(1) if heading else source.stem)
    path = page_path(source)
    root = "../" * path.count("/")
    body, sections = to_html(rewrite_links(text, source, root))
    crumbs = [("git into gsoc", SITE_URL), ("Guide", f"{SITE_URL}docs/")]
    if path != "docs/":
        crumbs.append((title, f"{SITE_URL}{path}"))
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs, 1)
        ],
    }
    trail = " / ".join(f'<a href="{escape(url)}">{escape(name)}</a>' for name, url in crumbs[:-1])
    source_rel = source.relative_to(ROOT).as_posix()
    return (
        _head(f"{title} | git into gsoc", description(text), root, path)
        + f'<script type="application/ld+json">{json.dumps(breadcrumbs)}</script>\n'
        + f'<div class="wrap doc-grid">\n{toc(sections)}<article class="doc">\n'
        + f'<nav class="crumbs" aria-label="Breadcrumb">{trail}</nav>\n'
        + body
        + f'\n<p class="fine">Source: <a href="{REPO_URL}/blob/main/{source_rel}">{source_rel}</a>'
        " on GitHub. Corrections are welcome.</p>\n</article>\n</div>\n" + FOOT
    )


def add_to_sitemap(sitemap: Path, paths: list[str]) -> None:
    """Append the docs pages to the sitemap build_site.py wrote, or start one."""
    urls = "".join(f"<url><loc>{escape(SITE_URL + p)}</loc></url>" for p in paths)
    if sitemap.is_file():
        text = sitemap.read_text(encoding="utf-8")
        if urls and urls[: urls.index("</url>") + 6] in text:
            return
        sitemap.write_text(text.replace("</urlset>", f"{urls}</urlset>"), encoding="utf-8")
    else:
        sitemap.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
            encoding="utf-8",
        )


def build(out: Path) -> list[str]:
    """Write every docs page under ``out`` and return their site paths."""
    paths = []
    for source in sorted(DOCS.rglob("*.md")):
        path = page_path(source)
        target = out / path / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(source), encoding="utf-8")
        paths.append(path)
    add_to_sitemap(out / "sitemap.xml", paths)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render docs/ as pages in the site folder.")
    parser.add_argument("--out", type=Path, default=ROOT / "site", help="site folder to write into")
    args = parser.parse_args(argv)
    paths = build(args.out)
    print(f"wrote {len(paths)} docs pages under {args.out / 'docs'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
