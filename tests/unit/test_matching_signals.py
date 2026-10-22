"""Building the shipped evidence file: credentials stay on GitHub, failures keep old data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc import config
from git_into_gsoc.matching.signals import build_signals, keep_previous

PAGE = """# GSoC 2026 ideas

## Accessible charts

Difficulty: easy
Size: small (90 hours)
Skills: JavaScript, D3
Mentors: Ana Lima

## Faster parser

Difficulty: hard
Skills: Rust
"""


def test_failed_pages_and_listings_keep_last_runs_evidence() -> None:
    previous = {
        "a": {"ideas": {"count": 4, "layout": "headings"}, "github": {"active_repos": 3}},
        "b": {"ideas": {"count": 2, "layout": "headings"}},
    }
    fresh = {
        "a": {"ideas": {"count": 0, "layout": "unreachable"}},  # page down, listing failed
        "b": {"ideas": {"count": 5, "layout": "headings"}},  # a real change wins
        "c": {"ideas": {"count": 0, "layout": "error"}},  # new organization, nothing to keep
    }
    merged = keep_previous(fresh, previous)
    assert merged["a"] == previous["a"]
    assert merged["b"]["ideas"]["count"] == 5
    assert merged["c"] == fresh["c"]


def test_a_page_that_suddenly_reads_empty_keeps_its_ideas_unless_it_moved() -> None:
    # On GitHub's runners BRL-CAD's page read as 0 ideas, where it had 32 the day before.
    url = "https://brlcad.org/wiki/Google_Summer_of_Code/Project_Ideas"
    previous = {"brl-cad": {"ideas": {"url": url, "count": 32, "layout": "headings"}}}
    stub = {"brl-cad": {"ideas": {"url": url, "count": 0, "layout": "unstructured"}}}
    assert keep_previous(stub, previous)["brl-cad"] == previous["brl-cad"]
    moved = {"brl-cad": {"ideas": {"url": url + "_2027", "count": 0, "layout": "unstructured"}}}
    assert keep_previous(moved, previous)["brl-cad"] == moved["brl-cad"]


@respx.mock
def test_ideas_pages_get_no_github_token_and_listings_do(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIG_GITHUB_TOKEN", "ghp_example")
    config.get_settings.cache_clear()
    from git_into_gsoc.service import GSoCToolkit

    pushed = datetime.now(UTC).isoformat()
    page = respx.get("https://example.org/gsoc/ideas").mock(
        return_value=httpx.Response(200, text=PAGE, headers={"content-type": "text/markdown"})
    )
    listing = respx.get("https://api.github.com/orgs/example/repos").mock(
        return_value=httpx.Response(
            200, json=[{"language": "JavaScript", "pushed_at": pushed, "topics": ["charts"]}]
        )
    )
    respx.get("https://api.github.com/orgs/broken/repos").mock(return_value=httpx.Response(500))
    # Posts about the coming GSoC: Example says it sits out; the search for Broken fails.
    sitting_out = {
        "items": [
            {
                "number": 7,
                "title": "No GSoC 2027 for Example",
                "body": "We will not take part in GSoC 2027.",
                "html_url": "https://github.com/example/site/issues/7",
                "repository_url": "https://api.github.com/repos/example/site",
                "state": "open",
                "created_at": "2026-10-01T00:00:00Z",
                "user": {"login": "maintainer"},
                "author_association": "MEMBER",
            }
        ]
    }

    def posts(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        if "org:fossasia" in query:
            # The canary: one label finds 5, the label OR another finds 7.
            return httpx.Response(
                200, json={"total_count": 7 if " OR " in query else 5, "items": []}
            )
        if "org:broken" in query:
            return httpx.Response(500)
        return httpx.Response(200, json=sitting_out if "org:example" in query else {"items": []})

    respx.get("https://api.github.com/search/issues").mock(side_effect=posts)
    official: list[dict[str, Any]] = [
        {
            "slug": "example",
            "name": "Example",
            "ideas_link": "https://example.org/gsoc/ideas",
            "source_code": "https://github.com/example",
        },
        {"slug": "broken", "name": "Broken", "source_code": "https://github.com/broken"},
    ]
    previous = {
        "broken": {
            "github": {"active_repos": 7, "languages": {"C": 7}},
            "participation": {"status": "undecided", "url": "https://x/1", "year": 2027},
        }
    }
    signals = build_signals(official, GSoCToolkit(), previous=previous)

    assert page.called and listing.called
    assert "authorization" not in {k.lower() for k in page.calls.last.request.headers}
    assert listing.calls.last.request.headers["authorization"] == "Bearer ghp_example"
    ideas = signals["example"]["ideas"]
    assert ideas["count"] == 2 and ideas["difficulty"] == {"easy": 1, "hard": 1}
    assert signals["example"]["github"]["languages"] == {"JavaScript": 1}
    assert signals["broken"]["github"] == previous["broken"]["github"]  # kept, not wiped
    said = signals["example"]["participation"]
    assert said["status"] == "not_taking_part" and said["year"] == 2027
    assert said["url"] == "https://github.com/example/site/issues/7"
    # The search for Broken failed, so last month's answer stands.
    assert signals["broken"]["participation"] == previous["broken"]["participation"]
    assert "_participation_failed" not in signals["broken"]


def test_a_failed_beginner_label_count_keeps_last_months_figure() -> None:
    previous = {"a": {"github": {"active_repos": 3, "beginner_issues_year": 9}}}
    fresh = {"a": {"github": {"active_repos": 4}}}  # the listing worked, the search did not
    merged = keep_previous(fresh, previous)
    assert merged["a"]["github"] == {"active_repos": 4, "beginner_issues_year": 9}


def test_a_statement_not_found_again_stays_with_its_old_date() -> None:
    said = {"status": "reported", "year": 2027, "checked": "2026-10-22", "url": "https://x/1"}
    previous = {"sympy": {"participation": said}}
    fresh = {"sympy": {"github": {"active_repos": 3}}}  # the refresh found nothing this time
    assert keep_previous(fresh, previous)["sympy"]["participation"] == said
    newer = {"status": "posted", "year": 2027, "checked": "2026-11-02", "url": "https://x/2"}
    replaced = keep_previous({"sympy": {"participation": newer}}, previous)
    assert replaced["sympy"]["participation"] == newer


def test_a_canary_decides_whether_or_group_searches_can_be_trusted() -> None:
    from types import SimpleNamespace

    from git_into_gsoc.matching.signals import search_trustworthy

    def toolkit(alone: int | None, either: int | None) -> SimpleNamespace:
        def opened(owners: list[str], *, since: str, labels: list[str]) -> int | None:
            return either if len(labels) > 1 else alone

        return SimpleNamespace(github=SimpleNamespace(beginner_issues_opened=opened))

    previous = {"big": {"github": {"owners": ["fossasia"], "beginner_issues_year": 100}}}
    assert search_trustworthy(toolkit(80, 95), previous)  # OR finds at least as many
    assert search_trustworthy(toolkit(1864, 1862), previous)  # approximate totals
    assert not search_trustworthy(toolkit(80, 0), previous)  # the 2026-10-22 failure
    assert not search_trustworthy(toolkit(80, 12), previous)  # fewer: the OR is broken
    assert not search_trustworthy(toolkit(None, 95), previous)  # a failed search
    assert not search_trustworthy(toolkit(0, 0), previous)  # nothing to compare


def test_a_failed_canary_keeps_last_months_counts_and_statements() -> None:
    from git_into_gsoc.matching.signals import _github_for

    class GitHub:
        calls = 0

        def list_owner_repos(self, owner: str) -> list[dict[str, Any]]:
            return []

        def beginner_issues_opened(self, *a: Any, **k: Any) -> int:
            GitHub.calls += 1
            return 0

    from types import SimpleNamespace

    toolkit = SimpleNamespace(github=GitHub())
    summary = _github_for(toolkit, ["lab"], datetime.now(UTC), searches=False)
    assert summary is not None and "beginner_issues_year" not in summary
    assert GitHub.calls == 0  # no search when the canary failed
    previous = {
        "lab": {"github": {"beginner_issues_year": 9}, "participation": {"status": "posted"}}
    }
    fresh = {"lab": {"github": summary, "_participation_failed": True}}
    merged = keep_previous(fresh, previous)["lab"]
    assert (
        merged["github"]["beginner_issues_year"] == 9
        and merged["participation"]["status"] == "posted"
    )


def test_competencies_in_a_skills_field_are_not_the_project_subject() -> None:
    # Oppia lists what a contributor does ("Debug; fix CI failures", "Write Python code
    # with unit tests"); read as subjects, developer tools landed in 10 of its 11 ideas.
    from git_into_gsoc.matching.ideas import skill_concepts
    from git_into_gsoc.matching.signals import summarize_ideas

    assert skill_concepts("Debug; fix CI failures; flakes") == []
    assert skill_concepts("Write Python code with unit tests") == ["python"]
    assert skill_concepts("Build an IDE plugin") == ["developer tools"]
    assert skill_concepts("CI/CD pipelines") == ["devops"]
    # What a testing project works on is still its subject, and nothing new appears.
    assert "developer tools" in skill_concepts("Python, testing")
    assert skill_concepts("test frameworks") == ["developer tools"]
    assert skill_concepts("test automation") == ["developer tools"]
    # InVesalius asks for "A source code editor" in all 9 ideas: a tool to have, not
    # the subject. Building a debugger, an editor plugin, or a review tool is one.
    assert skill_concepts("A source code editor") == []
    assert skill_concepts("Mac OS installed. A source code editor") == []
    assert skill_concepts("Build a debugger UI")[0] == "developer tools"
    assert skill_concepts("Build a code editor plugin") == ["developer tools"]
    assert skill_concepts("a code review tool") == ["developer tools"]
    assert skill_concepts("Debugging skills") == []
    summary = summarize_ideas(
        [{"title": "Web user feedback", "skills": ["Debug", "Write Python code with unit tests"]}],
        layout="headings",
        url="https://x",
    )
    assert "developer tools" not in summary["ideas"][0].get("k", [])


def test_stated_hours_reach_the_time_fit() -> None:
    # FreeBSD's "500 hours" read as large, then checked as a 350-hour project; at 20 hours
    # a week (440 hours over the longest coding period) it fit when it does not.
    from git_into_gsoc.matching.ideas import fit_idea
    from git_into_gsoc.matching.profile import build_profile
    from git_into_gsoc.matching.signals import summarize_ideas

    summary = summarize_ideas(
        [
            {"title": "PJDFSTest rewrite", "size": "large", "hours": 500, "skills": ["C"]},
            {"title": "Docs", "size": "medium", "hours": 175, "skills": ["Python"]},
        ],
        layout="headings",
        url="https://x",
    )
    first, second = summary["ideas"]
    assert (first["s"], first["h"]) == ("large", 500)
    assert "h" not in second  # the size's own hours add nothing
    person = build_profile(technologies=["c"], hours_per_week=20)
    stated = fit_idea(person, skill_keys=["c"], domain_keys=[], size="large", hours=500)
    usual = fit_idea(person, skill_keys=["c"], domain_keys=[], size="large")
    assert stated.too_big and "large (500 hours)" in stated.notes
    assert not usual.too_big
