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
    is_main_repo,
    mentioned_repos,
    outside_authors_merged,
    outside_merges,
    outside_merges_points,
    pick_beginner_label,
    pull_stats,
    repo_kind,
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
    # A published document: `repos` read nothing for Learning Unlimited while `ideas` did.
    published = "https://docs.google.com/document/d/e/2PACX-1vQHE4/pub"
    assert ideas_fetch_url(published + "#h.x") == published


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


def test_toolchain_follows_the_main_language_and_knows_more_build_systems() -> None:
    # ArduPilot (2026-10-21) is 58% C++ with a pyproject.toml for its Python tools;
    # `repo` called it a "Python project" and missed waf and BUILD.md.
    root = [{"name": n} for n in ("pyproject.toml", "waf", "wscript", "BUILD.md", "Dockerfile")]
    hints, _ = detect_toolchain(root, language="C++")
    assert "Python project (pyproject.toml)" not in hints
    assert "Python tooling (pyproject.toml)" in hints
    assert hints[0] == "Build instructions in BUILD.md"
    assert "waf build (./waf)" in hints
    python_hints, _ = detect_toolchain(root, language="Python")
    assert "Python project (pyproject.toml)" in python_hints


def test_repo_language_matches_common_short_forms() -> None:
    from git_into_gsoc.github.repos import repo_lead_score

    # `repos ... --language cpp` used to add nothing for a C++ repository.
    repo = {"language": "C++", "pushed_at": None, "stargazers_count": 1}
    for spelling in ("cpp", "C++", "c++"):
        _, reasons = repo_lead_score(
            repo, beginner_issues=0, ideas_mention=False, language=spelling
        )
        assert "Written in C++" in reasons


def test_repositories_around_a_project_are_told_apart_from_its_code() -> None:
    # Names from a blind review of live `repos` runs, each graded bad as a first stop.
    for name in ("GeomScale/gsoc26", "ioos/gsoc", "kubevirt/community", "kubevirt/enhancements"):
        assert repo_kind(name) == "not code", name
    for name in (
        "openMF/mifos-x-actionhub-publish-android-on-playstore-beta",
        "scummvm/dockerized-bb",
        "tardis-sn/release-pipeline-template",
        "ros2/buildfarm_perf_tests",
    ):
        assert repo_kind(name) == "plumbing", name
    for name in (
        "joomla/framework.joomla.org",
        "Rust-GCC/Rust-GCC.github.io",
        "gnuradio/hugo-website",
    ):
        assert repo_kind(name) == "website", name
    for name in ("scummvm/scummvm", "joomla/joomla-cms", "openMF/mifos-mobile", "helm/helm"):
        assert repo_kind(name) is None, name  # helm/helm is Helm itself, not plumbing
    assert is_main_repo("kubevirt/kubevirt")
    assert not is_main_repo("kubevirt/kubevirt-tekton-tasks")
    assert is_main_repo("openMF/mifos-mobile", most_starred=True)


def test_the_main_repository_outranks_a_gsoc_repository_the_ideas_page_names() -> None:
    gsoc = {"full_name": "geom/gsoc26", "pushed_at": _iso(3), "stargazers_count": 2}
    main = {"full_name": "geom/volesti", "pushed_at": _iso(3), "stargazers_count": 150}
    gsoc_score, reasons = repo_lead_score(
        gsoc, beginner_issues=0, ideas_mention=True, language=None
    )
    main_score, _ = repo_lead_score(
        main, beginner_issues=0, ideas_mention=False, language=None, main_repo=True
    )
    assert main_score > gsoc_score
    assert any("not the project's code" in r for r in reasons)


def test_a_main_repository_with_issues_turned_off_is_still_ranked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: None)

    def repo(name: str, stars: int, *, issues: bool = True) -> dict[str, Any]:
        return {
            "full_name": f"scummvm/{name}",
            "html_url": f"https://github.com/scummvm/{name}",
            "language": "C++",
            "stargazers_count": stars,
            "pushed_at": _iso(1),
            "archived": False,
            "fork": False,
            "has_issues": issues,
        }

    listed = [
        repo("dockerized-bb", 30),
        repo("scummvm-icons", 20),
        repo("scummvm", 2400, issues=False),
    ]
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner, pages=1: listed)
    monkeypatch.setattr(toolkit.github, "beginner_issue_counts", lambda owner: {})
    monkeypatch.setattr(toolkit.github, "list_pulls", lambda owner, repo, **k: [])
    found = toolkit.discover_repos("scummvm")
    assert found["repos"][0]["full_name"] == "scummvm/scummvm"
    assert any("issues are turned off" in r for r in found["repos"][0]["reasons"])


@respx.mock
def test_a_full_first_page_of_repositories_reads_the_second() -> None:
    api = "https://api.github.com/orgs/openMF/repos"
    first = [{"full_name": f"openMF/connector-{n}"} for n in range(100)]
    respx.get(api, params={"page": "2"}).mock(
        return_value=httpx.Response(200, json=[{"full_name": "openMF/mifos-mobile"}])
    )
    respx.get(api).mock(return_value=httpx.Response(200, json=first))
    repos = GitHubClient().list_owner_repos("openMF", pages=2)
    assert len(repos) == 101 and repos[-1]["full_name"] == "openMF/mifos-mobile"


def test_outside_authors_merged_counts_people_without_write_access_lately() -> None:
    since = NOW - timedelta(days=180)

    def pr(login: str, role: str, days: float | None, bot: bool = False) -> dict[str, Any]:
        return {
            "user": {"login": login, "type": "Bot" if bot else "User"},
            "author_association": role,
            "merged_at": _iso(days) if days is not None else None,
        }

    pulls = [
        pr("ana", "CONTRIBUTOR", 10),
        pr("ana", "CONTRIBUTOR", 20),  # the same person twice
        pr("ben", "NONE", 30),
        pr("core", "MEMBER", 5),  # the team
        pr("dependabot[bot]", "NONE", 2, bot=True),
        pr("old", "CONTRIBUTOR", 400),  # too long ago
        pr("open", "CONTRIBUTOR", None),  # not merged
    ]
    assert outside_authors_merged(pulls, since=since) == 2


def test_a_repository_outsiders_never_get_merged_in_drops_below_one_they_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: None)

    def repo(name: str, stars: int) -> dict[str, Any]:
        return {
            "full_name": f"lab/{name}",
            "html_url": f"https://github.com/lab/{name}",
            "language": "Python",
            "stargazers_count": stars,
            "pushed_at": _iso(1),
            "fork": False,
            "has_issues": True,
        }

    listed = [repo("quiet-helper", 900), repo("toolkit", 300)]
    merged = {"user": {"login": "ana"}, "author_association": "CONTRIBUTOR", "merged_at": _iso(9)}
    by_team = {"user": {"login": "core"}, "author_association": "MEMBER", "merged_at": _iso(3)}
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner, pages=1: listed)
    monkeypatch.setattr(toolkit.github, "beginner_issue_counts", lambda owner: {})
    monkeypatch.setattr(
        toolkit.github,
        "list_pulls",
        lambda owner, repo, **k: [merged] * 3 if repo == "toolkit" else [by_team] * 5,
    )
    found = toolkit.discover_repos("lab")
    assert [r["full_name"] for r in found["repos"]] == ["lab/toolkit", "lab/quiet-helper"]
    quiet = found["repos"][1]
    assert any("No pull request from outside the team merged" in r for r in quiet["reasons"])


def test_a_repository_that_rises_into_the_checked_top_is_checked_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import git_into_gsoc.service as service
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(service, "OUTSIDE_CHECKED", 1)
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: None)
    listed = [
        {
            "full_name": f"lab/{name}",
            "html_url": f"https://github.com/lab/{name}",
            "stargazers_count": stars,
            "pushed_at": _iso(1),
            "fork": False,
            "has_issues": True,
        }
        for name, stars in (("quiet", 900), ("busy", 300))
    ]
    seen: list[str] = []

    def pulls(owner: str, repo: str, **k: Any) -> list[dict[str, Any]]:
        seen.append(repo)
        return (
            []
            if repo == "quiet"
            else [{"user": {"login": "ana"}, "author_association": "NONE", "merged_at": _iso(5)}]
        )

    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner, pages=1: listed)
    monkeypatch.setattr(toolkit.github, "beginner_issue_counts", lambda owner: {})
    monkeypatch.setattr(toolkit.github, "list_pulls", pulls)
    found = toolkit.discover_repos("lab")
    assert seen == ["quiet", "busy"]
    assert found["repos"][0]["full_name"] == "lab/busy"


def test_repos_says_where_to_start_when_no_repository_takes_outside_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: None)
    listed = [
        {
            "full_name": f"lab/tool-{n}",
            "html_url": f"https://github.com/lab/tool-{n}",
            "stargazers_count": 10,
            "pushed_at": _iso(1),
            "fork": False,
            "has_issues": True,
        }
        for n in range(4)
    ]
    by_team = {"user": {"login": "core"}, "author_association": "MEMBER", "merged_at": _iso(3)}
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner, pages=1: listed)
    monkeypatch.setattr(toolkit.github, "beginner_issue_counts", lambda owner: {})
    monkeypatch.setattr(toolkit.github, "list_pulls", lambda owner, repo, **k: [by_team])
    note = toolkit.discover_repos("lab")["note"]
    assert "None of the 4 repositories checked" in note
    assert "mentors" in note
    # "lab" is a GitHub login, not a GSoC organization `ideas` could look up.
    assert "git-into-gsoc ideas" not in note
    # One repository that takes outside work is enough to say nothing.
    welcome = {"user": {"login": "ana"}, "author_association": "NONE", "merged_at": _iso(3)}
    monkeypatch.setattr(
        toolkit.github,
        "list_pulls",
        lambda owner, repo, **k: [welcome] if repo == "tool-2" else [by_team],
    )
    assert toolkit.discover_repos("lab")["note"] == ""


def test_an_empty_issue_search_in_an_organization_points_to_its_ideas() -> None:
    from git_into_gsoc.service import _when_no_issues

    steps = _when_no_issues("python", org="ML4SCI", repo=None, gsoc_org=True)
    assert any('git-into-gsoc ideas "ML4SCI"' in step for step in steps)
    # A plain GitHub login is not something `ideas` can look up.
    login = _when_no_issues("python", org="some-lab", repo=None)
    assert not any("git-into-gsoc ideas" in step for step in login)
    assert not any(
        "git-into-gsoc ideas" in s for s in _when_no_issues("python", org=None, repo=None)
    )


def _closed(login: str, role: str, days: float, *, merged: bool = True, bot: bool = False):
    return {
        "user": {"login": login, "type": "Bot" if bot else "User"},
        "author_association": role,
        "updated_at": _iso(days),
        "merged_at": _iso(days) if merged else None,
    }


def test_the_outside_merge_claim_covers_only_the_period_the_sample_reaches() -> None:
    # A full page of 30 that reaches back 12 days says nothing about the last 180.
    busy = [_closed("core", "MEMBER", 0.4 * n) for n in range(30)]
    found = outside_merges(busy)
    assert found.days <= 12 and found.authors == 0
    _, reason = outside_merges_points(found)
    assert "in the last 180 days" not in reason and "its last 30 closed" in reason
    # A shorter page is the whole history: the full window holds.
    small = [_closed("core", "MEMBER", 10), _closed("core", "MEMBER", 300)]
    assert outside_merges(small).days == 180


def test_bots_only_no_pulls_and_several_outsiders_each_say_what_they_mean() -> None:
    bots = outside_merges([_closed("dependabot[bot]", "NONE", 1, bot=True)] * 30)
    points, reason = outside_merges_points(bots)
    assert points == 0 and "all from bots" in reason
    points, reason = outside_merges_points(outside_merges([]))
    assert points < 0 and "No closed pull requests yet" in reason
    many = outside_merges([_closed(name, "CONTRIBUTOR", 5) for name in ("ana", "ben", "cy")])
    points, reason = outside_merges_points(many)
    assert many.authors == 3 and points > 0 and "3 people outside the team" in reason


def _quiet_lab(monkeypatch: pytest.MonkeyPatch, count: int, *, failing: set[str] = frozenset()):
    from git_into_gsoc.errors import RateLimitError
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, year=None: None)
    listed = [
        {
            "full_name": f"lab/tool-{n}",
            "html_url": f"https://github.com/lab/tool-{n}",
            "stargazers_count": 100 - n,
            "pushed_at": _iso(1),
            "fork": False,
            "has_issues": True,
        }
        for n in range(count)
    ]
    calls: list[str] = []

    def pulls(owner: str, repo: str, **k: Any) -> list[dict[str, Any]]:
        calls.append(repo)
        if repo in failing:
            raise RateLimitError("limit", reset_at=None)
        return [_closed("core", "MEMBER", 3)]

    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner, pages=1: listed)
    monkeypatch.setattr(toolkit.github, "beginner_issue_counts", lambda owner: {})
    monkeypatch.setattr(toolkit.github, "list_pulls", pulls)
    return toolkit, calls


def test_in_an_all_quiet_organization_no_unchecked_repository_rises_above_a_checked_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit, calls = _quiet_lab(monkeypatch, 20)
    found = toolkit.discover_repos("lab", limit=20)
    assert len(calls) == 15  # the request budget
    read = [r for r in found["repos"] if any("outside the team" in x for x in r["reasons"])]
    assert found["repos"][: len(read)] == read  # every read one before every unread one
    assert "None of the 15 repositories checked" in found["note"]


def test_a_repository_whose_pull_requests_could_not_be_read_says_so_and_stays_below(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit, _ = _quiet_lab(monkeypatch, 6, failing={"tool-0", "tool-1"})
    found = toolkit.discover_repos("lab", limit=6)
    names = [r["full_name"] for r in found["repos"]]
    # tool-0 and tool-1 have the most stars, but they could not be checked.
    assert names.index("lab/tool-0") > names.index("lab/tool-2")
    unread = next(r for r in found["repos"] if r["full_name"] == "lab/tool-0")
    assert any("could not be read" in x for x in unread["reasons"])
    assert "2 repositories could not be checked" in found["note"]
