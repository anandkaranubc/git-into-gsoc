"""Committer statistics from ecosyste.ms: newcomers and the bus factor."""

from __future__ import annotations

import httpx
import respx

from git_into_gsoc.github.ecosystems import fetch_commit_stats, summarize
from git_into_gsoc.http_client import CachedHttpClient

API = "https://commits.ecosyste.ms/api/v1"


def _payload() -> dict[str, object]:
    return {
        "past_year_total_commits": 120,
        "last_synced_at": "2026-10-20T06:32:19Z",
        "past_year_committers": [
            {"name": "Core Dev", "login": "core", "count": 70},
            {"name": "Second", "login": "second", "count": 30},
            {"name": "dependabot[bot]", "login": "dependabot[bot]", "count": 40},
            {"name": "Newcomer A", "login": "a", "count": 1},
            {"name": "Newcomer B", "login": "b", "count": 1},
            {"name": "Newcomer C", "login": "c", "count": 1},
            {"name": "Regular", "login": "reg", "count": 5},
        ],
    }


def test_summarize_counts_people_newcomers_and_bus_factor() -> None:
    stats = summarize(_payload())
    assert stats is not None
    assert stats.committers_last_year == 6  # the bot is excluded
    assert stats.commits_last_year == 108
    assert stats.newcomer_committers_last_year == 3
    assert stats.bus_factor == 1  # 70 of 108 commits is more than half
    assert summarize({}) is None


def test_bus_factor_counts_people_until_half_of_commits() -> None:
    payload = {
        "past_year_committers": [
            {"login": "a", "count": 10},
            {"login": "b", "count": 10},
            {"login": "c", "count": 10},
            {"login": "d", "count": 9},
        ]
    }
    stats = summarize(payload)
    assert stats is not None and stats.bus_factor == 2


@respx.mock
def test_fetch_commit_stats_handles_unknown_repos() -> None:
    respx.get(f"{API}/hosts/GitHub/repositories/acme/lib").mock(
        return_value=httpx.Response(200, json=_payload())
    )
    respx.get(f"{API}/hosts/GitHub/repositories/acme/new").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    http = CachedHttpClient()
    stats = fetch_commit_stats(http, api_url=API, owner="acme", repo="lib", ttl=60)
    assert stats is not None and stats.newcomer_committers_last_year == 3
    assert fetch_commit_stats(http, api_url=API, owner="acme", repo="new", ttl=60) is None
