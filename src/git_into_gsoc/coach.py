"""Turn program phase, saved progress, and live checks into the next few actions.

Pure functions only: the service layer gathers the data and this module decides
what a contributor should do now. Every action carries a command they can run.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.models import ProgressState

DEADLINE_HORIZON_DAYS = 45
SOON_DAYS = 14
PROPOSAL_PHASES = {"org_exploration", "proposal_window", "proposal_review"}
PROPOSAL_KEYS = {"contributor_proposals_open", "proposal_deadline"}
LOG_REMINDER_DAYS = 7
ACTIVE_PHASES = {"community_bonding", "coding"}


def _action(title: str, command: str, why: str) -> dict[str, str]:
    return {"title": title, "command": command, "why": why}


def upcoming_deadlines(
    program: dict[str, Any], *, horizon_days: int = DEADLINE_HORIZON_DAYS
) -> list[dict[str, Any]]:
    """Milestones within the horizon, nearest first."""
    out = []
    for item in program.get("timeline") or []:
        days = int(item.get("days_until") or 0)
        if item.get("status") in {"upcoming", "today"} and days <= horizon_days:
            out.append(item)
    out.sort(key=lambda m: int(m.get("days_until") or 0))
    return out[:4]


BUDGET_HORIZON_DAYS = 120

# From the GSoC FAQ: projects are about 90, 175, or 350 hours, and the coding
# period runs 8 to 22 weeks (past the standard end only if the mentor agrees).
PROJECT_HOURS = {"small": 90, "medium": 175, "large": 350}
LONGEST_CODING_WEEKS = 22
STANDARD_CODING_WEEKS = 12
GSOC_FAQ_URL = "https://developers.google.com/open-source/gsoc/faq"
# Our advice, not a GSoC rule: leave this many weeks before the longest period for
# exams and setbacks.
SPARE_WEEKS = 4


def project_weeks(hours: int) -> dict[str, int]:
    """Weeks each project size takes at these hours a week, rounded up."""
    return {size: -(-total // hours) for size, total in PROJECT_HOURS.items()}


def fitting_size(hours: int) -> dict[str, list[str]]:
    """Project sizes by how they fit these hours: `comfortable` (with SPARE_WEEKS to
    spare), `tight` (within the longest period but with no room left), `too_long`.

    One rule for `start`'s hours note and the learning path, so one person never gets
    two answers.
    """
    out: dict[str, list[str]] = {"comfortable": [], "tight": [], "too_long": []}
    for size, weeks in project_weeks(hours).items():
        if weeks > LONGEST_CODING_WEEKS:
            out["too_long"].append(size)
        elif weeks > LONGEST_CODING_WEEKS - SPARE_WEEKS:
            out["tight"].append(size)
        else:
            out["comfortable"].append(size)
    return out


def hours_note(hours_per_week: Any) -> str | None:
    """Which project sizes fit the hours someone has, or None when all of them do."""
    try:
        hours = int(hours_per_week or 0)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    weeks = project_weeks(hours)
    fit = fitting_size(hours)
    too_long = fit["too_long"]
    if not too_long and not fit["tight"]:
        return None
    small = weeks["small"]
    if "small" in too_long:
        return (
            f"At {hours} hours a week, even a small project (about 90 hours) takes about "
            f"{small} weeks, longer than the longest coding period ({LONGEST_CODING_WEEKS} "
            "weeks). You can still contribute now and apply when you have more time. "
            f"Source: {GSOC_FAQ_URL}"
        )
    # What fits first, then what would only just fit (advice), then what does not
    # (Google's limit).
    parts: list[str] = []
    for size in fit["comfortable"]:
        lead = "a small project" if size == "small" else f"a {size} one"
        clause = f"{lead} (about {PROJECT_HOURS[size]} hours) fits in about {weeks[size]} weeks"
        if weeks[size] > STANDARD_CODING_WEEKS:
            # Past the standard period only on a longer timeline the mentor agrees to.
            clause += (
                f", longer than the standard {STANDARD_CODING_WEEKS}, so agree a longer "
                "timeline with your mentor"
            )
        parts.append(clause)
    for size in fit["tight"]:
        lead = "a small project" if size == "small" else f"a {size} one"
        parts.append(
            f"{lead} (about {PROJECT_HOURS[size]} hours) would take about {weeks[size]} weeks, "
            "the longest period allowed, which leaves no room for exams or setbacks"
        )
    if too_long:
        sizes = " and ".join(too_long)
        parts.append(
            f"{sizes} projects would not fit in the longest coding period "
            f"({LONGEST_CODING_WEEKS} weeks, and only if your mentor agrees)"
        )
    choose = " or ".join(fit["comfortable"] or fit["tight"])
    return (
        f"At {hours} hours a week, " + "; ".join(parts) + f". Choose a {choose} idea and "
        f"state your hours in your proposal. Source: {GSOC_FAQ_URL}"
    )


def time_budget(
    state: ProgressState, program: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any] | None:
    """Hours available before the next milestone, split by what this phase needs.

    Uses the saved hours per week. The milestone is the proposal deadline when it
    is within the horizon, else the nearest upcoming milestone. None when there is
    nothing to plan against.
    """
    profile = state.profile or {}
    try:
        hours = int(profile.get("hours_per_week") or 0)
    except (TypeError, ValueError):
        hours = 0
    if hours <= 0:
        return None
    upcoming = [
        m
        for m in program.get("timeline") or []
        if m.get("status") in {"upcoming", "today"}
        and 0 < int(m.get("days_until") or 0) <= BUDGET_HORIZON_DAYS
    ]
    upcoming.sort(key=lambda m: int(m.get("days_until") or 0))
    target = next((m for m in upcoming if m.get("key") == "proposal_deadline"), None)
    target = target or (upcoming[0] if upcoming else None)
    if target is None:
        return None
    days = int(target.get("days_until") or 0)
    weeks = max(1, round(days / 7))
    total = hours * weeks
    phase_id = str((program.get("phase") or {}).get("id") or "")
    if (
        phase_id in {"proposal_window", "proposal_review"}
        or target.get("key") == "proposal_deadline"
    ):
        split = [
            ("Proposal: draft from the template, get mentor feedback, revise", 0.5),
            ("Keep contributing where you are applying", 0.3),
            ("Community: answer questions, review a pull request", 0.2),
        ]
    elif not state.phases.get("community"):
        split = [
            ("Community: read the channel, introduce yourself, ask one real question", 0.2),
            ("Set the project up and reproduce one issue", 0.5),
            ("Read the code and a few merged pull requests", 0.3),
        ]
    else:
        split = [
            ("Contribute: a small fix with a test, then answer review", 0.6),
            ("Read code and reviews around your change", 0.2),
            ("Community and the weekly note", 0.2),
        ]
    return {
        "hours_per_week": hours,
        "until": str(target.get("label") or target.get("key")),
        "days": days,
        "weeks": weeks,
        "hours_available": total,
        "official": bool(target.get("official")),
        "suggested_split": [{"what": what, "hours": round(total * share)} for what, share in split],
        "note": (
            "A budget, not a schedule: official dates win, and one small finished change "
            "beats a large unfinished one."
        ),
    }


def plan_actions(
    state: ProgressState,
    program: dict[str, Any],
    *,
    tracked_issues: list[dict[str, Any]],
    new_issues: list[dict[str, Any]],
    open_pull_requests: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    code_elsewhere: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """A short, ordered ladder of concrete next actions.

    `code_elsewhere` maps shortlisted organizations with no GitHub owner to where
    their code lives, so the repository and issue steps do not send someone to a
    GitHub-only command that cannot help.
    """
    now = now or datetime.now(UTC)
    profile = state.profile or {}
    github = str(profile.get("github") or "").strip()
    techs = list(profile.get("technologies") or [])
    orgs = list(state.shortlisted_orgs)
    repos = list(state.tracked_repos)
    # Tracking an issue means its repository is chosen, even if it was never tracked.
    for issue in state.tracked_issues:
        match = re.search(r"github\.com/([^/\s]+/[^/\s#]+)|^([\w.-]+/[\w.-]+)#", issue)
        repo = (match.group(1) or match.group(2)) if match else None
        if repo and repo.lower() not in {r.lower() for r in repos}:
            repos.append(repo)
    phase_id = str((program.get("phase") or {}).get("id") or "")
    deadlines = upcoming_deadlines(program, horizon_days=30)
    actions: list[dict[str, str]] = []

    for item in deadlines:
        if int(item.get("days_until") or 0) <= SOON_DAYS:
            label = str(item.get("label") or item.get("key"))
            days = int(item.get("days_until") or 0)
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            estimate = (
                "" if item.get("official") else " (estimated date; verify on the official site)"
            )
            actions.append(
                _action(
                    f"{label} {when}{estimate}",
                    "git-into-gsoc program",
                    "Plan around it now; the official timeline is the only source of truth.",
                )
            )

    # An open pull request that needs its author outranks everything but a deadline:
    # reviewers move on when a pull request goes quiet.
    for pr in (open_pull_requests or [])[:2]:
        if pr.get("status") == "needs_you":
            actions.append(
                _action(
                    f"Your pull request {pr['ref']} needs you: {pr['summary']}",
                    f"git-into-gsoc draft review-reply --repo {pr.get('repo') or 'owner/repo'}",
                    "Answering within a day keeps a review moving; the GSoC guide asks "
                    "contributors to finish what they start.",
                )
            )
        elif pr.get("follow_up"):
            actions.append(
                _action(
                    f"Follow up once on {pr['ref']}: {pr.get('quiet_days')} days without a reply",
                    f"git-into-gsoc draft question --repo {pr.get('repo') or 'owner/repo'}",
                    "One short, specific follow-up after about five days is expected; "
                    "more than one reads as pressure.",
                )
            )

    if not techs and not github:
        actions.append(
            _action(
                "Answer four questions so every recommendation fits you",
                "git-into-gsoc start",
                "It saves your profile, which recommendations, starter issues, and this "
                "command use.",
            )
        )

    if not orgs:
        command = (
            "git-into-gsoc recommend" if (techs or github) else "git-into-gsoc orgs --tech python"
        )
        actions.append(
            _action(
                "Shortlist 3 organizations that fit your skills",
                command + '   # then, for each: git-into-gsoc org "NAME" --shortlist',
                "Everything downstream (repos, issues, proposal) hangs off a shortlist.",
            )
        )
    elif not repos:
        first = orgs[0]
        elsewhere = (code_elsewhere or {}).get(first)
        why = "Mentors work in a few repos; the ideas page and beginner issues show which."
        if elsewhere:
            why = (
                f"{first} lists no GitHub organization. If repos says its code is elsewhere "
                f"({elsewhere}), pick the project an idea names there and save its link: "
                "git-into-gsoc progress track_repo --value LINK"
            )
        actions.append(
            _action(
                f"Pick the repository to start in at {first}",
                f'git-into-gsoc repos "{first}"   # then: git-into-gsoc repo owner/name --track',
                why,
            )
        )
    elif not state.phases.get("community") and not tracked_issues:
        first = orgs[0]
        actions.append(
            _action(
                f"Introduce yourself once, publicly, in {first}'s channel before claiming anything",
                f'git-into-gsoc org "{first}"   # channels; then: git-into-gsoc draft intro',
                "Every org admin guide says: talk to the org first. Mentors rank people "
                "they have spoken with. Mark it done with: "
                "git-into-gsoc progress complete_phase --phase community",
            )
        )
    elif not tracked_issues:
        repo = repos[0]
        if repo.startswith("http"):
            actions.append(
                _action(
                    f"Find a newcomer issue in {repo}",
                    "git-into-gsoc progress track_issue --value LINK   # once you pick one",
                    "This tool cannot search issues outside GitHub. Open the project's issue "
                    "list and filter by its newcomer label; for a GitLab issue, git-into-gsoc "
                    "issue LINK then checks its assignee and merge requests.",
                )
            )
        else:
            actions.append(
                _action(
                    f"Find a beginner issue that is actually free in {repo}",
                    f"git-into-gsoc issues --repo {repo} -n 5",
                    "Only issues with no assignee, open PR, or recent claim are worth your time.",
                )
            )
    else:
        free = [t for t in tracked_issues if t.get("availability") == "available"]
        elsewhere_issues = [
            t for t in tracked_issues if t.get("off_github") and t.get("availability") == "unknown"
        ]
        if not free and elsewhere_issues:
            link = elsewhere_issues[0]["url"]
            actions.append(
                _action(
                    "Check the issue you saved, then reproduce it and comment with a short plan",
                    link,
                    "It is not on GitHub, so this tool cannot check it: make sure nobody is "
                    "assigned or has a merge request open first.",
                )
            )
        elif free:
            ref = free[0]["ref"]
            actions.append(
                _action(
                    f"Reproduce {ref} and comment with a short plan",
                    f"git-into-gsoc issue {ref}",
                    "It is still free. Read the thread, reproduce, then say what you would change.",
                )
            )
        else:
            repo = repos[0] if repos else tracked_issues[0]["ref"].split("#")[0]
            command = (
                f"{repo}   # pick another newcomer issue there"
                if repo.startswith("http")
                else f"git-into-gsoc issues --repo {repo} -n 5"
            )
            actions.append(
                _action(
                    "Everything you tracked is taken or stale; pick another issue",
                    command,
                    "Do not compete for claimed issues; a free one gets you reviewed sooner.",
                )
            )

    if new_issues:
        newest = new_issues[0]
        actions.append(
            _action(
                f"{len(new_issues)} new beginner issue(s) appeared since your last check",
                f"git-into-gsoc issue {newest['repo']}#{newest['number']}",
                "New issues have no competition yet; check availability before commenting.",
            )
        )

    last_log = max((entry.at for entry in state.weekly_log), default=None)
    contributing = bool(repos or tracked_issues) or phase_id in ACTIVE_PHASES
    log_due = last_log is None or (now - last_log).days >= LOG_REMINDER_DAYS
    if contributing and log_due:
        actions.append(
            _action(
                "Write this week's note: goal, what happened, links, what is stuck",
                'git-into-gsoc log --goal "..." --done "..." --links URL --stuck "..." --next "..."',
                "A short weekly record is what mentors ask for and what your proposal draws on.",
            )
        )

    proposal_soon = phase_id in PROPOSAL_PHASES or any(
        d.get("key") in PROPOSAL_KEYS for d in deadlines
    )
    if proposal_soon and orgs:
        who = github or "YOUR_USERNAME"
        actions.append(
            _action(
                f"Check what evidence you have at {orgs[0]} before writing a proposal",
                f'git-into-gsoc contributions --github {who} --org "{orgs[0]}"',
                "Prior contributions and public discussion are what reviewers look for first.",
            )
        )
        if phase_id == "proposal_window":
            actions.append(
                _action(
                    "Draft with the organization's template, in your own words",
                    "git-into-gsoc proposal",
                    "Submit only on the official site, before the deadline in your timezone.",
                )
            )

    return actions[:6]
