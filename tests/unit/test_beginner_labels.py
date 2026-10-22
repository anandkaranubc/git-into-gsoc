"""A repository's own beginner label counts when issues are scored, not only the usual names."""

from __future__ import annotations

from typing import Any

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


# Real spellings from a census of 24,779 labels in GSoC organizations' top repositories
# (2026-10-21), with the owners that use them.
CENSUS_BEGINNER = [
    "Easy to Fix",  # SymPy
    "complexity:low",  # Neovim
    "Good First Contribution",  # DeepChem, webpack
    "difficulty: 1",  # stdlib-js
    "level: easy",  # Haskell
    "new contributor opportunity",  # OpenStreetMap
    "newcomer: 2-one-file-change",  # Haskell
    "🍭 good first issue",  # Rocket.Chat
    "your first PR",  # OneBusAway
    "low-hanging fruit",  # Typelevel
    "Difficulty Novice",  # cBioPortal
    "upforgrabs",  # Netflix
    "up for grabs",  # NumFOCUS
    "good-first-issues",  # Processing
    "good first issue - LLM not welcome",  # OpenStreetMap
]
CENSUS_TRAPS = [
    "Impact: Low -- ONLY DO IF GOOD FIRST ISSUE",  # Oppia: "Postponing for now"
    "Good First Issue (Taken)",  # Accord Project
    "Easy to Revive",  # SymPy, about old pull requests
    "Easy Review",  # D, about reviewing pull requests
    "Review effort 1/5",
    "size/XS",
    "priority:trivial",
    "not a good first issue",
    "help wanted",
    "difficulty: hard",
    "difficulty: 10",
    "easy to reproduce",
    "starter-kit",
]


def test_census_spellings_count_and_traps_do_not() -> None:
    for name in CENSUS_BEGINNER:
        assert is_beginner_label(name), name
    for name in CENSUS_TRAPS:
        assert not is_beginner_label(name), name


def test_a_taken_label_is_never_picked_for_a_search() -> None:
    from git_into_gsoc.github.repos import beginner_labels, pick_beginner_label

    labels = [{"name": "Good First Issue (Taken)"}, {"name": "Difficulty: Starter"}]
    assert pick_beginner_label(labels) == "Difficulty: Starter"
    assert beginner_labels(labels) == ["Difficulty: Starter"]
    assert pick_beginner_label([{"name": "Impact: Low -- ONLY DO IF GOOD FIRST ISSUE"}]) is None


def test_labels_that_ask_for_no_ai_help() -> None:
    from git_into_gsoc.labels import no_ai_label

    assert no_ai_label(["bug", "not for AI lovers"]) == "not for AI lovers"  # GDAL
    assert no_ai_label(["good first issue - LLM not welcome"])  # OpenStreetMap
    assert no_ai_label(["no-ai"]) == "no-ai"
    # Labels about AI features, or flags on a contribution, ask nothing of the person.
    for name in ["AI", "LLMs", "component: ai", "ai-license", "AI/LLM Policy Violation", "Slop"]:
        assert no_ai_label([name]) is None, name


def test_issue_and_issues_say_when_a_project_wants_no_ai_work(monkeypatch: Any) -> None:
    from git_into_gsoc.matching.profile import ContributorProfile
    from git_into_gsoc.models import IssueAssessment
    from git_into_gsoc.service import GSoCToolkit, _with_cautions

    toolkit = GSoCToolkit()
    found = IssueAssessment(availability=Availability.AVAILABLE, reason="Open")
    issue = {
        "title": "x",
        "html_url": "https://github.com/OSGeo/gdal/issues/9",
        "labels": [{"name": "good first issue"}, {"name": "not for AI lovers"}],
    }
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: {"archived": False})
    monkeypatch.setattr(toolkit.github, "unlinked_pulls", lambda *a: [])
    data = toolkit.issue_status("OSGeo/gdal#9")
    assert data["availability"] == "available"
    assert data["assessment"]["caveats"][0].startswith(
        "The label 'not for AI lovers' says the project does not want AI-generated work"
    )

    listed = _with_cautions(
        [
            {
                "repo": "OSGeo/gdal",
                "number": 9,
                "title": "Fix the parser crash on empty input",
                "labels": ["good first issue", "not for AI lovers"],
                "availability": "available",
                "created_at": "2026-09-01T00:00:00Z",
                "body_excerpt": "Steps to reproduce: run it with no input.",
                "assessment": {"claims": []},
            }
        ],
        ContributorProfile(),
    )
    assert listed[0]["caution"] == (
        "the project does not want AI-generated work on it (label 'not for AI lovers')"
    )
