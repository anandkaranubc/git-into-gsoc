"""A read GitHub did not answer is left out of the health score, never counted as missing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from git_into_gsoc.errors import NotFoundError, RateLimitError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.models import RepoHealth
from git_into_gsoc.scoring.health import score_repo_health


def _perfect(**overrides: object) -> RepoHealth:
    fields: dict[str, object] = {
        "full_name": "acme/ideal",
        "url": "https://github.com/acme/ideal",
        "pushed_at": datetime.now(UTC) - timedelta(days=1),
        "has_contributing": True,
        "contributing_source": "file",
        "has_code_of_conduct": True,
        "has_issue_template": True,
        "has_ci": True,
        "beginner_label": "good first issue",
        "open_beginner_issues": 6,
        "prs_sampled": 40,
        "merge_rate": 0.8,
        "outsider_prs_sampled": 20,
        "outsider_merge_rate": 0.8,
        "outside_authors_merged": 5,
        "median_first_response_hours": 10,
        "first_response_sampled": 12,
        "committers_last_year": 60,
        "newcomer_committers_last_year": 25,
        "license": "MIT",
    }
    fields.update(overrides)
    return RepoHealth(**fields)  # type: ignore[arg-type]


def test_an_unread_community_profile_is_left_out_not_missing() -> None:
    # A rate limit on the community profile used to read as no CONTRIBUTING guide, no
    # Code of Conduct, and no templates: 20 points lost and a false warning.
    scored = score_repo_health(
        _perfect(
            has_contributing=False,
            contributing_source=None,
            has_code_of_conduct=False,
            has_issue_template=False,
            unread=["community profile"],
        )
    )
    assert scored.health_score == 100
    assert not any("No CONTRIBUTING guide" in w for w in scored.warnings)
    left_out = {p.signal for p in scored.points if p.most == 0}
    assert left_out == {"CONTRIBUTING guide", "Code of Conduct", "Issue or PR templates"}
    assert sum(p.most for p in scored.points) == 80
    assert any("GitHub did not answer for its community profile" in n for n in scored.notes)


def test_unread_workflows_and_beginner_issues_are_left_out() -> None:
    scored = score_repo_health(
        _perfect(has_ci=False, open_beginner_issues=None, unread=["workflows", "beginner issues"])
    )
    assert scored.health_score == 100
    left_out = {p.signal for p in scored.points if p.most == 0}
    assert left_out == {"CI on pull requests", "Open beginner issues"}


def test_a_real_answer_still_counts_as_missing() -> None:
    # Nothing unread: no CI really is no CI.
    scored = score_repo_health(_perfect(has_ci=False))
    assert scored.health_score == 92
    assert not scored.notes or not any("did not answer" in n for n in scored.notes)


@pytest.mark.parametrize(
    "method, args, empty",
    [
        ("_community_profile", ("acme", "lib"), {}),
        ("_workflow_count", ("acme", "lib"), 0),
        ("_list_labels", ("acme", "lib"), []),
        ("_count_open_issues_with_label", ("acme", "lib", "good first issue"), (0, 0)),
    ],
)
def test_a_rate_limit_is_none_and_a_404_is_an_answer(
    monkeypatch: pytest.MonkeyPatch, method: str, args: tuple[str, ...], empty: Any
) -> None:
    client = GitHubClient()

    def limited(*_a: object, **_k: object) -> None:
        raise RateLimitError("rate limit exceeded")

    def missing(*_a: object, **_k: object) -> None:
        raise NotFoundError("not found", status_code=404)

    monkeypatch.setattr(client, "_api", limited)
    assert getattr(client, method)(*args) is None
    monkeypatch.setattr(client, "_api", missing)
    assert getattr(client, method)(*args) == empty


def test_several_left_out_signals_are_one_line() -> None:
    from git_into_gsoc.cli import _lost_points_lines

    scored = score_repo_health(
        _perfect(
            has_contributing=False,
            contributing_source=None,
            has_code_of_conduct=False,
            has_issue_template=False,
            unread=["community profile"],
        )
    )
    lines = _lost_points_lines(scored.model_dump(mode="json"))
    left = [line for line in lines if line.startswith("Left out:")]
    assert len(left) == 1
    assert "contributing guide, code of conduct, issue or pr templates" in left[0]
