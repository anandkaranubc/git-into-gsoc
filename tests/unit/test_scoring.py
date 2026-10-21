from __future__ import annotations

from datetime import UTC, datetime, timedelta

from git_into_gsoc.models import Availability, IssueCandidate, OrgSummary, RepoHealth
from git_into_gsoc.scoring.health import score_repo_health
from git_into_gsoc.scoring.issues import score_issue
from git_into_gsoc.scoring.org_match import score_org_match


def test_repo_health_rewards_active_welcoming_projects() -> None:
    health = RepoHealth(
        full_name="acme/lib",
        url="https://github.com/acme/lib",
        stars=500,
        pushed_at=datetime.now(UTC) - timedelta(days=3),
        has_contributing=True,
        has_code_of_conduct=True,
        has_ci=True,
        beginner_labels_present=True,
        merge_rate=0.7,
        median_pr_hours=24,
        license="MIT",
    )
    scored = score_repo_health(health)
    assert scored.health_score >= 80
    assert scored.grade in {"A", "B"}


def test_repo_health_zeros_archived() -> None:
    health = RepoHealth(
        full_name="acme/old",
        url="https://github.com/acme/old",
        archived=True,
        stars=1000,
    )
    scored = score_repo_health(health)
    assert scored.health_score == 0
    assert scored.grade == "F"


def test_issue_score_prefers_available_beginner_labels() -> None:
    issue = IssueCandidate(
        repo="acme/lib",
        number=1,
        title="Fix docs typo in install guide",
        url="https://github.com/acme/lib/issues/1",
        labels=["good first issue", "documentation"],
        availability=Availability.AVAILABLE,
        updated_at=datetime.now(UTC) - timedelta(days=2),
        comments=1,
        body_excerpt="Steps to reproduce: open docs. Expected: correct path.",
    )
    scored = score_issue(issue)
    assert scored.beginner_score >= 70


def test_issue_score_penalizes_assigned() -> None:
    open_issue = score_issue(
        IssueCandidate(
            repo="acme/lib",
            number=2,
            title="x",
            url="https://example.com",
            labels=["good first issue"],
            availability=Availability.AVAILABLE,
        )
    )
    taken = score_issue(
        IssueCandidate(
            repo="acme/lib",
            number=3,
            title="x",
            url="https://example.com",
            labels=["good first issue"],
            availability=Availability.ASSIGNED,
        )
    )
    assert open_issue.beginner_score > taken.beginner_score


def test_org_match_technology_and_continuity() -> None:
    org = OrgSummary(
        name="SymPy",
        description="symbolic mathematics",
        technologies=["python"],
        topics=["mathematics", "science"],
        years_active=[2024, 2025, 2026],
        latest_year=2026,
        num_projects_latest=4,
        category="Science and Medicine",
    )
    score, reasons = score_org_match(
        org,
        technologies=["python"],
        topics=["science"],
        prefer_year=2026,
    )
    assert score > 40
    assert any("python" in r.lower() for r in reasons)
    assert any("2026" in r for r in reasons)
