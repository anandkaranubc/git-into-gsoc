"""GSoC program timeline helpers.

Dates for completed years come from the official program pages.
GSoC 2027 dates are not published yet — we expose planning phases
and clearly mark estimates vs official facts.
"""

from __future__ import annotations

from datetime import date

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, OFFICIAL_GSOC_HOME
from git_into_gsoc.models import TimelineEvent

# Official 2026 milestones (America/New_York), from summerofcode.withgoogle.com
GSOC_2026_EVENTS: list[tuple[str, str, str]] = [
    ("Program announced", "2025-12-03", "Organizations and contributors can start preparing"),
    ("Org applications open", "2026-01-19", "Mentoring orgs apply"),
    ("Org applications deadline", "2026-02-03", ""),
    ("Accepted orgs announced", "2026-02-19", "Contributor exploration intensifies"),
    ("Contributor proposals open", "2026-03-16", "Submit via official GSoC site only"),
    ("Proposal deadline", "2026-03-31", ""),
    ("Accepted projects announced", "2026-04-30", "Community bonding begins after this"),
    ("Program end", "2026-11-11", ""),
]

# Planning scaffold for 2027 — NOT official until Google publishes dates.
GSOC_2027_PLANNING: list[tuple[str, str, str]] = [
    ("Watch for program announcement", "2026-11-01", "ESTIMATE — confirm on official site"),
    ("Study 2026 orgs & contribute early", "2026-11-01", "Best predictor of 2027 org continuity"),
    ("Org list expected (typical window)", "2027-02-01", "ESTIMATE — do not treat as official"),
    ("Proposal window (typical)", "2027-03-01", "ESTIMATE — submit only on official site"),
    ("Coding period (typical summer)", "2027-06-01", "ESTIMATE — length varies by project"),
]


def build_timeline(year: int = DEFAULT_TARGET_YEAR) -> list[TimelineEvent]:
    today = date.today()
    events: list[TimelineEvent] = []

    if year == 2026:
        source = GSOC_2026_EVENTS
        official = True
    elif year == 2027:
        source = GSOC_2027_PLANNING
        official = False
    else:
        return [
            TimelineEvent(
                name=f"No embedded timeline for {year}",
                date="unknown",
                status="unknown",
                notes=f"Check {OFFICIAL_GSOC_HOME}/programs/{year}",
            )
        ]

    for name, iso, notes in source:
        try:
            event_date = date.fromisoformat(iso)
            if event_date < today:
                status = "past"
            elif event_date == today:
                status = "today"
            else:
                status = "upcoming"
        except ValueError:
            status = "unknown"
        if not official and "ESTIMATE" in notes:
            status = f"estimate/{status}"
        events.append(TimelineEvent(name=name, date=iso, status=status, notes=notes))
    return events


def program_status(year: int = DEFAULT_TARGET_YEAR) -> dict[str, object]:
    timeline = build_timeline(year)
    upcoming = [e for e in timeline if "upcoming" in e.status or e.status == "today"]
    return {
        "year": year,
        "official_home": OFFICIAL_GSOC_HOME,
        "program_page": f"{OFFICIAL_GSOC_HOME}/programs/{year}",
        "dates_are_official": year == 2026,
        "disclaimer": (
            "GSoC 2027 dates are not officially published yet. "
            "Use 2026 archive data for org research and verify all dates on the official site."
            if year >= 2027
            else "Dates sourced from the official GSoC 2026 program page."
        ),
        "next_milestones": [e.model_dump() for e in upcoming[:3]],
        "timeline": [e.model_dump() for e in timeline],
    }
