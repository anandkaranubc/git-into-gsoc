"""A short, ordered plan from where a contributor is to a first useful pull request.

The steps change with experience: someone new to open source practises the
pull request routine first and starts with documentation or tests, which the
onboarding research finds is how most newcomers learn a codebase; someone
experienced goes straight to the ideas and the mentors. Hours per week set
the pace. Each step names the command that does it.
"""

from __future__ import annotations

from typing import Any

from git_into_gsoc.coach import (
    GSOC_FAQ_URL,
    LONGEST_CODING_WEEKS,
    STANDARD_CODING_WEEKS,
    fitting_size,
    project_weeks,
)
from git_into_gsoc.matching.profile import ContributorProfile

GUIDE = "https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide"


def _quote(name: str) -> str:
    return '"' + name.replace('"', "") + '"'


def _pace(hours: int) -> str:
    """Which project size fits these hours, by the same rule as `start`'s hours note."""
    weeks = project_weeks(hours)
    fit = fitting_size(hours)
    small, medium = weeks["small"], weeks["medium"]
    longer = (
        f"longer than the standard {STANDARD_CODING_WEEKS}, which your mentor has to agree "
        f"to; GSoC allows at most {LONGEST_CODING_WEEKS} weeks"
    )
    if "medium" in fit["comfortable"]:
        if medium <= STANDARD_CODING_WEEKS:
            return f"a 175-hour project fits the standard {STANDARD_CODING_WEEKS} weeks (about {medium})"
        return f"a 175-hour project fits in about {medium} weeks, {longer}"
    if "small" in fit["comfortable"]:
        stretch = f", {longer}" if small > STANDARD_CODING_WEEKS else ""
        where = "too close to the limit" if "medium" in fit["tight"] else "past the limit"
        return (
            f"plan for a 90-hour project (about {small} weeks{stretch}); a 175-hour one would "
            f"take about {medium}, {where}"
        )
    where = (
        f"longer than the {LONGEST_CODING_WEEKS}-week limit"
        if "small" in fit["too_long"]
        else f"too close to the {LONGEST_CODING_WEEKS}-week limit"
    )
    return f"even a 90-hour project would take about {small} weeks, {where}, so find more hours before you apply"


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
    unread = bool((top or {}).get("ideas_unread"))
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
        add(
            f"Plan around {hours} hours a week: {_pace(hours)}.",
            "Mentors ask how much time you have; a project that fits it is one you can finish.",
            None,
        )
    if level == "experienced":
        add(
            "Check that you can take part: GSoC is for students and beginners to open source, "
            "and you must be 18 when you register.",
            "Its FAQ says regular open source contributors are not beginners; check before you "
            "put in the time.",
            f"Read {GSOC_FAQ_URL}",
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
