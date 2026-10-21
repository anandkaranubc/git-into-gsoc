"""The time budget turns hours per week and the next milestone into a plan."""

from __future__ import annotations

from git_into_gsoc.coach import time_budget
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
