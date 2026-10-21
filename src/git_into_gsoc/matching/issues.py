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
from typing import Any

from git_into_gsoc.matching.concepts import find_concepts, find_tag_concepts, label
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


def is_event_repo(full_name: str) -> bool:
    """True for a repository named after an event or a year, rather than a project."""
    return bool(_EVENT_REPO.search(str(full_name).split("/")[-1]))


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
