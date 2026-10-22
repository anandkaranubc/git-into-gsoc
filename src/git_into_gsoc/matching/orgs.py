"""What each organization works on, with the source of every claim.

An organization's profile is a set of concepts, each with a strength from 0
to 1 and the evidence behind it. A tag the organization chose counts most; a
word in its description, an ideas page, or its repositories counts less, and
more when several sources agree. Strengths combine like independent votes:
two sources at 0.6 give 0.84, never more than 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from git_into_gsoc.matching.concepts import (
    CATEGORY_CONCEPTS,
    broader_of,
    find_concepts,
    find_tag_concepts,
    label,
)
from git_into_gsoc.matching.signals import language_concepts
from git_into_gsoc.models import OrgSummary

TAG = 1.0
TAGLINE = 0.9
CATEGORY = 0.45
DESCRIPTION_ONE, DESCRIPTION_MANY = 0.55, 0.7
IDEA_SKILL_ONE, IDEA_SKILL_MANY = 0.6, 0.85
IDEA_TEXT = {1: 0.25, 2: 0.45}
IDEA_TEXT_MANY = 0.6
REPO_LANG = ((0.25, 0.85), (0.1, 0.6))
REPO_LANG_FEW = 0.35
REPO_TOPIC = {1: 0.25, 2: 0.45}
REPO_TOPIC_MANY = 0.6
BROADER = 0.85  # a narrower concept counts toward its broader one


@dataclass(frozen=True)
class Evidence:
    concept: str
    strength: float
    source: str  # tag | tagline | category | description | ideas | github
    detail: str


@dataclass
class OrgProfile:
    org: OrgSummary
    strength: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    text: str = ""
    tags: tuple[str, ...] = ()
    ideas: dict[str, Any] = field(default_factory=dict)
    github: dict[str, Any] = field(default_factory=dict)
    participation: dict[str, Any] = field(default_factory=dict)

    def add(self, concept: str, strength: float, source: str, detail: str) -> None:
        if strength <= 0:
            return
        self.evidence.setdefault(concept, []).append(Evidence(concept, strength, source, detail))

    def sources(self, concept: str) -> int:
        """How many independent kinds of evidence support a concept."""
        return len({e.source for e in self.evidence.get(concept, [])})

    def finish(self) -> None:
        combined: dict[str, float] = {}
        for concept, items in self.evidence.items():
            miss = 1.0
            for item in items:
                miss *= 1.0 - min(1.0, item.strength)
            combined[concept] = 1.0 - miss
            self.evidence[concept] = sorted(items, key=lambda e: -e.strength)
        # A narrower concept supports its broader one (Django -> Python, ROS ->
        # robotics), two levels up at most.
        for _ in range(2):
            for concept, value in list(combined.items()):
                for parent in broader_of(concept):
                    lifted = BROADER * value
                    if lifted > combined.get(parent, 0.0):
                        combined[parent] = lifted
        self.strength = combined

    def best_evidence(self, concept: str, n: int = 2) -> list[str]:
        """Plain-language evidence for a concept, its own or through a narrower one."""
        own = [e.detail for e in self.evidence.get(concept, [])[:n]]
        if own:
            return own
        for child, items in self.evidence.items():
            if concept in broader_of(child) and items:
                return [f"{label(child)}: {items[0].detail}"]
        return []


def _tag_detail(kind: str, tag: str) -> str:
    return f"{kind} tag '{tag}' on its official GSoC listing"


def build_org_profile(
    org: OrgSummary,
    *,
    description: str = "",
    signals: dict[str, Any] | None = None,
    signals_year: int | None = None,
) -> OrgProfile:
    """An organization's profile from its listing, its long description, and the
    shipped evidence (ideas page and repositories) for it, when there is any."""
    signals = signals or {}
    ideas = dict(signals.get("ideas") or {})
    github = dict(signals.get("github") or {})
    tags = tuple(t.strip() for t in [*org.technologies, *org.topics] if t and t.strip())
    titles = " ".join(str(i.get("t") or "") for i in ideas.get("ideas") or [])
    profile = OrgProfile(
        org=org,
        text=" ".join([org.name, org.description, description, " ".join(tags), titles]).lower(),
        tags=tuple(t.lower() for t in tags),
        ideas=ideas,
        github=github,
        participation=dict(signals.get("participation") or {}),
    )
    for kind, values in (("tech", org.technologies), ("topic", org.topics)):
        for tag in values:
            # Both forms: "cloud-native" reads as "cloud native", but "r-project" and
            # "objective-c" are spellings only with the hyphen.
            found = {**find_tag_concepts(tag.replace("-", " ")), **find_tag_concepts(tag)}
            for concept in found:
                profile.add(concept, TAG, "tag", _tag_detail(kind, tag))
    for category in (org.category or "").split(","):
        name = category.strip()
        for concept in CATEGORY_CONCEPTS.get(name.lower(), ()):
            profile.add(concept, CATEGORY, "category", f"official category '{name}'")
    for concept in find_concepts(org.description):
        profile.add(concept, TAGLINE, "tagline", "its official GSoC tagline")
    for concept, count in find_concepts(description).items():
        strength = DESCRIPTION_MANY if count >= 2 else DESCRIPTION_ONE
        profile.add(concept, strength, "description", "its official GSoC description")

    year = f"{signals_year} " if signals_year else ""
    real = int(ideas.get("count") or 0)
    blocks = int(ideas.get("blocks") or real)
    # Counts are over the blocks the page was split into; call them ideas only when
    # every block was an idea, so a fraction never reads "11 of 2".
    unit = f"{year}ideas" if blocks == real else f"parts of its {year}ideas page"
    for concept, count in (ideas.get("skills") or {}).items():
        strength = IDEA_SKILL_MANY if count >= 2 else IDEA_SKILL_ONE
        profile.add(
            concept,
            strength,
            "ideas",
            f"listed as a skill in {min(count, blocks)} of {blocks} {unit}",
        )
    for concept, count in (ideas.get("mentions") or {}).items():
        if concept in (ideas.get("skills") or {}):
            continue
        strength = IDEA_TEXT.get(count, IDEA_TEXT_MANY)
        profile.add(concept, strength, "ideas", f"named in {min(count, blocks)} of {blocks} {unit}")

    active = int(github.get("active_repos") or 0)
    if active:
        for concept, count in language_concepts(github.get("languages") or {}).items():
            share = count / active
            strength = next((s for cut, s in REPO_LANG if share >= cut), REPO_LANG_FEW)
            profile.add(
                concept,
                strength,
                "github",
                f"main language of {count} of its {active} GitHub repositories pushed in the "
                "last year",
            )
        for concept, count in (github.get("concepts") or {}).items():
            strength = REPO_TOPIC.get(count, REPO_TOPIC_MANY)
            profile.add(
                concept,
                strength,
                "github",
                f"in the topics or descriptions of {count} of its active GitHub repositories",
            )
    profile.finish()
    return profile


def idf_table(profiles: list[OrgProfile], threshold: float = 0.5) -> dict[str, float]:
    """How rare each concept is among organizations: rare skills say more about fit."""
    n = len(profiles)
    df: dict[str, int] = {}
    for profile in profiles:
        for concept, value in profile.strength.items():
            if value >= threshold:
                df[concept] = df.get(concept, 0) + 1
    return {c: math.log((n + 1) / (d + 1)) + 1.0 for c, d in df.items()}
