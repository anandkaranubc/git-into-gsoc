from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
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
