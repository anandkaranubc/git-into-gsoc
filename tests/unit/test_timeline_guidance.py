from __future__ import annotations

from git_into_gsoc.gsoc.timeline import build_timeline, program_status
from git_into_gsoc.guidance import ANTI_SPAM_RULES, journey_overview, proposal_checklist


def test_2027_timeline_marked_as_estimate() -> None:
    events = build_timeline(2027)
    assert events
    assert any("ESTIMATE" in (e.notes or "") for e in events)


def test_program_status_disclaimer() -> None:
    status = program_status(2027)
    assert status["dates_are_official"] is False
    assert "2027" in status["disclaimer"]


def test_journey_overview_complete() -> None:
    overview = journey_overview()
    assert len(overview["phases"]) == 8
    assert len(ANTI_SPAM_RULES) >= 5
    assert len(proposal_checklist()) >= 5
