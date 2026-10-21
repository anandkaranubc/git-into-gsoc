from __future__ import annotations

from datetime import UTC, datetime, timedelta

from git_into_gsoc.models import Availability, IssueCandidate, OrgSummary, RepoHealth
from git_into_gsoc.scoring.health import score_repo_health
from git_into_gsoc.scoring.issues import score_issue
from git_into_gsoc.scoring.org_match import canonical, mentions, score_org_match, slot_trend


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


def _org(**overrides: object) -> OrgSummary:
    base: dict[str, object] = {
        "name": "SymPy",
        "description": "symbolic mathematics in pure Python",
        "technologies": ["python"],
        "topics": ["mathematics", "science"],
        "years_active": [2022, 2023, 2024, 2025, 2026],
        "latest_year": 2026,
        "num_projects_latest": 4,
        "projects_by_year": {2024: 5, 2025: 6, 2026: 5},
        "category": "Science and medicine",
    }
    base.update(overrides)
    return OrgSummary.model_validate(base)


def test_org_match_technology_and_continuity() -> None:
    result = score_org_match(
        _org(), technologies=["python"], topics=["science"], reference_year=2026
    )
    assert result.relevant
    assert result.score > 40
    assert any("python" in r.lower() for r in result.reasons)
    assert any("2026" in r for r in result.reasons)


def test_org_match_requires_relevance_when_filtered() -> None:
    assert not score_org_match(_org(), technologies=["rust"]).relevant
    assert not score_org_match(_org(), query="kubernetes").relevant


def test_short_terms_do_not_substring_match() -> None:
    org = _org(description="A Google-scale cloud platform", technologies=["java"])
    assert not score_org_match(org, technologies=["go"]).relevant
    assert not score_org_match(org, technologies=["c"]).relevant


def test_symbol_terms_match_exactly() -> None:
    org = _org(technologies=["c/c++", "qt"])
    assert score_org_match(org, technologies=["cpp"]).relevant
    assert score_org_match(org, technologies=["c"]).relevant
    assert not score_org_match(org, technologies=["c#"]).relevant


def test_browse_mode_ranks_by_continuity() -> None:
    veteran = score_org_match(_org(years_active=list(range(2016, 2027))), reference_year=2026)
    newcomer = score_org_match(_org(years_active=[2026], projects_by_year={}), reference_year=2026)
    assert veteran.relevant and newcomer.relevant
    assert veteran.score > newcomer.score


def test_slot_trend() -> None:
    assert slot_trend({2024: 4, 2025: 4, 2026: 8}) == "growing"
    assert slot_trend({2024: 8, 2025: 8, 2026: 4}) == "shrinking"
    assert slot_trend({2024: 5, 2025: 5, 2026: 5}) == "steady"
    assert slot_trend({2026: 5}) is None


def test_mentions_word_boundaries() -> None:
    assert mentions("We love C++ and Rust", "c++")
    assert not mentions("maintainers", "ai")
    assert mentions("Applied AI research", "ai")
    assert canonical(" Golang ") == "go"
