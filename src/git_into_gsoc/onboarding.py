"""First-run guidance: the home screen and the guided `start` setup.

Both read only what the tool already saves (the profile and progress file) plus the
program calendar, so the home screen is fast and works without a GitHub token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from git_into_gsoc.errors import GigError
from git_into_gsoc.validation import split_csv

if TYPE_CHECKING:
    from git_into_gsoc.service import GSoCToolkit

# Topics offered by number in `start`. Each value matches at least a few organizations'
# own topic tags or GSoC categories in the official list, so a pick is never a dead end.
TOPIC_CHOICES: tuple[tuple[str, str], ...] = (
    ("science", "science and medicine"),
    ("ai", "AI and machine learning"),
    ("web", "websites and web apps"),
    ("data", "data and databases"),
    ("developer tools", "developer tools"),
    ("programming languages", "programming languages and compilers"),
    ("cloud", "cloud and infrastructure"),
    ("security", "security"),
    ("media", "graphics, audio, and video"),
    ("operating systems", "operating systems"),
    ("education", "education"),
    ("robotics", "robotics"),
    ("mobile", "mobile apps"),
    ("games", "games"),
)

TECH_EXAMPLES = "python, javascript, java, c++"

# What "making progress" looks like before a proposal, in the order people get there.
# Each step names the command that completes it, so the next one is always concrete.
_MILESTONES: tuple[tuple[str, str, str], ...] = (
    ("profile", "Tell the tool what you know", "git-into-gsoc start"),
    ("shortlist", "Shortlist an organization", 'git-into-gsoc org "NAME" --shortlist'),
    ("repo", "Pick a repository", "git-into-gsoc repo OWNER/NAME --track"),
    ("issue", "Track an issue you could work on", "git-into-gsoc issue OWNER/REPO#123 --track"),
    ("log", "Write a weekly note", 'git-into-gsoc log --goal "..." --done "..."'),
    ("merged", "Get a pull request merged", "git-into-gsoc next"),
)


def parse_topics(answer: str) -> list[str]:
    """Turn "1, 3, open hardware" into ["science", "web", "open hardware"].

    Numbers pick from TOPIC_CHOICES; anything else is kept as typed. Numbers out of
    range are ignored rather than guessed at.
    """
    picked: list[str] = []
    for part in split_csv(answer.replace(" and ", ",")):
        if part.isdigit():
            index = int(part) - 1
            if 0 <= index < len(TOPIC_CHOICES):
                picked.append(TOPIC_CHOICES[index][0])
        else:
            picked.append(part)
    return list(dict.fromkeys(picked))


def milestones(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Progress as concrete steps, each done or not, from the saved progress file."""
    profile = summary.get("profile") or {}
    counts = {
        "profile": int(bool(profile.get("technologies") or profile.get("interests"))),
        "shortlist": len(summary.get("shortlisted_orgs") or []),
        "repo": len(summary.get("tracked_repos") or []),
        "issue": len(summary.get("tracked_issues") or []),
        "log": int(summary.get("log_entries") or 0),
        # `next` records merged pull requests it finds once your profile has a username.
        "merged": int(summary.get("contributions") or 0),
    }
    return [
        {"key": key, "label": label, "done": counts[key] > 0, "count": counts[key], "command": cmd}
        for key, label, cmd in _MILESTONES
    ]


def home(toolkit: GSoCToolkit) -> dict[str, Any]:
    """Everything the bare `git-into-gsoc` command shows: who, when, how far, what next."""
    from git_into_gsoc import __version__

    summary: dict[str, Any] = dict(toolkit.progress.summary())
    steps = milestones(summary)
    profile = summary.get("profile") or {}
    done = sum(1 for s in steps if s["done"])
    return {
        "version": __version__,
        "new_user": not steps[0]["done"],
        "github": profile.get("github"),
        # False shows the gh auth login tip; the token itself is never put in this data.
        "github_token": bool(toolkit.github.token),
        "program": program_now(toolkit),
        "milestones": steps,
        "done": done,
        "total": len(steps),
        "next_command": "git-into-gsoc next" if steps[0]["done"] else "git-into-gsoc start",
    }


def program_now(toolkit: GSoCToolkit) -> dict[str, Any] | None:
    """The year, phase, and next date in a few words; None if no timeline is available."""
    try:
        info = toolkit.program_info()
    except GigError:
        return None
    upcoming = info.get("next_milestones") or []
    return {
        "year": info["year"],
        "dates_are_official": info["dates_are_official"],
        "phase": info["phase"]["title"],
        "advice": info["phase"]["advice"],
        "next_milestone": upcoming[0] if upcoming else None,
    }


def signed_in_login(toolkit: GSoCToolkit) -> str | None:
    """The GitHub username behind the token in use, if there is one; never an error."""
    if not toolkit.github.token:
        return None
    try:
        login = toolkit.github.authenticated_login()
    except GigError:
        return None
    return login


def questions() -> list[dict[str, Any]]:
    """The four `start` questions, for an assistant to ask in its own words."""
    return [
        {"option": "--github", "question": "What is your GitHub username? (optional)"},
        {
            "option": "--tech",
            "question": "Which languages and tools do you know?",
            "examples": TECH_EXAMPLES,
        },
        {
            "option": "--interests",
            "question": "What would you enjoy working on?",
            "choices": [value for value, _ in TOPIC_CHOICES],
        },
        {"option": "--hours", "question": "About how many hours a week can you give?"},
    ]


def first_run(
    toolkit: GSoCToolkit,
    *,
    github: str | None = None,
    technologies: list[str] | None = None,
    interests: list[str] | None = None,
    hours_per_week: int | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Save the answers from `start`, then return organizations that fit and what to do next.

    Organizations come from the embedded official list, so this works without a token.
    The ones shown are checked for posts about the coming year; one that says it will
    sit the year out is set aside and the next match takes its place.
    """
    profile = toolkit.save_profile(
        github=github,
        technologies=technologies or None,
        interests=interests or None,
        hours_per_week=hours_per_week,
    )
    techs = list(profile.get("technologies") or [])
    if not techs and profile.get("top_language"):
        techs = [str(profile["top_language"])]
    topics = list(profile.get("interests") or [])
    organizations: list[dict[str, Any]] = []
    set_aside: list[dict[str, Any]] = []
    catalog: dict[str, Any] = {}
    if techs or topics:
        # Two spares, so an organization that is sitting out can be replaced.
        matched = toolkit.match_orgs(
            technologies=techs or None, topics=topics or None, limit=limit + 2
        )
        checked = toolkit.check_participation(matched["organizations"], check=limit)
        organizations = checked[:limit]
        set_aside = [
            {"name": org["name"], **org["participation"]}
            for org in checked[limit:]
            if (org.get("participation") or {}).get("status") == "not_taking_part"
        ]
        catalog = matched["catalog"]
    shortlisted = toolkit.progress.load().shortlisted_orgs
    return {
        "profile": profile,
        "catalog": catalog,
        "organizations": organizations,
        "set_aside": set_aside,
        "shortlisted": shortlisted,
        "next_steps": next_steps_after_start(organizations, shortlisted),
    }


def shortlist(toolkit: GSoCToolkit, result: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """Shortlist organizations picked from a `first_run` result and refresh its next steps."""
    for name in names:
        toolkit.progress.shortlist_org(name)
    shortlisted = toolkit.progress.load().shortlisted_orgs
    return {
        **result,
        "shortlisted": shortlisted,
        "next_steps": next_steps_after_start(result["organizations"], shortlisted),
    }


def next_steps_after_start(
    organizations: list[dict[str, Any]], shortlisted: list[str]
) -> list[dict[str, str]]:
    """Three steps that turn a fresh profile into a shortlist, a repository, and a habit."""
    ask = {"title": "Whenever you are unsure what to do, ask", "command": "git-into-gsoc next"}
    if shortlisted:
        name = shortlisted[0]
        return [
            {
                "title": f"Read {name} closely: ideas page, chat channels, past projects",
                "command": f'git-into-gsoc org "{name}"',
            },
            {
                "title": "See which of its repositories mentors work in and welcome newcomers",
                "command": f'git-into-gsoc repos "{name}"',
            },
            ask,
        ]
    if organizations:
        name = organizations[0]["name"]
        return [
            {
                "title": f"Read {name} closely: ideas page, chat channels, past projects",
                "command": f'git-into-gsoc org "{name}"',
            },
            {
                "title": "Shortlist it if it fits, so the tool can follow it for you",
                "command": f'git-into-gsoc org "{name}" --shortlist',
            },
            ask,
        ]
    return [
        {
            "title": "Browse organizations by a topic you care about",
            "command": "git-into-gsoc orgs --topics science",
        },
        ask,
    ]
