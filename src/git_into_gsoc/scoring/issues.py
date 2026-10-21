"""Beginner-issue scoring."""

from __future__ import annotations

from datetime import UTC, datetime

from git_into_gsoc.models import Availability, IssueCandidate

POSITIVE_LABELS = {
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner friendly",
    "beginner-friendly",
    "easy",
    "starter",
    "first-timers-only",
    "help wanted",
    "help-wanted",
    "newcomer",
    "documentation",
    "docs",
    "bug",
    "gsoc",
}

NEGATIVE_LABELS = {
    "breaking change",
    "security",
    "critical",
    "epic",
    "rfc",
    "proposal",
    "wontfix",
    "blocked",
    "needs design",
}


def score_issue(issue: IssueCandidate) -> IssueCandidate:
    score = 40.0
    signals: list[str] = []
    labels = {label.lower() for label in issue.labels}

    pos = labels & POSITIVE_LABELS
    if pos:
        score += min(25.0, 8.0 * len(pos))
        signals.append("Beginner-friendly labels: " + ", ".join(sorted(pos)[:4]))

    neg = labels & NEGATIVE_LABELS
    if neg:
        score -= 15.0
        signals.append("Caution labels: " + ", ".join(sorted(neg)))

    if issue.availability == Availability.AVAILABLE:
        score += 20.0
        signals.append("Availability: available")
    elif issue.availability == Availability.STALE:
        score -= 10.0
        signals.append("Availability: stale")
    elif issue.availability in {
        Availability.ASSIGNED,
        Availability.LIKELY_TAKEN,
        Availability.CLAIMED,
    }:
        score -= 30.0
        signals.append(f"Availability: {issue.availability.value}")
    elif issue.availability == Availability.CONTESTED:
        score -= 25.0
        signals.append("Availability: contested by several people")
    elif issue.availability == Availability.CLOSED:
        score -= 50.0

    assessment = issue.assessment
    if assessment is not None:
        if assessment.maintainer_engaged:
            score += 6.0
            signals.append("Maintainers active in the thread")
        if assessment.caveats:
            score -= 3.0 * len(assessment.caveats)
    if issue.gsoc_org:
        score += 5.0
        signals.append(f"Part of GSoC org {issue.gsoc_org}")
    if issue.filed_by_maintainer:
        score += 6.0
        signals.append("Filed by a maintainer, so it reflects a real priority")

    if issue.updated_at:
        days = (datetime.now(UTC) - issue.updated_at.astimezone(UTC)).days
        if days <= 30:
            score += 10.0
            signals.append("Updated in last 30 days")
        elif days >= 180:
            score -= 10.0
            signals.append("No updates in 180+ days")

    if issue.comments <= 2:
        score += 5.0
        signals.append("Low comment noise")
    elif issue.comments >= 10:
        score -= 5.0
        signals.append("Busy discussion thread")

    body = issue.body_excerpt.lower()
    if any(word in body for word in ("steps to reproduce", "acceptance criteria", "expected")):
        score += 5.0
        signals.append("Issue appears well-specified")
    if len(issue.body_excerpt) < 40:
        score -= 5.0
        signals.append("Very short issue body. Ask maintainers for details")

    issue.beginner_score = round(max(0.0, min(score, 100.0)), 1)
    issue.signals = signals
    return issue
