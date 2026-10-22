"""Beginner-issue scoring."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from git_into_gsoc.labels import is_beginner_label
from git_into_gsoc.models import Availability, IssueCandidate

# Useful context, but not a sign of an easy task: "help wanted" often marks work
# the maintainers have no time for, which can be large.
HELPFUL_LABELS = {"help wanted", "help-wanted", "documentation", "docs", "bug", "gsoc"}

NEGATIVE_LABELS = {
    "backlog",
    "icebox",
    "someday",
    "on hold",
    "long-term",
    "breaking change",
    "behavior change",
    "security",
    "critical",
    "epic",
    "rfc",
    "proposal",
    "wontfix",
    "blocked",
    "needs design",
    "needs discussion",
    "needs triage",
    "difficulty: hard",
    "hard",
    "complex",
    "research",
}
# Without a beginner label an issue can still be a good start, but never a top pick.
NO_BEGINNER_LABEL_CAP = 75.0
# An epic or tracking issue groups many tasks. Even with "good first issue" on it,
# the first task is one of its sub-issues, never the whole thing.
UMBRELLA_LABELS = {"epic", "tracking", "tracking issue", "umbrella", "meta", "roadmap"}
_UMBRELLA_TITLE_RE = re.compile(
    r"^\W*(?:epic|tracking issue|tracker|umbrella|roadmap)\b", re.IGNORECASE
)
UMBRELLA_CAP = 35.0


def score_issue(issue: IssueCandidate) -> IssueCandidate:
    """Score an issue from 0 to 100 as a first task, and say why.

    Sets `beginner_score` and `signals` on the candidate and returns it. Labels,
    availability, freshness, and how well the issue is written each add or take
    points; an epic or an issue with no beginner label is capped, never a top pick.
    """
    score = 40.0
    signals: list[str] = []
    labels = {label.lower() for label in issue.labels}

    # Repository-specific names count too ("GSOC Starter", "Difficulty-easy"): the search
    # uses them, and an exact list called such issues "no beginner label".
    beginner = {label for label in labels if is_beginner_label(label)}
    helpful = labels & HELPFUL_LABELS
    if beginner:
        score += 20.0
        signals.append("Beginner label: " + ", ".join(sorted(beginner)[:3]))
    if helpful:
        score += 5.0
        signals.append("Also labelled: " + ", ".join(sorted(helpful)[:3]))

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
        Availability.NOT_OPEN,
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

    if issue.created_at:
        age_days = (datetime.now(UTC) - issue.created_at.astimezone(UTC)).days
        if age_days > 730:
            score -= 8.0
            signals.append(
                f"Open since {issue.created_at.year}: long-open issues are often harder than "
                "they look, or blocked on a decision"
            )

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

    if labels & UMBRELLA_LABELS or _UMBRELLA_TITLE_RE.match(issue.title or ""):
        score = min(score, UMBRELLA_CAP)
        signals.append("An epic or tracking issue: pick one of its smaller sub-issues instead")

    if not beginner:
        score = min(score, NO_BEGINNER_LABEL_CAP)
        signals.append(
            "No beginner label: issues marked only 'help wanted' are often harder than they look"
        )

    issue.beginner_score = round(max(0.0, min(score, 100.0)), 1)
    issue.signals = signals
    return issue
