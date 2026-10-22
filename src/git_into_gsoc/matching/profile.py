"""What a contributor told us, read into concepts the ranking can use."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from git_into_gsoc.matching.concepts import DOMAIN, SKILL, broader_of, kind_of, label, resolve
from git_into_gsoc.validation import plain_skill

EXPERIENCE_LEVELS = ("new", "some", "experienced")
EXPERIENCE_HELP = (
    "new: never had a pull request merged in someone else's project; "
    "some: a few merged; experienced: many, or you maintain a project"
)


# Skill concepts that are languages GitHub classifies repositories by, with the name
# its search uses.
GITHUB_LANGUAGES = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "kotlin": "kotlin",
    "c": "c",
    "c++": "c++",
    "c#": "csharp",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
    "dart": "dart",
    "r": "r",
    "julia": "julia",
    "haskell": "haskell",
    "scala": "scala",
    "ocaml": "ocaml",
    "elixir": "elixir",
    "clojure": "clojure",
    "lua": "lua",
    "perl": "perl",
    "fortran": "fortran",
    "assembly": "assembly",
    "shell": "shell",
    "html": "html",
    "css": "css",
    "matlab": "matlab",
    "zig": "zig",
    "objective-c": "objective-c",
    "solidity": "solidity",
    "tcl": "tcl",
}


def languages_of(person: ContributorProfile, limit: int = 4) -> list[str]:
    """GitHub language names for what the person knows, frameworks traced to their language."""
    out: list[str] = []

    def add(concept: str, depth: int = 0) -> None:
        if concept in GITHUB_LANGUAGES:
            if GITHUB_LANGUAGES[concept] not in out:
                out.append(GITHUB_LANGUAGES[concept])
            return
        if depth < 2:
            for parent in broader_of(concept):
                add(parent, depth + 1)

    for want in person.skills:
        for concept in want.concepts:
            add(concept)
    return out[:limit]


def experience_from_merged(count: int | None) -> str | None:
    """A level from merged pull requests in other people's projects (None: unknown)."""
    if count is None:
        return None
    if count == 0:
        return "new"
    return "some" if count < 10 else "experienced"


def effective_experience(saved: dict[str, object]) -> tuple[str | None, str | None]:
    """The level to use and where it came from: what the person said wins over GitHub."""
    stated = str(saved.get("experience") or "").lower()
    if stated in EXPERIENCE_LEVELS:
        return stated, "you said so"
    merged = saved.get("merged_prs_elsewhere")
    if isinstance(merged, int):
        level = experience_from_merged(merged)
        plural = "s" if merged != 1 else ""
        return level, (
            f"{merged} merged pull request{plural} in other people's repositories on GitHub"
        )
    return None, None


@dataclass(frozen=True)
class Want:
    """One skill or interest as typed, and what it was read as."""

    raw: str
    concepts: tuple[str, ...]
    corrected_from: str | None = None
    # Words that narrow the subject: "notation" in "music notation", which reads as
    # music. An organization that names one of them is the closer match.
    qualifiers: tuple[str, ...] = ()

    @property
    def literal(self) -> str | None:
        """The plain word to search for when it names no known concept."""
        return None if self.concepts else self.raw.strip().lower() or None

    @property
    def shown(self) -> str:
        return " / ".join(label(c) for c in self.concepts) if self.concepts else self.raw


@dataclass
class ContributorProfile:
    skills: list[Want] = field(default_factory=list)
    interests: list[Want] = field(default_factory=list)
    # Domains a skill points to (PyTorch -> machine learning), used lightly when
    # someone gives skills but no interests.
    implied_interests: list[Want] = field(default_factory=list)
    experience: str | None = None
    hours_per_week: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.skills or self.interests)

    def summary(self) -> dict[str, object]:
        return {
            "skills": [w.shown for w in self.skills],
            "interests": [w.shown for w in self.interests],
            "experience": self.experience,
            "hours_per_week": self.hours_per_week,
            "read_as": self.notes,
        }


def _split(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        for part in re.split(r"\s*[,;]\s*", str(value)):
            cleaned = plain_skill(part).strip()
            if cleaned and cleaned.lower() not in {o.lower() for o in out}:
                out.append(cleaned)
    return out


# Words that never narrow a subject on their own.
_PLAIN_WORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "into",
        "from",
        "about",
        "open",
        "source",
        "software",
        "tools",
        "tool",
        "apps",
        "app",
        "applications",
        "application",
        "development",
        "developer",
        "programming",
        "projects",
        "project",
        "systems",
        "system",
        "things",
        "stuff",
        "work",
        "working",
        "related",
        "based",
        "using",
        "technology",
        "technologies",
        "real",
        "people",
        "user",
        "users",
        "help",
        "helping",
    }
)


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith("ss") else word


def _qualifiers(phrase: str, concepts: tuple[str, ...]) -> tuple[str, ...]:
    """Words of a phrase beyond the names of the subjects it was read as.

    A hyphenated word stays whole ("real-time"), and two words that spell a
    subject's name ("front end") are that name, not a narrower word.
    """
    if not concepts or any(kind_of(c) != DOMAIN for c in concepts):
        return ()
    named = {
        _stem(w)
        for c in concepts
        for w in re.findall(r"[a-z0-9]+", f"{c} {label(c)}".lower().replace("-", ""))
    }
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", phrase.lower())
    out: list[str] = []
    skip = False
    for here, word in enumerate(words):
        if skip:
            skip = False
            continue
        following = words[here + 1] if here + 1 < len(words) else ""
        if following and _stem(word + following) in named:
            skip = True
            continue
        stem = _stem(word)
        if (
            len(stem.replace("-", "")) >= 4
            and stem not in _PLAIN_WORDS
            and stem.replace("-", "") not in named
            and stem not in out
        ):
            out.append(stem)
    return tuple(out)


def _wants(values: list[str], notes: list[str]) -> list[Want]:
    wants: list[Want] = []
    seen: dict[tuple[str, ...], int] = {}
    for raw in values:
        found = resolve(raw)
        key = found.concepts or (raw.lower(),)
        qualifiers = _qualifiers(found.corrected_from or raw, found.concepts)
        if key in seen:
            # "query engines" after "database internals": one subject, more words for it.
            first = wants[seen[key]]
            more = tuple(q for q in qualifiers if q not in first.qualifiers)
            if more:
                wants[seen[key]] = replace(first, qualifiers=first.qualifiers + more)
            continue
        seen[key] = len(wants)
        if found.corrected_from:
            notes.append(f"Read '{raw}' as '{found.corrected_from}'.")
        wants.append(
            Want(
                raw=raw,
                concepts=found.concepts,
                corrected_from=found.corrected_from,
                qualifiers=qualifiers,
            )
        )
    return wants


def build_profile(
    *,
    technologies: list[str] | None = None,
    interests: list[str] | None = None,
    experience: str | None = None,
    hours_per_week: int | None = None,
) -> ContributorProfile:
    """Read typed skills and interests into concepts.

    A word given as a technology that names a domain ("web", "robotics") is
    treated as an interest, and the other way round, so a person never has to
    know which box a word belongs in.
    """
    notes: list[str] = []
    skills: list[Want] = []
    wants: list[Want] = []
    for want in _wants(_split(technologies), notes):
        kinds = {kind_of(c) for c in want.concepts}
        (wants if kinds == {DOMAIN} else skills).append(want)
    for want in _wants(_split(interests), notes):
        kinds = {kind_of(c) for c in want.concepts}
        (skills if kinds == {SKILL} and want.concepts else wants).append(want)
    implied: list[Want] = []
    have = {c for w in wants for c in w.concepts}
    for want in skills:
        for concept in want.concepts:
            for parent in broader_of(concept):
                if kind_of(parent) == DOMAIN and parent not in have:
                    have.add(parent)
                    implied.append(Want(raw=label(parent), concepts=(parent,)))
    level = (experience or "").strip().lower() or None
    if level is not None and level not in EXPERIENCE_LEVELS:
        level = None
    hours = int(hours_per_week) if hours_per_week else None
    return ContributorProfile(
        skills=skills,
        interests=wants,
        implied_interests=implied,
        experience=level,
        hours_per_week=hours if hours and hours > 0 else None,
        notes=notes,
    )
