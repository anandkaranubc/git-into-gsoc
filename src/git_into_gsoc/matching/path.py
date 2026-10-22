"""A short, ordered plan from where a contributor is to a first useful pull request.

The steps change with experience: someone new to open source practises the
pull request routine first and starts with documentation or tests, which the
onboarding research finds is how most newcomers learn a codebase; someone
experienced goes straight to the ideas and the mentors. Hours per week set
the pace. Each step names the command that does it.
"""

from __future__ import annotations

import math
from typing import Any

from git_into_gsoc.matching.profile import ContributorProfile

GUIDE = "https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide"
# The longest a GSoC coding period can run (official FAQ).
MAX_WEEKS = 22


def _quote(name: str) -> str:
    return '"' + name.replace('"', "") + '"'


def learning_path(
    person: ContributorProfile,
    orgs: list[dict[str, Any]],
    ideas_that_fit: list[dict[str, Any]] | None = None,
    *,
    top_has_starter: bool | None = None,
    program: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Steps for this person, built around their best-fitting organization.

    The skill to learn comes from the top organization's ideas that fit the
    person, not from everything its page lists. With `top_has_starter` False (no
    open beginner issue there right now), the first-task step goes through its ideas
    and mentors instead of an issue search that would come back empty. `program`
    (target year, list year, confirmed) puts the calendar first; a blind review of 46
    paths found none said where the program was in its year, and none reached the
    application itself.
    """
    top = orgs[0] if orgs else None
    name = _quote(top["name"]) if top else '"ORG"'
    level = person.experience or "some"
    learn: list[str] = []
    org_name = str((top or {}).get("name") or "").lower()
    for group in ideas_that_fit or []:
        if top and group.get("org") == top.get("name"):
            for idea in group.get("ideas") or []:
                learn.extend(
                    s
                    for s in idea.get("you_would_learn") or []
                    if s not in learn and s.split(" (")[0].lower() not in org_name
                )
    steps: list[dict[str, Any]] = []
    # When this tool could not read the ideas page, point at the page itself.
    unread = any(
        "ideas page" in str(c) and "open it" in str(c) for c in (top or {}).get("caveats") or []
    )
    ideas_url = str((top or {}).get("ideas_url") or "")
    ideas_command = f"Open {ideas_url}" if unread and ideas_url else f"git-into-gsoc ideas {name}"

    def add(step: str, why: str, command: str | None = None) -> None:
        steps.append({"step": step, "why": why, "command": command})

    if program:
        target, listed = program.get("target_year"), program.get("list_year")
        if program.get("confirmed"):
            add(
                f"Check the GSoC {target} timeline: when proposals open and close.",
                "Every step below has to fit before the proposal deadline.",
                "git-into-gsoc program",
            )
        else:
            add(
                f"Know where GSoC is in its year: the {target} organizations are not "
                "announced yet.",
                f"The organizations and ideas here are from {listed}; most return, but none is "
                "confirmed until the official list is published.",
                "git-into-gsoc program",
            )
    hours = person.hours_per_week
    if hours and hours <= 10:
        small, medium = math.ceil(90 / hours), math.ceil(175 / hours)
        if medium <= MAX_WEEKS:
            plan = f"a 175-hour project fits (about {medium} weeks)"
        elif small <= MAX_WEEKS:
            plan = (
                f"plan for a 90-hour project (about {small} weeks); a 175-hour one would take "
                f"about {medium}"
            )
        else:
            plan = (
                f"even a 90-hour project would take about {small} weeks, so find more hours "
                "before you apply"
            )
        add(
            f"Plan around {hours} hours a week: {plan}. GSoC allows at most {MAX_WEEKS} weeks.",
            "Mentors ask how much time you have; a project that fits it is one you can finish.",
            None,
        )
    if level == "new":
        add(
            "Practise the pull request routine once: fork, branch, commit, push, open a pull request.",
            "Learning Git and a new codebase at the same time is the most common early stumble.",
            f"Read {GUIDE}/06-first-contribution.md",
        )
    add(
        f"Read the contributor guide and ideas page of {top['name'] if top else 'your top pick'}, "
        "and join its chat.",
        "Organizations look for people they have already seen in their community.",
        f"git-into-gsoc org {name}",
    )
    add(
        "Pick the repository that fits your skills (its main code comes first in `repos`), "
        "set it up, and run the tests.",
        "Getting the project to build is the first real barrier; solve it before choosing an issue.",
        f"git-into-gsoc repos {name}, then git-into-gsoc orient OWNER/REPO",
    )
    if level in {"new", "some"} and top_has_starter is False:
        add(
            "Ask its mentors which small task would help a newcomer, starting from the idea "
            "closest to you.",
            "No starter issue from it passed the checks above; at organizations like this, "
            "first tasks often come from mentors and ideas rather than labelled issues.",
            ideas_command,
        )
    elif level == "new":
        add(
            "Start with a documentation, test, or small bug issue nobody has claimed.",
            "Small changes teach the review process without the risk of a large rewrite.",
            f"git-into-gsoc issues --org {name}",
        )
    elif level == "some":
        add(
            "Take a good first issue, then a medium one in the area of an idea you like.",
            "A second, larger change in the same area shows mentors you can grow there.",
            f"git-into-gsoc issues --org {name}",
        )
    else:
        add(
            "Choose an idea, ask its mentors which issue would show you can do it, and review an "
            "open pull request.",
            "Reviews and a well-chosen issue show judgement as well as code.",
            ideas_command,
        )
    if learn:
        add(
            f"Learn the basics of {learn[0]} with a short tutorial before you take on an idea "
            "that needs it.",
            f"The ideas there that fit you also ask for: {', '.join(learn[:3])}.",
            ideas_command,
        )
    add(
        "Read the projects it accepted in past years, to see their size and how they were "
        "written up.",
        "Past projects show what this organization's mentors expect from a proposal.",
        f"git-into-gsoc projects --org {name}",
    )
    add(
        "Before proposals open, talk with a mentor about one idea in your own words.",
        "A proposal built on earlier contact and merged work is what reviewers score.",
        ideas_command,
    )
    add(
        "Draft your proposal early, then check it against what organizations reject.",
        "A draft a mentor has seen before the deadline is far stronger than one sent at the end.",
        "git-into-gsoc proposal",
    )
    for number, step in enumerate(steps, start=1):
        step["n"] = number
    return steps
