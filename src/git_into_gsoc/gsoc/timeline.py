"""GSoC program timelines.

Official milestones come from the GSoC site when Google has published them.
For unpublished years we project the latest official year forward by 52 weeks
(milestones keep their weekday) and attach an uncertainty window measured from
how much each milestone moved between the two most recent official years.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib import resources
from typing import Any

from git_into_gsoc.config import OFFICIAL_GSOC_HOME, OFFICIAL_TIMELINE
from git_into_gsoc.models import Milestone, ProgramPhase

MIN_WINDOW_DAYS = 14
_YEAR = timedelta(weeks=52)

# (milestone that starts the phase, phase id, title, advice)
_PHASES: list[tuple[str, str, str, str]] = [
    (
        "prog_announce",
        "announced",
        "Program announced",
        "Read the rules and FAQ. The organization list is not out yet, so keep "
        "contributing to organizations that took part last year.",
    ),
    (
        "org_application_start",
        "org_applications",
        "Organizations are applying",
        "Organizations are being selected. Those that took part last year are the "
        "safest bets; deepen one or two contributions there.",
    ),
    (
        "org_announce_public",
        "org_exploration",
        "Accepted organizations announced",
        "Shortlist accepted organizations, read their ideas pages, introduce yourself "
        "publicly, and get a first meaningful pull request reviewed.",
    ),
    (
        "contributor_proposals_open",
        "proposal_window",
        "Proposal window is open",
        "Share a draft with mentors early, revise from feedback, and submit on the "
        "official site before the deadline.",
    ),
    (
        "proposal_deadline",
        "proposal_review",
        "Proposals under review",
        "Keep contributing and stay responsive in public channels; mentors notice.",
    ),
    (
        "project_announce_public",
        "community_bonding",
        "Community bonding",
        "Meet your mentor, agree on milestones, and get your development setup working.",
    ),
    (
        "project_work_start",
        "coding",
        "Coding period",
        "Deliver something every week, raise blockers early, and keep what you will show at "
        "evaluations visible.",
    ),
    (
        "program_end",
        "complete",
        "Program complete",
        "Write up your work and plan your next step: keep contributing, mentor, or "
        "apply again next year.",
    ),
]

_BEFORE = ProgramPhase(
    id="before_announcement",
    title="Before the program is announced",
    advice=(
        "The best time to start. Pick orgs that participated last year, contribute "
        "steadily, and treat every date as an estimate until Google publishes it."
    ),
)


@lru_cache(maxsize=1)
def load_history() -> dict[int, dict[str, Any]]:
    """Embedded snapshot of official program data (offline fallback + estimates)."""
    raw = resources.files("git_into_gsoc").joinpath("data/program_history.json").read_text("utf-8")
    payload = json.loads(raw)
    return {int(year): program for year, program in payload["programs"].items()}


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _key(item: dict[str, Any]) -> tuple[str, str | None]:
    return str(item.get("name")), item.get("project_size")


def estimate_program(year: int, history: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    """Project the latest official year before `year` forward to `year`."""
    earlier = sorted(y for y in history if y < year)
    if not earlier:
        return None
    base_year = earlier[-1]
    shift = _YEAR * (year - base_year)
    previous = {
        _key(m): _parse(m["datetime"]) for m in history.get(base_year - 1, {}).get("milestones", [])
    }
    milestones = []
    for item in history[base_year]["milestones"]:
        base_at = _parse(item["datetime"])
        window = MIN_WINDOW_DAYS
        prior = previous.get(_key(item))
        if prior is not None:
            drift = abs((base_at - (prior + _YEAR)).days)
            window = max(MIN_WINDOW_DAYS, drift)
        milestones.append(
            {
                **item,
                "datetime": (base_at + shift).isoformat(),
                "window_days": window,
            }
        )
    return {"milestones": milestones, "estimated_from": base_year}


def build_timeline(
    program: dict[str, Any],
    *,
    official: bool,
    project_size: str = "medium",
    now: datetime | None = None,
) -> list[Milestone]:
    """The program's milestones in date order, each marked past, today, or upcoming.

    Milestones that belong to another project size are left out; those with no
    size apply to every project.
    """
    now = now or datetime.now(UTC)
    items: list[Milestone] = []
    for raw in program.get("milestones", []):
        size = raw.get("project_size")
        if size and size != project_size:
            continue
        at = _parse(raw["datetime"])
        days = (at.date() - now.date()).days
        status = "today" if days == 0 else ("upcoming" if days > 0 else "past")
        items.append(
            Milestone(
                key=str(raw.get("name")),
                label=str(raw.get("label") or raw.get("name")),
                at=at,
                project_size=size,
                official=official,
                status=status,
                days_until=days,
                window_days=None if official else raw.get("window_days", MIN_WINDOW_DAYS),
            )
        )
    items.sort(key=lambda m: m.at)
    return items


def current_phase(timeline: list[Milestone], now: datetime | None = None) -> ProgramPhase:
    """The phase begun by the latest milestone already reached, or the one before any."""
    now = now or datetime.now(UTC)
    reached = {m.key for m in timeline if m.project_size is None and m.at <= now}
    phase = _BEFORE
    for key, phase_id, title, advice in _PHASES:
        if key in reached:
            phase = ProgramPhase(id=phase_id, title=title, advice=advice)
    return phase


def program_status(
    year: int,
    *,
    official_program: dict[str, Any] | None,
    history: dict[int, dict[str, Any]] | None = None,
    project_size: str = "medium",
    now: datetime | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    """Assemble timeline, current phase, and provenance for one program year."""
    now = now or datetime.now(UTC)
    history = load_history() if history is None else history
    official = official_program is not None
    program = official_program
    source_note: str
    if program is None and offline and year in history:
        program, official = history[year], True
        source_note = "Embedded snapshot of official dates (live site unreachable)."
    elif program is None:
        program = estimate_program(year, history)
        source_note = (
            f"ESTIMATE projected from official {program['estimated_from']} dates. "
            "Google has not published this timeline yet."
            if program
            else "No official or estimated timeline available."
        )
    else:
        source_note = "Official dates from summerofcode.withgoogle.com."

    timeline = build_timeline(program or {}, official=official, project_size=project_size, now=now)
    upcoming = [m for m in timeline if m.status in {"upcoming", "today"}]
    return {
        "year": year,
        "dates_are_official": official,
        "source": source_note,
        "official_home": OFFICIAL_GSOC_HOME,
        "official_timeline": OFFICIAL_TIMELINE,
        "program_page": f"{OFFICIAL_GSOC_HOME}/programs/{year}",
        "phase": current_phase(timeline, now).model_dump(),
        "project_size": project_size,
        "next_milestones": [m.model_dump(mode="json") for m in upcoming[:3]],
        "timeline": [m.model_dump(mode="json") for m in timeline],
        "stats": (official_program or {}).get("stats") if official else None,
        "disclaimer": (
            source_note
            if official
            else f"{source_note} Verify every date on {OFFICIAL_GSOC_HOME} before acting."
        ),
    }
