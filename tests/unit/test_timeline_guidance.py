"""The program timeline: embedded history, estimates, phases, and the journey overview."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import respx

from conftest import load_fixture
from git_into_gsoc.gsoc.timeline import (
    build_timeline,
    current_phase,
    estimate_program,
    load_history,
    program_status,
)
from git_into_gsoc.guidance import ANTI_SPAM_RULES, journey_overview, proposal_checklist

OCT_2026 = datetime(2026, 10, 20, tzinfo=UTC)


def test_embedded_history_has_official_years() -> None:
    history = load_history()
    assert {2025, 2026} <= set(history)
    keys = {m["name"] for m in history[2026]["milestones"]}
    assert {"contributor_proposals_open", "proposal_deadline", "program_end"} <= keys


def test_estimate_projects_52_weeks_with_measured_windows() -> None:
    history = load_history()
    estimate = estimate_program(2027, history)
    assert estimate is not None
    assert estimate["estimated_from"] == 2026
    by_key = {m["name"]: m for m in estimate["milestones"] if not m.get("project_size")}
    proposals = by_key["contributor_proposals_open"]
    assert proposals["datetime"].startswith("2027-03-15")
    # 2025 → 2026 drift for the announcement was ~6 weeks, so its window is wide.
    assert by_key["prog_announce"]["window_days"] > 30
    assert all(m["window_days"] >= 14 for m in estimate["milestones"])


def test_unpublished_year_is_labelled_estimate() -> None:
    status = program_status(2027, official_program=None, now=OCT_2026)
    assert status["dates_are_official"] is False
    assert "ESTIMATE" in status["disclaimer"]
    assert status["phase"]["id"] == "before_announcement"
    assert all(m["window_days"] for m in status["timeline"])
    assert status["next_milestones"][0]["key"] == "prog_announce"


def test_official_program_drives_phase_and_stats() -> None:
    official = load_fixture("official_program_2026.json")
    status = program_status(2026, official_program=official, now=OCT_2026)
    assert status["dates_are_official"] is True
    assert status["phase"]["id"] == "coding"
    assert status["stats"]["orgs_accepted"] > 100
    assert all(m["window_days"] is None for m in status["timeline"])


def test_offline_falls_back_to_embedded_snapshot() -> None:
    status = program_status(2026, official_program=None, offline=True, now=OCT_2026)
    assert status["dates_are_official"] is True
    assert "snapshot" in status["source"].lower()


def test_project_size_filters_evaluation_milestones() -> None:
    official = load_fixture("official_program_2026.json")
    small = build_timeline(official, official=True, project_size="small", now=OCT_2026)
    large = build_timeline(official, official=True, project_size="large", now=OCT_2026)
    assert {m.project_size for m in small} <= {None, "small"}
    assert {m.project_size for m in large} <= {None, "large"}


def test_phase_progression() -> None:
    official = load_fixture("official_program_2026.json")
    timeline = build_timeline(official, official=True)
    assert current_phase(timeline, datetime(2025, 11, 1, tzinfo=UTC)).id == "before_announcement"
    assert current_phase(timeline, datetime(2026, 3, 1, tzinfo=UTC)).id == "org_exploration"
    assert current_phase(timeline, datetime(2026, 3, 20, tzinfo=UTC)).id == "proposal_window"
    assert current_phase(timeline, datetime(2026, 5, 10, tzinfo=UTC)).id == "community_bonding"
    assert current_phase(timeline, datetime(2026, 12, 1, tzinfo=UTC)).id == "complete"


@respx.mock
def test_toolkit_switches_to_official_when_published() -> None:
    from git_into_gsoc.service import GSoCToolkit

    official = load_fixture("official_program_2026.json")
    respx.get("https://summerofcode.withgoogle.com/api/program/2026/").mock(
        return_value=httpx.Response(200, json=official)
    )
    respx.get("https://summerofcode.withgoogle.com/api/program/2027/").mock(
        return_value=httpx.Response(404, json={"message": "Program matching query does not exist."})
    )
    toolkit = GSoCToolkit()
    assert toolkit.program_info(2026)["dates_are_official"] is True
    assert toolkit.program_info(2027)["dates_are_official"] is False


@respx.mock
def test_toolkit_survives_official_site_outage() -> None:
    from git_into_gsoc.service import GSoCToolkit

    respx.get("https://summerofcode.withgoogle.com/api/program/2026/").mock(
        return_value=httpx.Response(503)
    )
    info = GSoCToolkit().program_info(2026)
    assert info["dates_are_official"] is True
    assert "snapshot" in info["source"].lower()


def test_journey_overview_complete() -> None:
    overview = journey_overview()
    assert len(overview["phases"]) == 10
    assert list(overview["phases"]) == [
        "learn",
        "discover",
        "evaluate",
        "orient",
        "community",
        "find_issues",
        "contribute",
        "iterate",
        "proposal",
        "track",
    ]
    assert len(ANTI_SPAM_RULES) >= 5
    assert len(proposal_checklist()) >= 5
