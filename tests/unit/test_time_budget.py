"""The time budget turns hours per week and the next milestone into a plan."""

from __future__ import annotations

from git_into_gsoc.coach import hours_note, time_budget
from git_into_gsoc.models import ProgressState


def _program(*milestones: tuple[str, str, int, bool], phase: str = "org_exploration") -> dict:
    return {
        "phase": {"id": phase},
        "timeline": [
            {"key": key, "label": label, "days_until": days, "status": "upcoming", "official": ok}
            for key, label, days, ok in milestones
        ],
    }


def test_budget_targets_the_proposal_deadline_and_splits_hours() -> None:
    state = ProgressState(profile={"hours_per_week": 6}, phases={"community": True})
    program = _program(
        ("orgs_announced", "Organizations announced", 10, True),
        ("proposal_deadline", "Proposal deadline", 42, True),
    )
    budget = time_budget(state, program)
    assert budget is not None
    assert budget["until"] == "Proposal deadline"
    assert budget["weeks"] == 6 and budget["hours_available"] == 36
    assert budget["official"] is True
    assert sum(part["hours"] for part in budget["suggested_split"]) in {35, 36, 37}
    assert budget["suggested_split"][0]["what"].startswith("Proposal")


def test_budget_needs_hours_and_a_milestone() -> None:
    assert time_budget(ProgressState(), _program(("x", "X", 10, True))) is None
    assert time_budget(ProgressState(profile={"hours_per_week": 5}), _program()) is None
    far = _program(("proposal_deadline", "Proposal deadline", 300, False))
    assert time_budget(ProgressState(profile={"hours_per_week": 5}), far) is None


def test_budget_before_community_contact_puts_setup_first() -> None:
    state = ProgressState(profile={"hours_per_week": "4"})
    budget = time_budget(state, _program(("orgs_announced", "Orgs announced", 14, False)))
    assert budget is not None
    assert budget["official"] is False
    assert budget["suggested_split"][1]["what"].startswith("Set the project up")


def test_hours_note_says_which_project_sizes_fit() -> None:
    # A simulated beginner with 5 hours a week was never told a medium project
    # (about 175 hours, GSoC FAQ) cannot fit even the longest 22-week coding period.
    five = hours_note(5)
    assert five is not None
    assert "about 18 weeks" in five and "medium and large projects would not fit" in five
    assert "developers.google.com/open-source/gsoc/faq" in five
    three = hours_note(3)
    assert three is not None and "even a small project" in three and "about 30 weeks" in three
    assert "large projects would not fit" in (hours_note(10) or "")
    # A simulated run at 15 hours a week was told to choose a small idea, though a
    # medium one (about 175 hours) fits in 12 weeks.
    assert "Choose a small or medium idea" in (hours_note(15) or "")
    assert "Choose a small idea" in (hours_note(5) or "")
    # 8 hours: what fits comes first, then a medium project at the very limit, said as
    # advice (no room for exams or setbacks), apart from Google's 22-week limit.
    eight = hours_note(8) or ""
    assert eight.startswith(
        "At 8 hours a week, a small project (about 90 hours) fits in about 12 weeks"
    )
    assert (
        "a medium one (about 175 hours) would take about 22 weeks, the longest period "
        "allowed, which leaves no room for exams or setbacks" in eight
    )
    assert "Choose a small idea and state your hours in your proposal" in eight
    # 5 hours: 18 weeks fits, but only on a longer timeline than the standard 12.
    assert (
        "a small project (about 90 hours) fits in about 18 weeks, longer than the standard "
        "12, so agree a longer timeline with your mentor" in (hours_note(5) or "")
    )
    # 12 weeks or less needs no such words.
    assert "agree a longer timeline" not in eight.split(";")[0]
    # 16 hours: 350 hours is 22 weeks, at the limit; 20 hours: 18 weeks, all fit.
    assert "a large one (about 350 hours) would take about 22 weeks" in (hours_note(16) or "")
    assert hours_note(20) is None
    assert hours_note(None) is None and hours_note("lots") is None


def test_saving_few_hours_explains_the_fit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from git_into_gsoc.cli import app

    result = CliRunner().invoke(app, ["profile", "--hours", "5"])
    assert result.exit_code == 0, result.output
    assert "medium and large projects would not fit" in " ".join(result.output.split())


def test_ideas_too_big_for_the_saved_hours_are_marked_and_listed_last() -> None:
    # A simulated beginner with 5 hours a week saw a 350-hour idea ranked first.
    from git_into_gsoc.service import _mark_ideas_too_big

    ideas = [
        {"title": "Theming", "hours": 350},
        {"title": "Docs", "hours": 90},
        {"title": "Scheduler", "hours": 175},
        {"title": "Unknown size"},
    ]
    note = _mark_ideas_too_big(ideas, 5)
    assert [i["title"] for i in ideas] == ["Docs", "Unknown size", "Theming", "Scheduler"]
    assert [i["too_big_for_your_hours"] for i in ideas] == [False, False, True, True]
    assert note is not None and "about 110 hours" in note and "2 idea(s)" in note
    assert _mark_ideas_too_big([{"hours": 350}], 20) is None
    assert _mark_ideas_too_big([{"hours": 350}], None) is None
