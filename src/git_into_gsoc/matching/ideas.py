"""Which of an organization's project ideas fit a contributor, and what each would teach.

An idea names skills and a subject. Matching them against what the person
knows gives two honest lists: the skills they already have for it, and the
ones they would learn. Difficulty and size are only what the ideas page
states; nothing is guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from git_into_gsoc.coach import LONGEST_CODING_WEEKS, PROJECT_HOURS
from git_into_gsoc.matching.concepts import (
    DOMAIN,
    SKILL,
    broader_of,
    find_concepts,
    find_tag_concepts,
    kind_of,
    label,
    narrower_index,
)
from git_into_gsoc.matching.profile import ContributorProfile

# Skills almost every idea expects, which say nothing about fit.
_EVERYWHERE = {"git"}
_DIFFICULTY_FOR = {
    "new": {"easy": 1.0, "medium": 0.6, "hard": 0.1},
    "some": {"easy": 0.8, "medium": 1.0, "hard": 0.5},
    "experienced": {"easy": 0.5, "medium": 1.0, "hard": 1.0},
}


@dataclass
class IdeaFit:
    score: float
    have: list[str] = field(default_factory=list)
    to_learn: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    too_big: bool = False


def known_skills(person: ContributorProfile) -> set[str]:
    """What the person said they know, and what that implies (Django means Python).

    Not the other way round: knowing JavaScript is not knowing React.
    """
    known: set[str] = set()
    for want in person.skills:
        for concept in want.concepts:
            known.add(concept)
            known.update(broader_of(concept))
    # Only skills: React's broader "frontend" is a subject, not something one knows.
    return {c for c in known if kind_of(c) == SKILL}


def wanted_domains(person: ContributorProfile) -> set[str]:
    wanted: set[str] = set()
    for want in person.interests:
        for concept in want.concepts:
            wanted.add(concept)
            wanted.update(narrower_index().get(concept, ()))
    return wanted


def idea_concepts(
    *, skills: list[str] | None = None, text: str = "", known: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """Skill concepts and subject concepts an idea names (labelled skills first)."""
    found: dict[str, None] = dict.fromkeys(known or [])
    for skill in skills or []:
        found.update(dict.fromkeys(find_tag_concepts(skill)))
    found.update(dict.fromkeys(find_concepts(text)))
    skill_keys = [c for c in found if kind_of(c) == SKILL and c not in _EVERYWHERE]
    domain_keys = [c for c in found if kind_of(c) == DOMAIN]
    return skill_keys, domain_keys


_REQUIRED_RE = re.compile(
    r"\b(?:required|requires|require|must know|must have|mandatory|prerequisites?|"
    r"needed|is a must)\b",
    re.I,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Short skill names count in a requirement only with their usual capital letter, so
# "you are required to go through the docs" does not require Go.
_SHORT_SKILLS = {"C": "c", "R": "r", "Go": "go", "D": "d"}
_SHORT_RE = re.compile(r"(?<![\w+#])(C|R|Go|D)(?![\w+#])")


# Section headings and page furniture that idea parsers sometimes pick up as ideas.
_HEADING_WORDS = frozenset(
    {
        "description",
        "scope",
        "goal",
        "goals",
        "tests",
        "test",
        "testing",
        "skills",
        "mentors",
        "mentor",
        "background",
        "material",
        "materials",
        "learning material",
        "overview",
        "introduction",
        "requirements",
        "prerequisites",
        "timeline",
        "team",
        "faq",
        "contact",
        "contacting us",
        "starter kit",
        "expected impact",
        "expected results",
        "expected outcome",
        "expected outcomes",
        "deliverables",
        "brief explanation",
        "knowledge prerequisites",
        "contribution guidelines",
        "application process",
        "project application process",
        "mentorship and guidance",
        "general evaluation criteria",
        "domain-specific",
        "difficulty",
        "size",
    }
)
_HEADING_RE = re.compile(
    r"^(?:project\s*\d+|idea\s*\d+|benefit to .+|why .+\?|what is .+\?|"
    r"projects under other organizations|see the official timeline.*|.*\[taken.*\].*)$",
    re.I,
)
_EDIT_LINK_RE = re.compile(r"\[[^\]]*\]")


def is_real_idea(title: str, *, labelled: bool = False) -> bool:
    """False for a heading, a page fragment, or an idea marked as taken."""
    cleaned = _EDIT_LINK_RE.sub("", title).strip(" :-|.\u2014").lower()
    if not cleaned or cleaned in _HEADING_WORDS or _HEADING_RE.match(cleaned):
        return False
    if re.search(r"\btaken\b", title, re.I):
        return False
    # One or two words with no stated difficulty or size is usually a product name or
    # a heading ("Flutter", "Kotlin Help", "Apache Dubbo"), not an idea.
    return labelled or len(cleaned.split()) >= 3


def required_skills(text: str) -> list[str]:
    """Skill concepts named in sentences that say something is required."""
    found: dict[str, None] = {}
    for sentence in _SENTENCE_RE.split(text or ""):
        if not _REQUIRED_RE.search(sentence):
            continue
        found.update(dict.fromkeys(c for c in find_concepts(sentence) if kind_of(c) == SKILL))
        for match in _SHORT_RE.finditer(sentence):
            found.setdefault(_SHORT_SKILLS[match.group(1)], None)
    return [c for c in found if c not in _EVERYWHERE]


def fit_idea(
    person: ContributorProfile,
    *,
    skill_keys: list[str],
    domain_keys: list[str],
    difficulty: str | None = None,
    size: str | None = None,
) -> IdeaFit:
    known = known_skills(person)
    wanted = wanted_domains(person)
    have = [c for c in skill_keys if c in known]
    to_learn = [c for c in skill_keys if c not in known]
    topics = [c for c in domain_keys if c in wanted]
    score = 0.0
    if skill_keys:
        score += 0.5 * len(have) / len(skill_keys)
    if topics:
        score += 0.3
    level = person.experience or "some"
    notes: list[str] = []
    too_big = False
    if difficulty:
        score += 0.15 * _DIFFICULTY_FOR[level].get(difficulty, 0.5)
        notes.append(f"stated difficulty: {difficulty}")
    if size:
        hours = PROJECT_HOURS.get(size)
        notes.append(f"{size} ({hours} hours)" if hours else size)
        if person.hours_per_week and hours:
            if hours > person.hours_per_week * LONGEST_CODING_WEEKS:
                score -= 0.3
                too_big = True
                notes.append(f"too big for {person.hours_per_week} hours a week")
            else:
                score += 0.05
    return IdeaFit(
        score=round(score, 3),
        have=[label(c) for c in have],
        to_learn=[label(c) for c in to_learn][:4],
        topics=[label(c) for c in topics],
        notes=notes,
        too_big=too_big,
    )


def ideas_for(
    ideas: list[dict[str, Any]],
    person: ContributorProfile,
    *,
    year: int | None,
    source_url: str | None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """The ideas from a signals summary that fit best, with what each asks and teaches."""
    scored = []
    for idea in ideas:
        if not is_real_idea(
            str(idea.get("t") or ""), labelled=bool(idea.get("d") or idea.get("s"))
        ):
            continue
        keys = list(idea.get("k") or [])
        skill_keys, domain_keys = idea_concepts(known=keys)
        fit = fit_idea(
            person,
            skill_keys=skill_keys,
            domain_keys=domain_keys,
            difficulty=idea.get("d"),
            size=idea.get("s"),
        )
        if fit.score <= 0.15 or not (fit.have or fit.topics) or fit.too_big:
            continue
        scored.append((fit.score, str(idea.get("t") or ""), fit))
    scored.sort(key=lambda item: (-item[0], item[1]))
    out = []
    for _, title, fit in scored[:limit]:
        out.append(
            {
                "title": title,
                "year": year,
                "source": source_url,
                "you_have": fit.have,
                "you_would_learn": fit.to_learn,
                "matches_interests": fit.topics,
                "stated": fit.notes,
            }
        )
    return out
