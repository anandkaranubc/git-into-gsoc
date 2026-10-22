"""Order beginner issues for one contributor, and say what in each fits them.

Availability and the beginner score (labels, freshness, clarity) come first;
this only adds what the person brings. An issue that names a skill they have
or a subject they care about is easier to start and more likely to hold their
interest, the finding behind personalised good first issue recommenders
(Xiao et al., ASE 2023). People new to open source get a small lift for
documentation and test issues, the usual first step.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.github.repos import is_beginner_label
from git_into_gsoc.matching.concepts import SKILL, find_concepts, find_tag_concepts, kind_of, label
from git_into_gsoc.matching.ideas import known_skills, wanted_domains
from git_into_gsoc.matching.profile import ContributorProfile

SKILL_BONUS = 6.0
INTEREST_BONUS = 5.0
GENTLE_BONUS = 5.0
_GENTLE_LABELS = {"documentation", "docs", "tests", "testing", "good first issue"}
_GENTLE_WORDS = ("documentation", "docs", "typo", "readme", "test", "tests")


# An unticked box in an issue template ("- [ ] Accessibility") names an area the issue
# is not about, so it must not count as a subject. Items are a few words at most.
_UNTICKED = re.compile(r"[-*]?\s*\[ \]\s*[^\s\[\]]+(?:[ \t]+[^\s\[\]*-]+){0,2}")


# Repositories for an event or its notes ("disc-unconference-2023-projects",
# "hackathon-2024"), not code a contributor can build on.
_EVENT_REPO = re.compile(
    r"(?:^|[-_.])(?:unconference|hackathon|conference|summit|meetup|workshop|sprints?|"
    r"events?|talks|slides)(?:$|[-_.])|(?:^|[-_.])20\d\d(?:$|[-_.])",
    re.I,
)


# Repositories for governance, tests, or experiments, not a project's code.
_NOT_CODE_REPO = re.compile(
    r"(?:^|[-_.])(?:tsc|governance|steering|working-groups?|rfcs?|community|meta|admin|"
    r"test-actions|sandbox|playground|demo|scratch)(?:$|[-_.])|^\.github$|^test-",
    re.I,
)


def is_not_code_repo(full_name: str) -> bool:
    """True for a governance, test, or sandbox repository."""
    return bool(_NOT_CODE_REPO.search(str(full_name).split("/")[-1]))


def is_event_repo(full_name: str) -> bool:
    """True for a repository named after an event or a year, rather than a project."""
    return bool(_EVENT_REPO.search(str(full_name).split("/")[-1]))


# Titles and labels of things that are not a first task: announcements, roadmaps,
# trackers, epics, "what can I work on?" lists, governance and release chores.
_NOT_A_TASK_RE = re.compile(
    r"\b(?:gsoc|google summer of code|roadmap|tracker|tracking issue|epic|umbrella issue|"
    r"meta issue|what can i work on|announcement|no gsoc|working group|release [0-9.]+|"
    r"publish .* to (?:maven|pypi|npm)|request for comments|rfc|"
    # Calls for testing or feedback: open-ended, with nothing to finish.
    r"find bugs|call for (?:testing|testers|feedback)|help (?:us )?test|testers wanted|"
    r"feedback wanted|bug bash)\b",
    re.I,
)
_NOT_A_TASK_LABELS = frozenset(
    {"epic", "tracking", "meta", "roadmap", "announcement", "discussion", "question", "rfc"}
)
# Labels that say an issue is beyond a first task or not ready to be worked on.
_NOT_READY_RE = re.compile(
    r"\b(?:intermediate|advanced|hard|difficult|expert|"
    r"can'?t reproduce|cannot reproduce|needs? (?:repro|reproduction|info|more info|"
    r"triage|decision|design|discussion)|waiting|blocked|on hold|duplicate|invalid|wontfix|"
    r"won't fix|stale)\b",
    re.I,
)
# Medium difficulty ("E-Medium", "difficulty: medium"), but not a medium priority.
_MEDIUM_RE = re.compile(r"^(?:e-|difficulty[:/ -]*|level[:/ -]*|effort[:/ -]*)?medium$", re.I)
OLD_ISSUE_YEARS = 3
# Claims a curated first-task list leaves alone, though `issue` calls the older ones
# stale: a newcomer's first comment should not land on someone else's work. A single
# old ask is not one of them; a blind reviewer still judged such issues good.
GRANTED_DAYS = 180
CROWDED_ASKS = 3


def starter_problem(issue: dict[str, Any], person: ContributorProfile) -> str | None:
    """Why an issue is not a good first task for this person, or None when it may be."""
    title = str(issue.get("title") or "")
    labels = {str(lab).lower() for lab in issue.get("labels") or []}
    if is_not_code_repo(str(issue.get("repo") or "")):
        return "in a governance, test, or sandbox repository"
    body = str(issue.get("body_excerpt") or "")
    if re.search(
        r"\breserved for\b|\bassigned to @|\bi(?:'m| am) working on (?:this|it)\b", body, re.I
    ):
        return "reserved for someone or already being worked on"
    if _NOT_A_TASK_RE.search(title) or labels & _NOT_A_TASK_LABELS:
        return "an announcement, roadmap, tracker, or call for testing rather than a task"
    not_ready = next(
        (lab for lab in labels if _NOT_READY_RE.search(lab) or _MEDIUM_RE.match(lab)), None
    )
    if not_ready:
        return f"labelled '{not_ready}'"
    if labels and not any(is_beginner_label(lab) for lab in labels):
        # In blind reviews, issues labelled only "help wanted" were mostly too big,
        # claimed, or unsettled: 1 of 12 was a good first task.
        return "has no beginner label" + (", only 'help wanted'" if "help wanted" in labels else "")
    claims = (issue.get("assessment") or {}).get("claims") or []
    asked = _claim_problem(claims, author=str(issue.get("author") or ""))
    if asked:
        return asked
    created = str(issue.get("created_at") or "")[:4]
    if created.isdigit() and int(created) <= datetime.now(UTC).year - OLD_ISSUE_YEARS:
        return f"open since {created}"
    named = set(find_concepts(" ".join([title, str(issue.get("body_excerpt") or "")])))
    for lab in issue.get("labels") or []:
        named.update(find_tag_concepts(str(lab)))
    skills = {c for c in named if kind_of(c) == SKILL and c not in {"git", "github actions"}}
    known = known_skills(person)
    if skills and known and not skills & known:
        return (
            "needs " + ", ".join(sorted(label(c) for c in skills)[:2]) + ", which you did not list"
        )
    return None


def _claim_problem(claims: list[dict[str, Any]], *, author: str = "") -> str | None:
    """Why the people who asked for an issue keep it off a first-task list, if they do."""
    if len(claims) >= CROWDED_ASKS:
        return f"{len(claims)} people have asked to work on it"
    if author and any(str(c.get("login") or "").lower() == author.lower() for c in claims):
        return "its author said they are working on it"
    granted = [int(c.get("days_ago") or 0) for c in claims if c.get("granted")]
    if granted and min(granted) <= GRANTED_DAYS:
        return f"a maintainer gave it to someone {min(granted)} days ago"
    return None


def issue_fit(issue: dict[str, Any], person: ContributorProfile) -> tuple[float, list[str]]:
    """Extra points and plain reasons for one issue (a dict as find_issues returns)."""
    labels = [str(lab) for lab in issue.get("labels") or []]
    body = _UNTICKED.sub(" ", str(issue.get("body_excerpt") or ""))
    text = " ".join([str(issue.get("title") or ""), body])
    named = set(find_concepts(text))
    for lab in labels:
        named.update(find_tag_concepts(lab))
    reasons: list[str] = []
    bonus = 0.0
    skills = sorted(c for c in named if c in known_skills(person))
    if skills:
        bonus += SKILL_BONUS
        reasons.append("Names " + ", ".join(label(c) for c in skills[:3]) + ", which you know")
    topics = sorted(c for c in named if c in wanted_domains(person))
    if topics:
        bonus += INTEREST_BONUS
        reasons.append(
            "About " + ", ".join(label(c) for c in topics[:2]) + ", one of your interests"
        )
    if person.experience == "new":
        lowered = {lab.lower() for lab in labels}
        title = str(issue.get("title") or "").lower()
        if lowered & _GENTLE_LABELS - {"good first issue"} or any(
            word in title.split() for word in _GENTLE_WORDS
        ):
            bonus += GENTLE_BONUS
            reasons.append("A documentation or test change: a gentle first pull request")
    return bonus, reasons


def personalize(
    issues: list[dict[str, Any]], person: ContributorProfile, *, reorder: bool = True
) -> list[dict[str, Any]]:
    """Issues with a `fits_you` list.

    With `reorder`, verified free issues come first, then by score plus fit. Without
    it the caller's order stands (find_issues puts an organization's own
    repositories before the ones its ideas page links to).
    """
    if person.empty and person.experience is None:
        return issues
    scored = []
    for position, issue in enumerate(issues):
        bonus, reasons = issue_fit(issue, person)
        scored.append((issue | {"fits_you": reasons}, bonus, position))
    if reorder:
        scored.sort(
            key=lambda item: (
                item[0].get("availability") != "available",
                -(float(item[0].get("beginner_score") or 0.0) + item[1]),
                item[2],
            )
        )
    return [issue for issue, _, _ in scored]
