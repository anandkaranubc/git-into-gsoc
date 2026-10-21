from __future__ import annotations

from pathlib import Path

import httpx
import respx

from git_into_gsoc.gsoc.project_ideas import (
    ai_policy_sentences,
    extract_ideas,
    html_to_lines,
    ideas_document_url,
    markdown_to_lines,
    normalize_difficulty,
    normalize_size,
    rank_ideas,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ideas"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_wiki_headings_style_extracts_fields() -> None:
    doc = extract_ideas(markdown_to_lines(_read("wiki_headings.md")), source_url="https://x/ideas")
    titles = [i.title for i in doc.ideas]
    assert "Faster trajectory readers" in titles[0]
    assert "How to apply" not in " ".join(titles)
    first = doc.ideas[0]
    assert first.hours == 350 and first.size == "large"
    assert first.difficulty == "medium"
    assert "Python" in first.skills and "NumPy" in first.skills
    assert first.mentors == ["Alice Example (@alice)", "Bob Example"]
    assert "https://github.com/example/lib/issues/12" in first.links
    assert first.expected_outcome.startswith("A new reader class")
    assert first.confidence == "high"
    assert doc.ideas[1].difficulty == "easy" and doc.ideas[1].hours == 175
    draft = next(i for i in doc.ideas if "Hidden" in i.title)
    assert draft.confidence == "low"
    assert doc.layout == "headings"


def test_bullet_labels_style() -> None:
    doc = extract_ideas(markdown_to_lines(_read("bullet_labels.md")), source_url="https://x")
    assert [i.title for i in doc.ideas] == ["Add a scheduler plugin", "Improve the CLI help"]
    idea = doc.ideas[0]
    assert idea.hours == 350
    assert idea.skills == ["Go", "Kubernetes"]
    assert idea.mentors[0].startswith("Dana Example")
    assert idea.links == ["https://github.com/great/project/issues/99"]
    assert idea.description.startswith("Implement a pluggable scheduler")


def test_html_bold_labels_with_two_level_umbrella() -> None:
    lines = html_to_lines(_read("html_bold_labels.html"))
    assert not any("var a=1" in line for line in lines)
    doc = extract_ideas(lines, source_url="https://x")
    assert [i.title for i in doc.ideas] == [
        "Annotation sidebar redesign",
        "Faster search",
        "Widget gallery",
    ]
    assert doc.ideas[0].section == "Okular"
    assert doc.ideas[2].section == "Plasma"
    assert doc.ideas[0].difficulty == "hard" and doc.ideas[0].hours == 175
    assert doc.ideas[0].skills == ["C++", "Qt"]
    assert doc.ideas[0].mentors == ["Frank Example"]


def test_umbrella_index_reports_sub_pages_not_ideas() -> None:
    doc = extract_ideas(markdown_to_lines(_read("umbrella_index.md")), source_url="https://x")
    assert doc.ideas == []
    assert doc.layout == "index"
    urls = [p["url"] for p in doc.sub_pages]
    assert "https://alpha.example.org/gsoc/ideas" in urls
    assert "https://github.com/beta/beta/wiki/GSoC-2026-Ideas" in urls
    assert doc.sub_pages[0]["title"] == "Sub-project Alpha"


def test_ai_policy_sentences() -> None:
    text = _read("wiki_headings.md")
    found = ai_policy_sentences(text)
    assert found and "disclose" in found[0].lower()
    assert ai_policy_sentences("We build AI models for astronomy.") == []


def test_normalizers() -> None:
    assert normalize_size("350 hours") == ("large", 350)
    assert normalize_size("Medium (175h)") == ("medium", 175)
    assert normalize_size("small") == ("small", 90)
    assert normalize_size("~ 90 hrs") == ("small", 90)
    assert normalize_size("unknown") == (None, None)
    assert normalize_difficulty("Intermediate") == "medium"
    assert normalize_difficulty("Beginner-friendly") == "easy"
    assert normalize_difficulty("Advanced / Hard") == "hard"
    assert normalize_difficulty("") is None


def test_ideas_document_url_prefers_structured_forms() -> None:
    assert (
        ideas_document_url("https://docs.google.com/document/d/abc_1/edit#heading=h.x")
        == "https://docs.google.com/document/d/abc_1/export?format=html"
    )
    assert (
        ideas_document_url("https://docs.google.com/document/d/e/2PACX-xyz/pub")
        == "https://docs.google.com/document/d/e/2PACX-xyz/pub"
    )
    assert (
        ideas_document_url("https://github.com/org/repo/wiki/Ideas-2026")
        == "https://raw.githubusercontent.com/wiki/org/repo/Ideas-2026.md"
    )
    assert ideas_document_url("https://github.com/o/r/issues?q=label%3AGSoC") is None


def test_rank_ideas_by_skills_and_size() -> None:
    doc = extract_ideas(markdown_to_lines(_read("wiki_headings.md")), source_url="https://x")
    ranked = rank_ideas(doc.ideas, skills=["sphinx", "python"], size="medium", difficulty="easy")
    assert ranked[0].title.startswith("Project 2") or "gallery" in ranked[0].title.lower()
    assert ranked[0].match_reasons


@respx.mock
def test_fetch_google_doc_as_html() -> None:
    from git_into_gsoc.config import get_settings
    from git_into_gsoc.gsoc.project_ideas import fetch_ideas_document
    from git_into_gsoc.http_client import CachedHttpClient

    respx.get("https://docs.google.com/document/d/abc/export?format=html").mock(
        return_value=httpx.Response(200, text=_read("html_bold_labels.html"))
    )
    doc = fetch_ideas_document(
        CachedHttpClient(get_settings()), "https://docs.google.com/document/d/abc/edit", ttl=10
    )
    assert doc is not None and len(doc.ideas) == 3
    assert doc.fetched_url.endswith("format=html")


def test_issues_page_target() -> None:
    from git_into_gsoc.gsoc.project_ideas import issues_page_target

    assert issues_page_target("https://github.com/o/r/issues?q=is%3Aopen+label%3AGSoC") == (
        "o/r",
        "GSoC",
    )
    assert issues_page_target("https://github.com/o/r/issues?q=label%3A%22GSoC+2026%22") == (
        "o/r",
        "GSoC 2026",
    )
    assert issues_page_target("https://github.com/o/r/labels/gsoc-2026") == ("o/r", "gsoc-2026")
    assert issues_page_target("https://github.com/o/r/wiki/Ideas") is None
    assert issues_page_target("https://example.org/ideas") is None
