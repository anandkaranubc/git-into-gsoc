"""A repository's own beginner label counts when issues are scored, not only the usual names."""

from __future__ import annotations

from git_into_gsoc.github.repos import is_beginner_label as search_rule
from git_into_gsoc.models import Availability, IssueCandidate
from git_into_gsoc.scoring.issues import is_beginner_label, score_issue


def _scored(labels: list[str]) -> IssueCandidate:
    return score_issue(
        IssueCandidate(
            repo="acme/lib",
            number=1,
            title="Tests should raise exceptions",
            url="https://github.com/acme/lib/issues/1",
            labels=labels,
            availability=Availability.AVAILABLE,
            body_excerpt="Steps to reproduce: run the tests. Expected: an exception.",
        )
    )


def test_a_repositorys_own_beginner_label_counts() -> None:
    # MDAnalysis labels beginner issues "GSOC Starter" and "Difficulty-easy". The search
    # found them by those labels, then scoring said "No beginner label" and capped them.
    for labels in (["testing", "GSOC Starter"], ["Difficulty-easy"]):
        issue = _scored(labels)
        assert not any(s.startswith("No beginner label") for s in issue.signals), labels
        assert any(s.startswith("Beginner label") for s in issue.signals), labels


def test_help_wanted_alone_is_still_not_a_beginner_label() -> None:
    issue = _scored(["help wanted", "performance"])
    assert any(s.startswith("No beginner label") for s in issue.signals)
    assert issue.beginner_score <= 75


def test_the_search_and_scoring_agree() -> None:
    for name in ["good first issue", "GSOC Starter", "Difficulty-easy", "help wanted", "bug"]:
        assert is_beginner_label(name) == search_rule(name), name
