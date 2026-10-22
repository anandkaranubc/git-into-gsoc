"""The GraphQL path of repository health: insiders, first human replies, project bots, and the REST
fallback."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.graphql import QUERY, normalize
from git_into_gsoc.github.repos import is_bot, pull_stats

NOW = datetime.now(UTC)


def _iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pr(
    number: int,
    login: str,
    assoc: str,
    *,
    merged: bool,
    replies: list[tuple[str, float]] = (),
    opened_hours_ago: float = 100,
) -> dict[str, Any]:
    nodes = [
        {
            "__typename": "IssueComment",
            "createdAt": _iso(opened_hours_ago - delay),
            "author": {"login": who, "__typename": "User"},
        }
        for who, delay in replies
    ]
    return {
        "number": number,
        "createdAt": _iso(opened_hours_ago),
        "mergedAt": _iso(opened_hours_ago - 50) if merged else None,
        "closedAt": _iso(opened_hours_ago - 50),
        "authorAssociation": assoc,
        "author": {"login": login, "__typename": "User"},
        "additions": 10,
        "deletions": 2,
        "changedFiles": 1,
        "timelineItems": {"nodes": nodes},
    }


def _payload() -> dict[str, Any]:
    return {
        "data": {
            "rateLimit": {"cost": 4},
            "repository": {
                "assignableUsers": {
                    "totalCount": 2,
                    "nodes": [{"login": "core"}, {"login": "lead"}],
                },
                "pullRequests": {
                    "nodes": [
                        # outsider, first human reply after 2h (bot replied first, author replied too)
                        _pr(
                            1,
                            "alice",
                            "CONTRIBUTOR",
                            merged=True,
                            replies=[("sympy-bot", 0.1), ("alice", 1), ("core", 2)],
                        ),
                        # outsider never answered
                        _pr(2, "bob", "NONE", merged=False, replies=[("dependabot[bot]", 0.5)]),
                        # looks like an outsider by association but is assignable: insider
                        _pr(3, "lead", "CONTRIBUTOR", merged=True, replies=[("core", 30)]),
                        # member
                        _pr(4, "core", "MEMBER", merged=True),
                        # outsider replied in 10h
                        _pr(
                            5,
                            "carol",
                            "FIRST_TIME_CONTRIBUTOR",
                            merged=True,
                            replies=[("lead", 10)],
                        ),
                    ]
                },
            },
        }
    }


def test_normalize_builds_rest_shaped_pulls_and_insiders() -> None:
    analysis = normalize(_payload())
    assert analysis is not None
    assert analysis.insiders == frozenset({"core", "lead"})
    assert analysis.cost == 4
    by_number = {p["number"]: p for p in analysis.pulls}
    assert by_number[1]["user"] == {"login": "alice", "type": "User"}
    assert by_number[1]["first_response_at"] is not None  # core at +2h, not the bot or the author
    assert by_number[2]["first_response_at"] is None  # only a bot replied
    assert normalize({"data": {"repository": None}}) is None


def test_pull_stats_uses_insiders_and_first_human_reply() -> None:
    analysis = normalize(_payload())
    assert analysis is not None
    stats = pull_stats(analysis.pulls, insiders=analysis.insiders)
    assert stats.insiders_known
    assert stats.outsider_sampled == 3  # alice, bob, carol; lead is assignable
    assert stats.outside_authors_merged == 2
    assert stats.median_first_response_hours == pytest.approx(6, abs=0.1)  # median of 2h and 10h
    assert stats.median_outsider_size == 12


def test_project_bots_are_detected_by_name() -> None:
    assert is_bot({"login": "sympy-bot", "type": "User"})
    assert is_bot({"login": "k8s-ci-robot", "type": "User"})
    assert not is_bot({"login": "robotics-fan", "type": "User"})


@respx.mock
def test_repo_health_prefers_graphql_when_a_token_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "acme/lib",
                "html_url": "https://github.com/acme/lib",
                "pushed_at": _iso(5),
                "stargazers_count": 300,
            },
        )
    )
    respx.get(f"{api}/community/profile").mock(return_value=httpx.Response(200, json={"files": {}}))
    respx.get(f"{api}/actions/workflows").mock(
        return_value=httpx.Response(200, json={"total_count": 1})
    )
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    rest_pulls = respx.get(f"{api}/pulls").mock(return_value=httpx.Response(200, json=[]))
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    graphql = respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=_payload())
    )
    # bob's PR 2 was closed unmerged, then a maintainer committed it crediting him.
    commits = respx.get(f"{api}/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "sha": "abcdef1234567",
                    "commit": {
                        "message": "Apply the parser fix\n\nCo-authored-by: Bob <123+bob@users.noreply.github.com>",
                        "committer": {"date": _iso(40)},
                    },
                }
            ],
        )
    )
    health = GitHubClient().repo_health("acme/lib")
    assert graphql.called
    assert commits.called
    assert health.outside_landed_elsewhere == 1
    assert health.outsider_merge_rate == pytest.approx(1.0)
    assert health.outside_authors_merged == 3
    assert any("landed through a maintainer's own commit" in s for s in health.notes)
    sent = json.loads(graphql.calls[0].request.content)
    assert (
        sent["variables"] == {"owner": "acme", "name": "lib"} and "assignableUsers" in sent["query"]
    )
    assert sent["query"].strip() == QUERY.strip()
    assert not rest_pulls.called
    assert health.pr_source == "graphql" and health.insiders_known
    assert health.median_first_response_hours == pytest.approx(6, abs=0.1)
    assert any("human reply" in s for s in health.signals + health.notes)


@respx.mock
def test_repo_health_falls_back_to_rest_when_graphql_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(200, json={"full_name": "acme/lib", "pushed_at": _iso(5)})
    )
    respx.get(f"{api}/community/profile").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{api}/actions/workflows").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    rest_pulls = respx.get(f"{api}/pulls").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/issues/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/pulls/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/assignees").mock(return_value=httpx.Response(403, json={}))
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    respx.post("https://api.github.com/graphql").mock(return_value=httpx.Response(502))
    health = GitHubClient().repo_health("acme/lib")
    assert rest_pulls.called
    assert health.pr_source == "rest" and not health.insiders_known  # assignees call failed
