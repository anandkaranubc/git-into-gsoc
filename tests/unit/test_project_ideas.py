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


def test_umbrella_links_index_without_subheadings() -> None:
    doc = extract_ideas(markdown_to_lines(_read("umbrella_links_index.md")), source_url="https://x")
    assert doc.layout == "index"
    assert doc.ideas == []
    titles = [p["title"] for p in doc.sub_pages]
    assert titles[:3] == ["Alpha Lab", "Beta Toolkit", "Gamma Solver"]
    assert all(p["url"].startswith("https://") for p in doc.sub_pages)
    assert not any("old/project" in p["url"] for p in doc.sub_pages)
    # Links to a ".ai" domain and a "Proposed-Projects" page are not a policy.
    assert doc.ai_policy == []


def test_ai_policy_ignores_links_and_survives_wrapped_lines() -> None:
    wrapped = (
        "Use of AI tools such as ChatGPT must be\n"
        "disclosed in your proposal.\n"
        "- [Solver](https://solver.ai/dev/#gsoc)\n"
        "- [Stats](https://github.com/x/y/wiki/GSOC-2026-Proposed-Projects)\n"
    )
    assert ai_policy_sentences(wrapped) == [
        "Use of AI tools such as ChatGPT must be disclosed in your proposal."
    ]


def test_html_without_head_close_or_nav_close_is_still_read() -> None:
    doc = extract_ideas(html_to_lines(_read("no_head_close.html")), source_url="https://x")
    assert doc.layout == "headings"
    assert [i.title for i in doc.ideas] == ["Faster indexer", "Terminal interface"]
    assert doc.ideas[0].skills == ["Python", "SQL"] and doc.ideas[0].hours == 175
    assert not any("Home" in line for line in html_to_lines(_read("no_head_close.html")))


def test_restructuredtext_underlines_become_headings() -> None:
    lines = markdown_to_lines(_read("rst_underlines.rst"))
    assert lines[0] == "# Ideas List"
    assert "## Projects Ideas" in lines and "### Mobile version (350hrs)" in lines
    assert not any(line.startswith("..") for line in lines)
    doc = extract_ideas(lines, source_url="https://x")
    assert doc.layout == "headings"
    assert [i.title for i in doc.ideas] == [
        "Mobile version (350hrs)",
        "Exporter for a new format (175hrs)",
    ]
    assert doc.ideas[0].hours == 350 and doc.ideas[1].difficulty == "easy"
    assert "C++" in doc.ideas[0].skills


def test_rules_and_front_matter_are_not_headings() -> None:
    text = "---\ntitle: Ideas\n---\n\nIntro paragraph.\n\n---\n\n## Real heading\nBody\n"
    lines = markdown_to_lines(text)
    assert lines == ["Intro paragraph.", "## Real heading", "Body"]


def test_styled_div_titles_and_keyword_labels_are_read() -> None:
    doc = extract_ideas(html_to_lines(_read("div_titles.html")), source_url="https://x")
    assert doc.layout == "headings"
    assert [i.title for i in doc.ideas] == [
        "Improving the test runner",
        "Better documentation generator",
    ]
    first = doc.ideas[0]
    assert first.mentors == ["Mentor One"] and first.difficulty == "medium"
    assert first.description.startswith("Make the test runner faster")
    assert doc.ideas[1].size == "large"


def test_prose_index_keeps_its_blocks_as_fallback_ideas() -> None:
    body = " ".join(["This idea needs a long explanation of the goal and the steps."] * 6)
    lines = ["# Projects"]
    for name in ("Alpha", "Beta", "Gamma"):
        lines += [
            f"### {name} project",
            body,
            f"See https://example.org/{name.lower()} for context.",
        ]
    doc = extract_ideas(lines, source_url="https://x")
    assert doc.layout == "index" and doc.ideas == []
    titles = [i.title for i in doc.fallback_ideas]
    assert titles == ["Alpha project", "Beta project", "Gamma project"]
    assert all(i.confidence == "low" for i in doc.fallback_ideas)
    short = ["# Projects"]
    for name in ("Alpha", "Beta", "Gamma"):
        short += [f"### {name}", f"Ideas: https://example.org/{name.lower()}/ideas"]
    short_doc = extract_ideas(short, source_url="https://x")
    assert short_doc.layout == "index" and short_doc.fallback_ideas == []


def test_getting_started_page_with_a_stray_label_is_still_an_index() -> None:
    lines = [
        "# Summer of Code - Getting Started",
        "## What you should know about Octave",
        "Read the manual first (https://example.org/manual).",
        "## How do we judge your application?",
        "Mentors: see the mentor guide (https://example.org/guide) for what we look for.",
        "## Suggested projects",
        "The list of projects lives at https://example.org/wiki/Project_Ideas for this year.",
        "## See also",
        "Last year's ideas (https://example.org/wiki/Project_Ideas_2025).",
    ]
    doc = extract_ideas(lines, source_url="https://x")
    assert doc.layout == "index" and doc.ideas == []
    assert any(p["url"] == "https://example.org/wiki/Project_Ideas" for p in doc.sub_pages)
    assert not any(p["url"].endswith("/guide") for p in doc.sub_pages)


def test_anchor_tags_are_stripped_from_titles() -> None:
    lines = [
        "# Ideas",
        "## <a name='project-1.1'></a> Project 1.1: Faster parser",
        "Mentors: Ada",
        "Skills: C++",
        "Difficulty: medium",
        "## <a name='project-1.2'></a> Project 1.2: New backend",
        "Mentors: Grace",
        "Skills: Rust",
        "Difficulty: hard",
    ]
    doc = extract_ideas(lines, source_url="https://x")
    assert [i.title for i in doc.ideas] == [
        "Project 1.1: Faster parser",
        "Project 1.2: New backend",
    ]


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


def test_label_headings_under_each_idea_do_not_win_level_choice() -> None:
    doc = extract_ideas(
        markdown_to_lines(_read("wiki_extra_subsections.md")), source_url="https://x"
    )
    assert [i.title for i in doc.ideas] == [
        "Project 1: Dashboard for tracking simulation progress",
        "Project 2: Lazy trajectory loading",
    ]
    first = doc.ideas[0]
    assert first.hours == 175 and first.difficulty == "easy"
    assert first.links == ["https://github.com/example/lib/issues/5"]
    assert first.description.startswith("A dashboard")
    assert first.confidence == "high"
    # policy comes from page text outside idea blocks, not from idea bodies
    assert doc.ai_policy and "generated by AI" in doc.ai_policy[0]


def test_bullet_sub_items_and_template_comments() -> None:
    doc = extract_ideas(markdown_to_lines(_read("bullet_comments.md")), source_url="https://x")
    idea = doc.ideas[0]
    assert idea.title == "Reactive Agents with Drasi"
    assert idea.skills == ["Python", "Kubernetes & Docker"]
    assert idea.mentors == ["Aman Example (@aman, aman@example.org)", "Zhao Example (@zhao)"]
    assert not any("For GSoC" in m for m in idea.mentors)
    assert idea.expected_outcome.startswith("Router Reaction")
    assert doc.ai_policy == []


def test_prose_index_is_detected_as_index() -> None:
    doc = extract_ideas(html_to_lines(_read("prose_index.html")), source_url="https://x")
    assert doc.layout == "index"
    assert doc.ideas == []
    titles = [p["title"] for p in doc.sub_pages]
    assert "pocketpy" in titles and "DIPY" in titles
    assert "Getting started" not in titles


def test_values_drop_markdown_links_html_and_inline_template_notes() -> None:
    lines = markdown_to_lines(
        "## Idea A\n- Mentor(s): #For GSoC, two mentors are required.\n"
        "  - [@alice](https://github.com/alice)\n- Skills: Python, Type Systems<br>\n"
        "- Expected project size: 175h\n## Idea B\n- Skills: Go\n- Expected project size: 90h\n"
    )
    doc = extract_ideas(lines, source_url="https://x")
    idea = doc.ideas[0]
    assert idea.mentors == ["@alice"]
    assert idea.skills == ["Python", "Type Systems"]
