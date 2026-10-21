from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.repos import (
    contributing_path,
    detect_toolchain,
    is_bot,
    mentioned_repos,
    pick_beginner_label,
    pull_stats,
    repo_lead_score,
)
from git_into_gsoc.gsoc.ideas import ideas_fetch_url, to_text

NOW = datetime.now(UTC)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _pull(
    login: str, role: str, merged: bool, hours: float = 24, bot: bool = False
) -> dict[str, Any]:
    return {
        "user": {"login": login, "type": "Bot" if bot else "User"},
        "author_association": role,
        "created_at": _iso(10),
        "merged_at": _iso(10 - hours / 24) if merged else None,
    }


def test_pull_stats_ignore_bots_and_split_outsiders() -> None:
    pulls = [
        _pull("dependabot[bot]", "NONE", True, bot=True),
        _pull("renovate", "NONE", True),
        _pull("core", "MEMBER", True, hours=2),
        _pull("alice", "FIRST_TIME_CONTRIBUTOR", True, hours=48),
        _pull("bob", "CONTRIBUTOR", False),
        _pull("carol", "NONE", False),
    ]
    stats = pull_stats(pulls)
    assert stats.sampled == 4
    assert stats.merge_rate == 0.5
    assert stats.outsider_sampled == 3
    assert round(stats.outsider_merge_rate or 0, 2) == 0.33
    assert stats.outside_authors_merged == 1  # alice; bob and carol were not merged
    assert stats.median_hours == 25


def test_is_bot() -> None:
    assert is_bot({"login": "pre-commit-ci[bot]"})
    assert is_bot({"login": "github-actions", "type": "Bot"})
    assert not is_bot({"login": "octocat", "type": "User"})


def test_pick_beginner_label_falls_back_to_any_beginner_spelling() -> None:
    assert pick_beginner_label([{"name": "bug"}, {"name": "first contrib"}]) == "first contrib"
    assert pick_beginner_label([{"name": "newbie-friendly"}]) == "newbie-friendly"
    assert pick_beginner_label([{"name": "Difficulty: Starter"}]) == "Difficulty: Starter"
    assert pick_beginner_label([{"name": "good_for_beginners"}]) == "good_for_beginners"
    assert pick_beginner_label([{"name": "easy"}]) == "easy"
    assert pick_beginner_label([{"name": "uneasy"}, {"name": "bug"}]) is None


def test_pick_beginner_label_prefers_canonical() -> None:
    labels = [{"name": "bug"}, {"name": "Good First Issue"}, {"name": "beginner"}]
    assert pick_beginner_label(labels) == "Good First Issue"
    assert pick_beginner_label([{"name": "Difficulty: Beginner-Friendly"}]) is not None
    assert pick_beginner_label([{"name": "bug"}]) is None


def test_detect_toolchain_and_devcontainer() -> None:
    hints, dev = detect_toolchain(
        [{"name": "pyproject.toml"}, {"name": ".pre-commit-config.yaml"}, {"name": ".devcontainer"}]
    )
    assert "Python project (pyproject.toml)" in hints
    assert any("pre-commit" in h for h in hints)
    assert dev


def test_contributing_path_from_profile() -> None:
    profile = {
        "files": {
            "contributing": {"html_url": "https://github.com/a/b/blob/main/docs/CONTRIBUTING.md"}
        }
    }
    assert contributing_path(profile) == "docs/CONTRIBUTING.md"
    assert contributing_path({}) is None


def test_mentioned_repos_by_url_and_name() -> None:
    repos = [
        {"name": "volesti", "full_name": "GeomScale/volesti"},
        {"name": "web", "full_name": "GeomScale/web"},
    ]
    text = "Project 1 improves volesti. See https://github.com/geomscale/dingo for code."
    found = mentioned_repos(text, ["GeomScale"], repos)
    assert "geomscale/volesti" in found
    assert "geomscale/dingo" in found
    assert "geomscale/web" not in found


def test_repo_lead_score_prefers_ideas_and_beginner_issues() -> None:
    repo = {"pushed_at": _iso(3), "stargazers_count": 200, "language": "Python"}
    boosted, reasons = repo_lead_score(
        repo, beginner_issues=5, ideas_mention=True, language="python"
    )
    plain, _ = repo_lead_score(repo, beginner_issues=0, ideas_mention=False, language=None)
    assert boosted > plain
    assert "Named on the GSoC ideas page" in reasons


def test_ideas_fetch_url_handles_google_docs() -> None:
    assert (
        ideas_fetch_url("https://docs.google.com/document/d/abc_123/edit?tab=t.0#heading=x")
        == "https://docs.google.com/document/d/abc_123/export?format=txt"
    )
    assert ideas_fetch_url("javascript:alert(1)") is None
    assert ideas_fetch_url("https://example.org/ideas#top") == "https://example.org/ideas"


def test_ideas_fetch_url_prefers_raw_github_content() -> None:
    assert (
        ideas_fetch_url("https://github.com/org/repo/wiki/GSoC-2026-Ideas")
        == "https://raw.githubusercontent.com/wiki/org/repo/GSoC-2026-Ideas.md"
    )
    assert (
        ideas_fetch_url("https://github.com/org/repo/blob/main/docs/IDEAS.md#top")
        == "https://raw.githubusercontent.com/org/repo/main/docs/IDEAS.md"
    )
    assert ideas_fetch_url("https://github.com/org/repo") == "https://github.com/org/repo"


def test_license_name_falls_back_to_display_name() -> None:
    from git_into_gsoc.github.client import _license_name

    assert _license_name({"spdx_id": "MIT", "name": "MIT License"}) == "MIT"
    assert _license_name({"spdx_id": "NOASSERTION", "name": "Other"}) == "Other"
    assert _license_name(None) is None


def test_to_text_keeps_links() -> None:
    text = to_text('<p>See <a href="https://github.com/org/repo">repo</a></p><script>x()</script>')
    assert "https://github.com/org/repo" in text
    assert "x()" not in text


@respx.mock
def test_repo_health_end_to_end() -> None:
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "acme/lib",
                "html_url": "https://github.com/acme/lib",
                "stargazers_count": 800,
                "pushed_at": _iso(2),
                "license": {"spdx_id": "MIT"},
            },
        )
    )
    respx.get(f"{api}/community/profile").mock(
        return_value=httpx.Response(
            200,
            json={
                "files": {
                    "contributing": {
                        "html_url": "https://github.com/acme/lib/blob/main/CONTRIBUTING.md"
                    },
                    "code_of_conduct": {"html_url": "x"},
                    "pull_request_template": {"html_url": "y"},
                }
            },
        )
    )
    respx.get(f"{api}/actions/workflows").mock(
        return_value=httpx.Response(200, json={"total_count": 3})
    )
    respx.get(f"{api}/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[_pull(f"u{i}", "CONTRIBUTOR", i % 2 == 0) for i in range(8)]
            + [_pull("core", "MEMBER", True)]
            + [_pull("lead", "CONTRIBUTOR", True)],  # assignable: an insider despite the label
        )
    )
    respx.get(f"{api}/issues/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/pulls/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/assignees").mock(
        return_value=httpx.Response(200, json=[{"login": "core"}, {"login": "lead"}])
    )
    respx.get(f"{api}/labels").mock(
        return_value=httpx.Response(200, json=[{"name": "good first issue"}])
    )
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    respx.get(f"{api}/issues").mock(
        return_value=httpx.Response(200, json=[{"number": 1}, {"number": 2, "pull_request": {}}])
    )
    health = GitHubClient().repo_health("https://github.com/acme/lib")
    assert health.has_contributing and health.has_ci and health.has_pr_template
    assert health.open_beginner_issues == 1
    assert health.outsider_prs_sampled == 8  # lead is assignable, so not an outsider
    assert health.insiders_known and health.pr_source == "rest"
    assert health.grade in {"A", "B"}


def test_attach_first_replies_uses_only_the_covered_window() -> None:
    from git_into_gsoc.github.repos import attach_first_replies

    pulls = [
        {"number": 10, "user": {"login": "alice"}, "created_at": _iso(3)},  # inside window
        {"number": 11, "user": {"login": "bob"}, "created_at": _iso(3)},  # only bot + self replies
        {"number": 12, "user": {"login": "carol"}, "created_at": _iso(40)},  # before the window
    ]
    comments = [
        {
            "issue_url": "https://api.github.com/repos/a/b/issues/10",
            "created_at": _iso(2.9),
            "user": {"login": "sympy-bot", "type": "User"},
        },
        {
            "issue_url": "https://api.github.com/repos/a/b/issues/10",
            "created_at": _iso(2.5),
            "user": {"login": "maintainer", "type": "User"},
        },
        {
            "pull_request_url": "https://api.github.com/repos/a/b/pulls/10",
            "created_at": _iso(2.8),
            "user": {"login": "reviewer", "type": "User"},
        },
        {
            "issue_url": "https://api.github.com/repos/a/b/issues/11",
            "created_at": _iso(2.0),
            "user": {"login": "bob", "type": "User"},
        },
        {
            "issue_url": "https://api.github.com/repos/a/b/issues/12",
            "created_at": _iso(1.0),
            "user": {"login": "maintainer", "type": "User"},
        },
        # an older comment on an unrelated issue sets the start of the covered window
        {
            "issue_url": "https://api.github.com/repos/a/b/issues/7",
            "created_at": _iso(5),
            "user": {"login": "someone", "type": "User"},
        },
    ]
    pulls, covered = attach_first_replies(pulls, comments)
    assert covered == 2
    assert pulls[0]["first_response_at"] == _iso(2.8)  # earliest human, bot skipped
    assert "first_response_at" not in pulls[1]  # author's own comment does not count
    assert "first_response_at" not in pulls[2]  # created before the comment window


@respx.mock
def test_rest_path_reports_first_reply_but_scores_it_only_with_a_sample() -> None:
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(200, json={"full_name": "acme/lib", "pushed_at": _iso(1)})
    )
    for path in ("community/profile", "actions/workflows"):
        respx.get(f"{api}/{path}").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/assignees").mock(return_value=httpx.Response(200, json=[]))
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    pulls = [{**_pull(f"u{i}", "CONTRIBUTOR", True, hours=24), "number": 100 + i} for i in range(6)]
    for pr in pulls:
        pr["created_at"] = _iso(2)
    respx.get(f"{api}/pulls").mock(return_value=httpx.Response(200, json=pulls))
    comments = [
        {
            "issue_url": f"https://api.github.com/repos/acme/lib/issues/{100 + i}",
            "created_at": _iso(2 - 5 / 24),
            "user": {"login": "maintainer", "type": "User"},
        }
        for i in range(6)
    ] + [
        {
            "issue_url": "https://api.github.com/repos/acme/lib/issues/1",
            "created_at": _iso(10),
            "user": {"login": "someone", "type": "User"},
        }
    ]
    respx.get(f"{api}/issues/comments").mock(return_value=httpx.Response(200, json=comments))
    respx.get(f"{api}/pulls/comments").mock(return_value=httpx.Response(200, json=[]))
    health = GitHubClient().repo_health("acme/lib")
    assert health.pr_source == "rest"
    assert health.first_response_sampled == 6
    assert health.median_first_response_hours is not None
    assert 4.5 <= health.median_first_response_hours <= 5.5
    assert any("human reply within" in s for s in health.signals)


@respx.mock
def test_rest_path_widens_the_comment_window_when_the_sample_is_short() -> None:
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(200, json={"full_name": "acme/lib", "pushed_at": _iso(1)})
    )
    for path in ("community/profile", "actions/workflows"):
        respx.get(f"{api}/{path}").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/assignees").mock(return_value=httpx.Response(200, json=[]))
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    pulls = [{**_pull(f"u{i}", "CONTRIBUTOR", True), "number": 200 + i} for i in range(6)]
    for pr in pulls:
        pr["created_at"] = _iso(9)
    respx.get(f"{api}/pulls").mock(return_value=httpx.Response(200, json=pulls))

    def comment(number: int, days_ago: float) -> dict[str, object]:
        return {
            "issue_url": f"https://api.github.com/repos/acme/lib/issues/{number}",
            "created_at": _iso(days_ago),
            "user": {"login": "maintainer", "type": "User"},
        }

    # page 1: 100 recent comments on unrelated issues, newest first, only 3 days deep
    page1 = [comment(1, 0.01 * i) for i in range(100)]
    # page 2: older comments that reply to the six sampled PRs opened nine days ago
    page2 = [comment(200 + i, 8.8) for i in range(6)] + [comment(1, 12)]
    issue_route = respx.get(f"{api}/issues/comments")
    issue_route.side_effect = lambda request: httpx.Response(
        200, json=page2 if request.url.params.get("page") == "2" else page1
    )
    review_route = respx.get(f"{api}/pulls/comments").mock(
        return_value=httpx.Response(200, json=[])
    )
    health = GitHubClient().repo_health("acme/lib")
    assert issue_route.call_count == 2 and review_route.call_count == 2
    assert health.first_response_sampled == 6
    assert health.median_first_response_hours == pytest.approx(0.2 * 24, abs=0.5)


def test_landed_elsewhere_matches_number_title_or_coauthor_credit() -> None:
    from git_into_gsoc.github.repos import closed_outside_unmerged, landed_elsewhere

    def pr(number: int, login: str, title: str, opened: str = "2026-10-01T00:00:00Z") -> dict:
        return {
            "number": number,
            "title": title,
            "user": {"login": login, "type": "User"},
            "author_association": "CONTRIBUTOR",
            "created_at": opened,
            "closed_at": "2026-10-05T00:00:00Z",
            "merged_at": None,
        }

    def commit(sha: str, message: str, when: str = "2026-10-06T00:00:00Z") -> dict:
        return {"sha": sha, "commit": {"message": message, "committer": {"date": when}}}

    closed = [
        pr(10, "ana", "Handle empty input in the CSV reader"),
        pr(11, "ben", "Fix typo"),
        pr(12, "cy", "Speed up the tokenizer for long files"),
        pr(13, "dee", "Document the retry option in the client"),
        pr(14, "eve", "Correct the license header in setup files"),
    ]
    commits = [
        commit("1111111aaaa", "Handle empty input in the CSV reader (#99)"),
        commit("2222222bbbb", "Fix typo"),
        commit("3333333cccc", "Tokenizer: faster scanning (#12)"),
        commit(
            "4444444dddd", "Retry docs\n\nCo-authored-by: Dee <77+dee@users.noreply.github.com>"
        ),
        commit(
            "5555555eeee", "Correct the license header in setup files", when="2026-09-01T00:00:00Z"
        ),
    ]
    assert landed_elsewhere(closed, commits) == {12: "3333333", 13: "4444444"}
    # Go imports pull requests into Gerrit and records them in a trailer.
    gerrit = [commit("6666666ffff", "csv: handle empty input\n\nGitHub-Pull-Request: acme/lib#10")]
    assert landed_elsewhere(closed, gerrit) == {10: "6666666"}
    # Same title, but the commit is the squash merge of another pull request (#99):
    # a resubmission, not this pull request landing.
    same_title_resubmitted = [commit("7777777gggg", "Handle empty input in the CSV reader")]
    assert landed_elsewhere(closed, same_title_resubmitted) == {10: "7777777"}

    pulls = [
        *closed,
        {**pr(20, "fay", "Merged one"), "merged_at": "2026-10-02T00:00:00Z"},
        {**pr(21, "core", "Insider one"), "author_association": "MEMBER"},
        {**pr(22, "renovate[bot]", "Bump deps"), "user": {"login": "renovate[bot]", "type": "Bot"}},
    ]
    assert [p["number"] for p in closed_outside_unmerged(pulls)] == [10, 11, 12, 13, 14]


def test_pull_stats_counts_outside_work_that_landed_elsewhere() -> None:
    pulls = [
        {
            "number": 1,
            "user": {"login": "ana"},
            "author_association": "NONE",
            "created_at": "2026-10-01T00:00:00Z",
            "merged_at": None,
        },
        {
            "number": 2,
            "user": {"login": "ben"},
            "author_association": "NONE",
            "created_at": "2026-10-01T00:00:00Z",
            "merged_at": "2026-10-02T00:00:00Z",
        },
    ]
    plain = pull_stats(pulls)
    assert plain.outsider_merge_rate == 0.5 and plain.outside_landed_elsewhere == 0
    landed = pull_stats(pulls, landed=frozenset({1}))
    assert landed.outsider_merge_rate == 1.0
    assert landed.outside_authors_merged == 2 and landed.outside_landed_elsewhere == 1
    assert landed.merge_rate == 0.5
