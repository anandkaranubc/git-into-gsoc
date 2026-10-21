"""Repository health scoring: how likely is a newcomer's PR to land here?"""

from __future__ import annotations

from datetime import UTC, datetime

from git_into_gsoc.github.repos import MIN_OUTSIDER_SAMPLE
from git_into_gsoc.models import RepoHealth


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    if score >= 58:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def score_repo_health(health: RepoHealth) -> RepoHealth:
    """Weights sum to 100. Outsider merge rate is the strongest newcomer signal.

    Stars add nothing: larger projects reject a higher share of newcomer PRs.
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []

    if health.archived or health.disabled:
        health.health_score = 0.0
        health.grade = "F"
        health.warnings = ["Repository is archived or disabled; do not contribute here for GSoC"]
        health.signals = []
        return health

    if health.pushed_at:
        days = (datetime.now(UTC) - health.pushed_at.astimezone(UTC)).days
        if days <= 14:
            score += 20
            signals.append(f"Very recent activity ({days}d since push)")
        elif days <= 45:
            score += 15
            signals.append(f"Active ({days}d since push)")
        elif days <= 120:
            score += 7
            signals.append(f"Somewhat active ({days}d since push)")
        else:
            warnings.append(f"Stale repository ({days}d since last push)")
    else:
        warnings.append("Missing push timestamp")

    if health.has_contributing:
        score += 12
        signals.append("Has a CONTRIBUTING guide")
    else:
        warnings.append("No CONTRIBUTING guide detected; ask maintainers how to start")
    if health.has_code_of_conduct:
        score += 4
        signals.append("Has a Code of Conduct")
    if health.has_issue_template or health.has_pr_template:
        score += 4
        signals.append("Issue/PR templates guide contributions")
    if health.has_ci:
        score += 8
        signals.append("CI runs on pull requests")

    if health.open_beginner_issues:
        score += 10
        signals.append(f"{health.open_beginner_issues} open '{health.beginner_label}' issue(s)")
    elif health.beginner_label:
        score += 4
        warnings.append(f"'{health.beginner_label}' label exists but no open issues use it")

    if health.merge_rate is not None and health.prs_sampled >= 5:
        if health.merge_rate >= 0.5:
            score += 12
            signals.append(f"Healthy merge rate ({health.merge_rate:.0%} of human PRs)")
        elif health.merge_rate >= 0.25:
            score += 6
            signals.append(f"Moderate merge rate ({health.merge_rate:.0%})")
        else:
            warnings.append(f"Low merge rate ({health.merge_rate:.0%})")

    rate = health.outsider_merge_rate
    sampled = health.outsider_prs_sampled
    if rate is not None and sampled >= MIN_OUTSIDER_SAMPLE:
        if rate >= 0.4:
            score += 12
            signals.append(f"Merges outside contributors' PRs ({rate:.0%} of {sampled})")
        elif rate >= 0.2:
            score += 6
            signals.append(f"Sometimes merges outside PRs ({rate:.0%} of {sampled})")
        else:
            warnings.append(
                f"Rarely merges PRs from outside contributors ({rate:.0%} of {sampled})"
            )
    elif rate is not None and sampled:
        signals.append(
            f"Outside PRs merged: {rate:.0%} of {sampled} (too few to score; check recent PRs)"
        )
    if health.outside_authors_merged:
        score += min(6.0, 2.0 * health.outside_authors_merged)
        signals.append(
            f"{health.outside_authors_merged} different outside author(s) merged recently"
        )

    if health.median_pr_hours is not None:
        if health.median_pr_hours <= 72:
            score += 10
            signals.append(f"Merged PRs land fast (~{health.median_pr_hours:.0f}h median)")
        elif health.median_pr_hours <= 240:
            score += 5
            signals.append(f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median)")
        else:
            warnings.append(
                f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median); "
                "unmerged ones are not counted"
            )

    if health.license:
        score += 4
        signals.append(f"License: {health.license}")
    else:
        warnings.append("No license detected")

    # Stars carry no points: popularity predicts competition, not acceptance.
    if health.stars < 20:
        warnings.append("Very small project; confirm it is still maintained")
    elif health.stars > 50000:
        warnings.append("Very popular repo: beginner issues go fast, expect competition")

    health.health_score = round(min(score, 100.0), 1)
    health.grade = _grade(health.health_score)
    health.signals = signals
    health.warnings = warnings
    return health
