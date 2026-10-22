"""Keep project text readable for first-time contributors.

CONTRIBUTING.md ("Writing docs") states the rules. This file checks the parts a
script can check: plain punctuation (no em dashes), no filler or sales words,
relative links that resolve, and every page reachable from an index, so a new
page cannot be orphaned and an old one cannot be deleted while something still
links to it. Every directory with text for people is listed here, so the check
protects all of it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKED = [
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".env.example",
    ".github",
    "docs",
    "examples",
    "skills",
    "pyproject.toml",
]
SUFFIXES = {".md", ".yml", ".yaml", ".toml", ".example", ".sh", ".json"}

# Filler and sales words that say nothing to a beginner. The list is short on
# purpose: each entry is a word the docs never need, not a word to ration.
AVOID = (
    "delve",
    "leverage",
    "seamless",
    "cutting-edge",
    "game-changing",
    "supercharge",
    "state-of-the-art",
    "it is worth noting",
    "it's worth noting",
    "in today's",
)

# Pages from which every other page must be reachable by relative links.
INDEXES = ("README.md", "CONTRIBUTING.md", "docs/README.md", "skills/git-into-gsoc/SKILL.md")
# Trees whose Markdown pages must all be reachable. CHANGELOG.md is generated,
# .github templates are shown by GitHub itself, and brand/ and site/ have their
# own entry points.
REACHABLE_TREES = ("docs", "examples", "skills")

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def _text_files() -> list[Path]:
    files: list[Path] = []
    for entry in CHECKED:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.suffix in SUFFIXES)
    return files


def _markdown_files() -> list[Path]:
    return [p for p in _text_files() if p.suffix == ".md"]


def _prose_lines(path: Path) -> list[tuple[int, str]]:
    """Lines outside fenced code blocks, numbered from 1."""
    lines: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((number, line))
    return lines


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    found: set[str] = set()
    for _, line in _prose_lines(path):
        match = HEADING.match(line)
        if match:
            found.add(_slug(match.group(1)))
    return found


def _relative_links(path: Path) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    for number, line in _prose_lines(path):
        for target in LINK.findall(line):
            if not re.match(r"(?:https?:|mailto:)", target):
                links.append((number, target))
    return links


def test_no_em_dashes_in_project_text() -> None:
    offenders = []
    for path in _text_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "—" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        "Em dashes found; use a comma, colon, period, or parentheses instead:\n  "
        + "\n  ".join(offenders)
    )


def test_no_filler_words_in_docs() -> None:
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in AVOID) + r")\b", re.IGNORECASE)
    offenders = []
    for path in _markdown_files():
        if path.name == "CHANGELOG.md":
            continue
        for number, line in _prose_lines(path):
            match = pattern.search(line)
            if match:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {match.group(0)!r}")
    assert not offenders, (
        "Filler words found; say the plain thing instead (CONTRIBUTING.md, Writing docs):\n  "
        + "\n  ".join(offenders)
    )


def test_relative_links_and_anchors_resolve() -> None:
    offenders = []
    for path in _markdown_files():
        for number, target in _relative_links(path):
            file_part, _, fragment = target.partition("#")
            dest = path if not file_part else (path.parent / file_part).resolve()
            where = f"{path.relative_to(ROOT)}:{number}"
            if not dest.exists():
                offenders.append(f"{where}: {target} does not exist")
            elif fragment and dest.suffix == ".md" and fragment not in _anchors(dest):
                offenders.append(f"{where}: no heading for #{fragment} in {dest.relative_to(ROOT)}")
    assert not offenders, "Broken links:\n  " + "\n  ".join(offenders)


def test_every_page_is_reachable_from_an_index() -> None:
    seen: set[Path] = set()
    queue = [ROOT / index for index in INDEXES]
    while queue:
        page = queue.pop()
        if page in seen or not page.is_file():
            continue
        seen.add(page)
        for _, target in _relative_links(page):
            file_part = target.partition("#")[0]
            if file_part:
                dest = (page.parent / file_part).resolve()
                if dest.suffix == ".md" and dest.is_file():
                    queue.append(dest)
    pages = [
        p for tree in REACHABLE_TREES for p in sorted((ROOT / tree).rglob("*.md")) if p.is_file()
    ]
    orphans = [str(p.relative_to(ROOT)) for p in pages if p not in seen]
    assert not orphans, (
        "Pages no index or page links to; add a link from docs/README.md or delete the page:\n  "
        + "\n  ".join(orphans)
    )
