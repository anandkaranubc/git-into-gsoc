"""Contribution evidence: counts, evidence lines, and gaps from a person's activity searches."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import respx

from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.evidence import summarize_activity

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def _iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _item(
    number: int,
    *,
    repo: str = "acme/lib",
    pr: bool = False,
    state: str = "open",
    merged: bool = False,
    author: str = "alice",
    days_ago: int = 10,
    comments: int = 1,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": number,
        "number": number,
        "title": f"Item {number}",
        "html_url": f"https://github.com/{repo}/{'pull' if pr else 'issues'}/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "state": state,
        "user": {"login": author},
        "created_at": _iso(days_ago),
        "updated_at": _iso(days_ago - 1),
        "closed_at": _iso(days_ago - 2) if state == "closed" else None,
        "comments": comments,
        "labels": [{"name": "documentation"}],
    }
    if pr:
        item["pull_request"] = {"merged_at": _iso(days_ago - 2) if merged else None}
    return item


def test_summarize_activity_counts_and_evidence_lines() -> None:
    prs = [
        _item(1, pr=True, state="closed", merged=True, days_ago=40),
        _item(2, pr=True, state="open", days_ago=5),
        _item(3, pr=True, state="closed", merged=False, days_ago=20),
    ]
    issues = [_item(10, days_ago=30)]
    joined = [_item(20, author="bob", comments=4, days_ago=12)]
    reviews = [_item(30, pr=True, author="carol", days_ago=8)]
    summary = summarize_activity(
        "alice", prs=prs, issues=issues, discussions=joined, reviews=reviews, now=NOW
    )
    counts = summary["counts"]
    assert counts["prs_merged"] == 1
    assert counts["prs_open"] == 1
    assert counts["prs_closed_unmerged"] == 1
    assert counts["issues_opened"] == 1
    assert counts["threads_joined"] == 1
    assert counts["reviews_given"] == 1
    assert summary["first_activity_days_ago"] == 40
    assert summary["repos"] == ["acme/lib"]
    merged = next(p for p in summary["pull_requests"] if p["number"] == 1)
    assert merged["state"] == "merged"
    assert any("acme/lib#1" in line and "merged" in line for line in summary["evidence_markdown"])
    assert summary["strength"] in {"strong", "developing", "starting", "none"}


def test_summarize_activity_flags_gaps_without_merged_work() -> None:
    summary = summarize_activity(
        "alice", prs=[_item(2, pr=True)], issues=[], discussions=[], reviews=[], now=NOW
    )
    assert summary["counts"]["prs_merged"] == 0
    assert summary["strength"] == "starting"
    assert any("merged" in gap.lower() for gap in summary["gaps"])


def test_summarize_activity_empty() -> None:
    summary = summarize_activity("alice", prs=[], issues=[], discussions=[], reviews=[], now=NOW)
    assert summary["strength"] == "none"
    assert summary["evidence_markdown"] == []
    assert summary["first_activity_days_ago"] is None


@respx.mock
def test_user_activity_builds_scoped_queries() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        if "is:pr" in q and "author:alice" in q:
            items = [_item(1, pr=True, state="closed", merged=True)]
        elif "is:issue" in q and "author:alice" in q:
            items = [_item(2)]
        elif "commenter:alice" in q:
            items = [_item(3, author="bob")]
        elif "reviewed-by:alice" in q:
            items = [_item(4, pr=True, author="bob")]
        else:  # pragma: no cover - unexpected query
            return httpx.Response(422, json={"message": f"unexpected {q}"})
        return httpx.Response(200, json={"items": items})

    search = respx.get("https://api.github.com/search/issues").mock(side_effect=respond)
    activity = GitHubClient().user_activity("alice", owners=["acme", "acme-labs"])
    queries = [c.request.url.params["q"] for c in search.calls]
    assert len(queries) == 4
    assert all("org:acme" in q and "org:acme-labs" in q for q in queries)
    assert activity["counts"]["prs_merged"] == 1
    assert activity["counts"]["issues_opened"] == 1
    assert activity["counts"]["threads_joined"] == 1
    assert activity["counts"]["reviews_given"] == 1


@respx.mock
def test_user_activity_repo_scope_and_self_comments_excluded() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        assert "repo:acme/lib" in q
        if "commenter:alice" in q:
            assert "-author:alice" in q
        return httpx.Response(200, json={"items": []})

    respx.get("https://api.github.com/search/issues").mock(side_effect=respond)
    activity = GitHubClient().user_activity("alice", repo="acme/lib")
    assert activity["strength"] == "none"
