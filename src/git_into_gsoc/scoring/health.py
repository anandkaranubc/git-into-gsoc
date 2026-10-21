"""Repository health scoring for contributor success likelihood."""

from __future__ import annotations

from datetime import UTC, datetime

from git_into_gsoc.models import RepoHealth


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def score_repo_health(health: RepoHealth) -> RepoHealth:
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []

    if health.archived or health.disabled:
        health.health_score = 0.0
        health.grade = "F"
        health.warnings = ["Repository is archived or disabled — do not contribute here for GSoC"]
        health.signals = []
        return health

    # Recency of pushes
    if health.pushed_at:
        days = (datetime.now(UTC) - health.pushed_at.astimezone(UTC)).days
        if days <= 14:
            score += 25
            signals.append(f"Very recent activity ({days}d since push)")
        elif days <= 45:
            score += 20
            signals.append(f"Active ({days}d since push)")
        elif days <= 120:
            score += 10
            signals.append(f"Somewhat active ({days}d since push)")
        else:
            warnings.append(f"Stale repository ({days}d since last push)")
    else:
        warnings.append("Missing push timestamp")

    # Community files
    if health.has_contributing:
        score += 15
        signals.append("Has CONTRIBUTING guide")
    else:
        warnings.append("No CONTRIBUTING file detected")

    if health.has_code_of_conduct:
        score += 5
        signals.append("Has Code of Conduct")

    if health.has_ci:
        score += 10
        signals.append("CI config detected")

    if health.beginner_labels_present:
        score += 10
        signals.append("Beginner-friendly issue labels present")

    # Merge rate
    if health.merge_rate is not None:
        if health.merge_rate >= 0.5:
            score += 15
            signals.append(f"Healthy merge rate ({health.merge_rate:.0%})")
        elif health.merge_rate >= 0.25:
            score += 8
            signals.append(f"Moderate merge rate ({health.merge_rate:.0%})")
        else:
            warnings.append(f"Low merge rate ({health.merge_rate:.0%})")

    if health.median_pr_hours is not None:
        if health.median_pr_hours <= 72:
            score += 10
            signals.append(f"Fast PR turnaround (~{health.median_pr_hours:.0f}h median)")
        elif health.median_pr_hours <= 240:
            score += 5
            signals.append(f"OK PR turnaround (~{health.median_pr_hours:.0f}h median)")
        else:
            warnings.append(f"Slow PR reviews (~{health.median_pr_hours:.0f}h median)")

    # Size / popularity bands — prefer mid-size active projects for newcomers
    if 100 <= health.stars <= 20000:
        score += 5
        signals.append("Star count in approachable active range")
    elif health.stars < 20:
        warnings.append("Very small star count — verify the project is still maintained")
    elif health.stars > 50000:
        warnings.append("Extremely popular repo — competition for issues may be fierce")

    if health.license:
        score += 5
        signals.append(f"License: {health.license}")
    else:
        warnings.append("No license detected via GitHub API")

    health.health_score = round(min(score, 100.0), 1)
    health.grade = _grade(health.health_score)
    health.signals = signals
    health.warnings = warnings
    return health
