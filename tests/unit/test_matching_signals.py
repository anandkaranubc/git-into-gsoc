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
    official: list[dict[str, Any]] = [
        {
            "slug": "example",
            "name": "Example",
            "ideas_link": "https://example.org/gsoc/ideas",
            "source_code": "https://github.com/example",
        },
        {"slug": "broken", "name": "Broken", "source_code": "https://github.com/broken"},
    ]
    previous = {"broken": {"github": {"active_repos": 7, "languages": {"C": 7}}}}
    signals = build_signals(official, GSoCToolkit(), previous=previous)

    assert page.called and listing.called
    assert "authorization" not in {k.lower() for k in page.calls.last.request.headers}
    assert listing.calls.last.request.headers["authorization"] == "Bearer ghp_example"
    ideas = signals["example"]["ideas"]
    assert ideas["count"] == 2 and ideas["difficulty"] == {"easy": 1, "hard": 1}
    assert signals["example"]["github"]["languages"] == {"JavaScript": 1}
    assert signals["broken"]["github"] == previous["broken"]["github"]  # kept, not wiped
