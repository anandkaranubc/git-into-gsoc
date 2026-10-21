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
        beginner_label="good first issue",
        open_beginner_issues=4,
        prs_sampled=40,
        merge_rate=0.7,
        outsider_prs_sampled=12,
        outsider_merge_rate=0.6,
        outside_authors_merged=3,
        median_pr_hours=24,
        license="MIT",
    )
    scored = score_repo_health(health)
    assert scored.health_score >= 85
    assert scored.grade == "A"
    assert any("outside contributors" in s for s in scored.signals)


def test_repo_health_warns_when_outsiders_rarely_merged() -> None:
    health = RepoHealth(
        full_name="acme/closed",
        url="https://github.com/acme/closed",
        pushed_at=datetime.now(UTC) - timedelta(days=3),
        prs_sampled=30,
        merge_rate=0.8,
        outsider_prs_sampled=10,
        outsider_merge_rate=0.1,
    )
    scored = score_repo_health(health)
    assert any("Rarely merges" in w for w in scored.warnings)


def test_repo_health_does_not_score_tiny_outsider_samples_or_stars() -> None:
    few = RepoHealth(
        full_name="acme/small",
        url="https://github.com/acme/small",
        pushed_at=datetime.now(UTC) - timedelta(days=3),
        stars=5000,
        outsider_prs_sampled=4,
        outsider_merge_rate=0.0,
    )
    scored = score_repo_health(few)
    assert not any("Rarely merges" in w for w in scored.warnings)
    assert any("too few to score" in s for s in scored.signals)
    assert not any("star" in s.lower() for s in scored.signals)


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


def _busy_repo(**overrides: object) -> RepoHealth:
    # Shaped like OWASP/Nest on 2026-10-21: everything looks great except that
    # 7 of the last 10 outside pull requests were not merged.
    fields: dict[str, object] = {
        "full_name": "acme/busy",
        "url": "https://github.com/acme/busy",
        "stars": 900,
        "pushed_at": datetime.now(UTC) - timedelta(days=1),
        "has_contributing": True,
        "has_code_of_conduct": True,
        "has_pr_template": True,
        "has_ci": True,
        "beginner_label": "good first issue",
        "open_beginner_issues": 11,
        "prs_sampled": 40,
        "merge_rate": 0.56,
        "outsider_prs_sampled": 10,
        "outsider_merge_rate": 0.3,
        "outside_authors_merged": 2,
        "median_pr_hours": 12,
        "committers_last_year": 135,
        "newcomer_committers_last_year": 72,
        "license": "MIT",
        "median_outsider_pr_size": 3,
    }
    fields.update(overrides)
    return RepoHealth(**fields)  # type: ignore[arg-type]


def test_a_repo_that_rejects_most_outside_prs_never_gets_an_a() -> None:
    scored = score_repo_health(_busy_repo())
    assert scored.grade != "A"
    assert scored.health_score < 85
    assert any("7 of the last 10" in w for w in scored.warnings)
    rare = score_repo_health(_busy_repo(outsider_merge_rate=0.1))
    assert rare.grade in {"C", "D", "F"}


def test_pr_size_is_reported_without_telling_people_to_shrink_their_work() -> None:
    scored = score_repo_health(_busy_repo())
    size = next(s for s in scored.signals if "lines" in s)
    assert "keep yours" not in size


def test_beginner_issue_count_says_how_many_are_still_unassigned() -> None:
    scored = score_repo_health(_busy_repo(open_beginner_issues=11, assigned_beginner_issues=7))
    assert any(
        "4 open 'good first issue' issue(s) nobody is assigned to" in s for s in scored.signals
    )
    taken = score_repo_health(_busy_repo(open_beginner_issues=5, assigned_beginner_issues=5))
    assert any("already assigned" in w for w in taken.warnings)


def test_recommendation_text_matches_the_grade() -> None:
    from git_into_gsoc.service import _repo_recommendation

    busy = score_repo_health(_busy_repo())
    assert "Go ahead" not in _repo_recommendation(busy.health_score, busy.warnings)
    assert "warnings" in _repo_recommendation(90, ["One person wrote most commits"])
    assert "Go ahead" in _repo_recommendation(90, [])


def _candidate(labels: list[str], **overrides: object) -> IssueCandidate:
    fields: dict[str, object] = {
        "repo": "acme/lib",
        "number": 7,
        "title": "x",
        "url": "https://github.com/acme/lib/issues/7",
        "labels": labels,
        "availability": Availability.AVAILABLE,
        "updated_at": datetime.now(UTC) - timedelta(days=2),
        "comments": 1,
        "filed_by_maintainer": True,
        "gsoc_org": "Acme",
        "body_excerpt": "Steps to reproduce: run it. Expected: no crash. " * 3,
    }
    fields.update(overrides)
    return score_issue(IssueCandidate(**fields))  # type: ignore[arg-type]


def test_help_wanted_alone_is_not_a_beginner_issue() -> None:
    # Shaped like apache/sedona#2993 (2026-10-21): a large tooling change that
    # scored 100 because every label in the list counted as beginner-friendly.
    big = _candidate(["improvement", "help wanted", "docs", "behavior change", "question"])
    starter = _candidate(["good first issue", "help wanted"])
    assert big.beginner_score <= 75
    assert starter.beginner_score > big.beginner_score
    assert any("No beginner label" in s for s in big.signals)
    assert any("Caution" in s and "behavior change" in s for s in big.signals)


def test_beginner_label_variants_count_once() -> None:
    one = _candidate(["good first issue"])
    many = _candidate(["good first issue", "beginner", "easy", "starter"])
    assert many.beginner_score == one.beginner_score


def test_a_compound_term_counts_once() -> None:
    # A simulated run typed --tech "C/C++" and saw MariaDB score 137 ("Uses c; Uses c++;
    # Uses c/c++") against 79 for --tech C++: one skill counted three times.
    org = _org(name="MariaDB", technologies=["c", "c++", "c/c++"], topics=["databases"])
    compound = score_org_match(org, technologies=["C/C++"])
    single = score_org_match(org, technologies=["C++"])
    assert compound.score == single.score
    assert sum(r.startswith("Uses") for r in compound.reasons) == 1
    both = score_org_match(org, technologies=["C", "C++"])  # two skills still count twice
    assert both.score > single.score


def test_a_long_open_backlog_issue_ranks_below_a_fresh_good_first_issue() -> None:
    # ros2/rclcpp#985 (opened 2020, labelled help wanted and backlog) ranked first in
    # a simulated run of `issues --org ros2`, above real good first issues.
    old = _candidate(
        ["enhancement", "help wanted", "backlog"],
        created_at=datetime(2020, 2, 8, tzinfo=UTC),
    )
    fresh = _candidate(
        ["good first issue"], created_at=datetime.now(UTC) - timedelta(days=60), comments=4
    )
    assert fresh.beginner_score > old.beginner_score
    assert any("Open since 2020" in s for s in old.signals)
    assert any("backlog" in s for s in old.signals)


def test_an_epic_is_never_a_top_beginner_pick() -> None:
    # JdeRobot/RoboticsAcademy-Desktop#11 (2026-10-21), "EPIC Feature Request: ...",
    # labelled good first issue and epic, scored 66 as an available beginner task.
    epic = IssueCandidate(
        repo="JdeRobot/RoboticsAcademy-Desktop",
        number=11,
        title="EPIC Feature Request: Progress Tracking and Engagement Features",
        url="https://github.com/JdeRobot/RoboticsAcademy-Desktop/issues/11",
        labels=["enhancement", "good first issue", "help wanted", "epic"],
        availability=Availability.AVAILABLE,
        comments=1,
        updated_at=datetime.now(UTC) - timedelta(days=3),
    )
    scored = score_issue(epic)
    assert scored.beginner_score <= 35
    assert any("sub-issues" in s for s in scored.signals)
    by_title = score_issue(
        epic.model_copy(update={"labels": ["good first issue"], "title": "[Tracking issue] Docs"})
    )
    assert by_title.beginner_score <= 35
