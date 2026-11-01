"""What the site's start page runs in the browser, and what its test runs natively.

The page (``site/start/``) runs this file in Pyodide, a build of CPython for the
browser, with the real ``git_into_gsoc`` package unpacked beside it. So the ranking
is the matching package itself, not a port of it, and ``tests/unit/test_start_page.py``
runs the same functions in ordinary CPython to show they rank exactly as the CLI does.
Nothing here may import anything outside the package and the standard library: the
browser has only those.
"""

from __future__ import annotations

import json
from typing import Any

from git_into_gsoc.coach import hours_note
from git_into_gsoc.matching.profile import build_profile
from git_into_gsoc.matching.rank import OrgIndex, OrgMatch
from git_into_gsoc.models import OrgSummary
from git_into_gsoc.onboarding import next_steps_after_start, parse_topics
from git_into_gsoc.validation import split_csv

# As `start` shows: three organizations, with two spares in case one sits the year out.
LIMIT = 3
SPARES = 2


def load_index(data: dict[str, Any]) -> OrgIndex:
    """The ranking index from the JSON ``scripts/build_site.py`` writes beside the page."""
    orgs = [OrgSummary.model_validate(raw) for raw in data["orgs"]]
    return OrgIndex.build(
        orgs,
        descriptions=data["descriptions"],
        signals=data["signals"],
        reference_year=int(data["year"]),
    )


def _shell(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _org(match: OrgMatch) -> dict[str, Any]:
    # The same slices `start` prints: three reasons, one readiness line, two caveats.
    reasons = [r for r in match.reasons() if not r.startswith("Accepted in")]
    return {
        "name": match.org.name,
        "slug": match.org.slug,
        "description": match.org.description,
        "fit": match.fit,
        "why": reasons[:3],
        "evidence": match.evidence(),
        "readiness": match.readiness[:1],
        "caveats": match.caveats[:2],
        "skills_to_learn": match.skills_to_learn,
    }


def answer(
    index: OrgIndex,
    *,
    technologies: str = "",
    interests: str = "",
    hours: int | None = None,
    experience: str | None = None,
    limit: int = LIMIT,
) -> dict[str, Any]:
    """Rank for one visitor's four answers, shaped like what `start` prints.

    An organization that said it will not take part in the coming year goes after
    the others and, when that pushes it off the list, is named as set aside, as
    `start` does after its live check.
    """
    hours = int(hours) if hours and int(hours) > 0 else None
    person = build_profile(
        technologies=split_csv(technologies),
        interests=parse_topics(interests),
        experience=experience,
        hours_per_week=hours,
    )
    matches = index.rank(person, limit=limit + SPARES) if not person.empty else []
    sitting_out = [m for m in matches if (m.participation or {}).get("status") == "not_taking_part"]
    ordered = [m for m in matches if m not in sitting_out] + sitting_out
    shown = [_org(m) for m in ordered[:limit]]
    set_aside = [
        {"name": m.org.name, **(m.participation or {})} for m in ordered[limit:] if m in sitting_out
    ]
    commands = []
    if experience:
        commands.append(f"git-into-gsoc profile --experience {experience}")
    options = [
        *(["--tech", _shell(", ".join(w.raw for w in person.skills))] if person.skills else []),
        *(
            ["--interests", _shell(", ".join(w.raw for w in person.interests))]
            if person.interests
            else []
        ),
        *(["--hours", str(hours)] if hours else []),
    ]
    commands.append(" ".join(["git-into-gsoc start", *options]))
    return {
        "matched_on": person.summary(),
        "read_as": person.notes,
        "hours_note": hours_note(hours),
        "organizations": shown,
        "set_aside": set_aside,
        "next_steps": next_steps_after_start(shown, []),
        "commands": commands,
    }


def answer_json(index: OrgIndex, answers_json: str) -> str:
    """`answer` over a JSON object of its keyword arguments; what the page calls."""
    return json.dumps(answer(index, **json.loads(answers_json)))
