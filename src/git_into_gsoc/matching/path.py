"""A short, ordered plan from where a contributor is to a first useful pull request.

The steps change with experience: someone new to open source practises the
pull request routine first and starts with documentation or tests, which the
onboarding research finds is how most newcomers learn a codebase; someone
experienced goes straight to the ideas and the mentors. Hours per week set
the pace. Each step names the command that does it.
"""

from __future__ import annotations

from typing import Any

from git_into_gsoc.matching.profile import ContributorProfile

GUIDE = "https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide"


def _quote(name: str) -> str:
    return '"' + name.replace('"', "") + '"'


def learning_path(
    person: ContributorProfile,
    orgs: list[dict[str, Any]],
    ideas_that_fit: list[dict[str, Any]] | None = None,
    *,
    top_has_starter: bool | None = None,
) -> list[dict[str, Any]]:
    """Steps for this person, built around their best-fitting organization.

    The skill to learn comes from the top organization's ideas that fit the
    person, not from everything its page lists. With `top_has_starter` False (no
    open beginner issue there right now), the first-task step goes through its ideas
    and mentors instead of an issue search that would come back empty.
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

    def add(step: str, why: str, command: str | None = None) -> None:
        steps.append({"step": step, "why": why, "command": command})

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
        "Pick its most active repository, set it up, and run the tests.",
        "Getting the project to build is the first real barrier; solve it before choosing an issue.",
        f"git-into-gsoc repos {name}, then git-into-gsoc orient OWNER/REPO",
    )
    if level in {"new", "some"} and top_has_starter is False:
        add(
            "Ask its mentors which small task would help a newcomer, starting from the idea "
            "closest to you.",
            "It has no open beginner issue right now; at organizations like this, first tasks "
            "come from mentors and ideas rather than labelled issues.",
            f"git-into-gsoc ideas {name}",
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
            f"git-into-gsoc ideas {name}",
        )
    if learn:
        add(
            f"Learn {learn[0]} by reading the code that uses it in this project.",
            f"The ideas there that fit you also ask for: {', '.join(learn[:3])}.",
            f"git-into-gsoc ideas {name}",
        )
    add(
        "Before proposals open, talk with a mentor about one idea in your own words.",
        "A proposal built on earlier contact and merged work is what reviewers score.",
        f"git-into-gsoc ideas {name}",
    )
    hours = person.hours_per_week
    if hours and hours <= 8:
        add(
            f"At {hours} hours a week, aim for one small pull request every two weeks and a small "
            "(about 90 hour) project.",
            "Steady small changes beat a rushed large one.",
            None,
        )
    for number, step in enumerate(steps, start=1):
        step["n"] = number
    return steps
