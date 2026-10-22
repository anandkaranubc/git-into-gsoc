"""Rank organizations for one contributor, and say why with evidence.

Relevance decides the order: how well an organization's work matches the
person's interests, and how much of it uses the skills they have. A skill few
organizations use (Julia, Kotlin) says more about fit than one most use
(Python), so skills are weighted by rarity. Track record, project capacity,
and beginner readiness only break ties: together they can move an
organization by a fifth, never past a clearly better match.

The score orders results. It is not a probability of acceptance, and nothing
here estimates one: every reason given is a fact someone can check.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from git_into_gsoc.coach import LONGEST_CODING_WEEKS, PROJECT_HOURS
from git_into_gsoc.matching.concepts import (
    CONCEPTS,
    GENERIC_PARENTS,
    SKILL,
    broader_of,
    find_concepts,
    kind_of,
    label,
    narrower_index,
)
from git_into_gsoc.matching.orgs import OrgProfile, build_org_profile, idf_table
from git_into_gsoc.matching.profile import ContributorProfile, Want, build_profile
from git_into_gsoc.matching.signals import language_concepts
from git_into_gsoc.models import OrgSummary

# How much a match through a neighbouring concept counts.
VIA_BROADER_SKILL = 0.3  # wants React, the org uses JavaScript
VIA_BROADER_DOMAIN = 0.35  # wants computer vision, the org does machine learning
VIA_RELATED = 0.35  # wants astronomy, the org does physics
WORD_IN_TAG, WORD_IN_TEXT = 1.0, 0.6
# An organization named after something the person asked for (The Rust Foundation,
# LLVM, Open Robotics) is that thing's home; it gets this much extra relevance when
# its other evidence agrees.
NAME_BOOST = 0.1
# Interests and skills weigh the same (tuned on the dev half of evals/; see evals/README.md).
INTEREST_WEIGHT = 0.5
SYNERGY = 0.1
IMPLIED_WEIGHT = 0.15
# Skills are alternatives: someone who knows Python and R can work where either is
# used. The best match counts most; covering more of them, rare ones first, adds.
BEST_SKILL_WEIGHT = 0.5
# A concept several kinds of evidence agree on (tags, description, ideas, code) is
# central to an organization; one mentioned once may be a side interest.
CENTRALITY_FLOOR = 0.85
CENTRAL_SOURCES = 3
# An organization that lists many skills or subjects (a polyglot runtime, an umbrella)
# says less about each one than a focused organization does, as long documents do in
# search ranking. Matches are scaled by (median breadth / breadth) ** power, never up.
SKILL_BREADTH_POWER = 0.15
DOMAIN_BREADTH_POWER = 0.15
BREADTH_THRESHOLD = 0.5
# How far the tie-breakers can move a score: from x0.8 to x1.0.
PRIOR_FLOOR = 0.8
HARD_FOR_NEW = 0.85
# An organization that said it will not take part in the coming year goes far down.
SITTING_OUT = 0.3
TIME_MISFIT = 0.85
# Most of its active code is in a language the person did not list, so a tag naming
# theirs is likely a side project (tuned on the dev sets of evals/).
OTHER_MAIN_LANGUAGE = 0.95
MAIN_LANGUAGE_SHARE = 0.4
FAMILY_SKIP = frozenset({"html", "css"})
# "Most of its ideas need X" stays a caveat only. A x0.95 cost helped the dev sets but
# made both held-out sets worse (holdout2 and holdout3), so it was taken out.

# Beginner-labelled issues in a year below which the count says nothing useful.
MIN_LABELLED = 3
# How much a phrase's common concept counts against its rarest one (see match_term).
SPECIFIC_POWER = 1.0
FIT_STRONG, FIT_GOOD, FIT_MIN = 0.7, 0.45, 0.12
DIVERSITY = 0.08
STANDARD_WEEKS = 12
# From this many matching organizations, a word is broad enough to suggest narrower ones.
SHARPEN_AT = 25
# "music notation" reads as music: an organization whose own text never names
# "notation" matches it this much less. A word named by more than this share of
# organizations says too little to count.
QUALIFIER_MISS = 0.85
QUALIFIER_MAX_SHARE = 0.15


@dataclass
class TermMatch:
    want: Want
    strength: float
    how: str  # direct | broader | related | word | none
    via: str | None = None
    evidence: list[str] = field(default_factory=list)

    def reason(self, kind: str) -> str:
        shown = self.want.shown
        if self.how == "direct":
            return f"Uses {shown}" if kind == "skill" else f"Topic: {shown}"
        if self.how == "word":
            return f"Mentions {self.want.raw}"
        return f"Related {'skill' if kind == 'skill' else 'topic'}: {shown} (via {self.via})"


@dataclass
class OrgMatch:
    org: OrgSummary
    profile: OrgProfile
    score: float
    relevance: float
    fit: str | None
    skill_fit: float | None = None
    interest_fit: float | None = None
    skills: list[TermMatch] = field(default_factory=list)
    interests: list[TermMatch] = field(default_factory=list)
    readiness: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    skills_to_learn: list[str] = field(default_factory=list)
    extra_reasons: list[str] = field(default_factory=list)
    ideas_unread: bool = False

    @property
    def participation(self) -> dict[str, Any] | None:
        """The evidence file's statement about the coming year, when there is one."""
        said = self.profile.participation
        if said.get("status") and int(said.get("year") or 0) > 0:
            return {
                "status": said["status"],
                "url": said.get("url"),
                "checked": said.get("checked"),
            }
        return None

    def reasons(self) -> list[str]:
        """Short reasons: direct matches first, then matches through a neighbour."""
        terms = [("topic", t) for t in self.interests] + [("skill", t) for t in self.skills]
        direct = [t.reason(k) for k, t in terms if t.strength > 0 and t.how in {"direct", "word"}]
        nearby = [
            t.reason(k) for k, t in terms if t.strength > 0 and t.how not in {"direct", "word"}
        ]
        return [*self.extra_reasons, *direct, *nearby, *self.readiness[:3]]

    def evidence(self) -> list[str]:
        """Direct evidence first; a near match says plainly that it is not the thing."""
        direct: list[str] = []
        near: list[str] = []
        for kind, terms in (("Topic", self.interests), ("Skill", self.skills)):
            for term in terms:
                if term.strength <= 0 or not term.evidence:
                    continue
                detail = "; ".join(term.evidence)
                if term.how == "broader":
                    near.append(
                        f"{kind} {term.want.shown}: not named; it works on {term.via} "
                        f"more broadly ({detail})"
                    )
                elif term.how == "related":
                    near.append(
                        f"{kind} {term.want.shown}: not named; the nearest is {term.via} ({detail})"
                    )
                else:
                    direct.append(f"{kind} {term.want.shown}: {detail}")
        return [*direct, *near]


# ------------------------------------------------------------------ matching


@lru_cache(maxsize=1)
def _related_index() -> dict[str, tuple[str, ...]]:
    """Related links in both directions."""
    out: dict[str, set[str]] = {}
    for concept in CONCEPTS.values():
        for other in concept.related:
            out.setdefault(concept.key, set()).add(other)
            out.setdefault(other, set()).add(concept.key)
    return {k: tuple(sorted(v)) for k, v in out.items()}


def _word_pattern(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w+#]){re.escape(word)}(?![\w+#])")


def match_term(profile: OrgProfile, want: Want, idf: dict[str, float] | None = None) -> TermMatch:
    """How strongly an organization covers one thing the person asked for.

    With `idf`, a phrase that names several concepts ("audio machine learning") counts
    a match on its common one (machine learning) for less than one on its rare one.
    """
    best = TermMatch(want=want, strength=0.0, how="none")
    rarest = max((idf.get(c, 0.0) for c in want.concepts), default=0.0) if idf else 0.0

    def central(concept: str) -> float:
        share = min(1.0, profile.sources(concept) / CENTRAL_SOURCES)
        return profile.strength.get(concept, 0.0) * (
            CENTRALITY_FLOOR + (1 - CENTRALITY_FLOOR) * share
        )

    for concept in want.concepts:
        share = 1.0
        if idf and len(want.concepts) > 1 and rarest > 0:
            share = (idf.get(concept, rarest) / rarest) ** SPECIFIC_POWER
        own = central(concept) * share
        if own > best.strength:
            best = TermMatch(want, own, "direct", None, profile.best_evidence(concept))
        is_skill = kind_of(concept) == SKILL
        factor = VIA_BROADER_SKILL if is_skill else VIA_BROADER_DOMAIN
        for parent in broader_of(concept):
            # React counts through JavaScript, but Phoenix never through "backend";
            # and "science" or "web" is too broad to stand for any one interest.
            if (kind_of(parent) == SKILL) != is_skill or parent in GENERIC_PARENTS:
                continue
            value = factor * profile.strength.get(parent, 0.0) * share
            if value > best.strength:
                best = TermMatch(
                    want, value, "broader", label(parent), profile.best_evidence(parent)
                )
        # A neighbouring skill is not the skill (C is not assembly, Java is not Scala).
        for other in () if is_skill else _related_index().get(concept, ()):
            if kind_of(other) == SKILL:
                continue
            value = VIA_RELATED * profile.strength.get(other, 0.0) * share
            if value > best.strength:
                best = TermMatch(want, value, "related", label(other), profile.best_evidence(other))
    word = want.literal
    if word and len(word) > 2:
        pattern = _word_pattern(word)
        if any(pattern.search(tag) for tag in profile.tags):
            if best.strength < WORD_IN_TAG:
                best = TermMatch(want, WORD_IN_TAG, "word", None, [f"tag '{word}'"])
        elif pattern.search(profile.text) and best.strength < WORD_IN_TEXT:
            best = TermMatch(
                want, WORD_IN_TEXT, "word", None, [f"'{word}' appears in its listing or ideas"]
            )
    return best


def _weight(want: Want, idf: dict[str, float], ceiling: float) -> float:
    if not want.concepts:
        return ceiling
    return max(idf.get(c, ceiling) for c in want.concepts)


# ------------------------------------------------------------- tie-breakers


def _years_line(org: OrgSummary, reference_year: int) -> tuple[float, str | None]:
    years = sorted(set(org.years_active))
    recent = [y for y in years if reference_year - 4 <= y <= reference_year]
    streak = 0
    for year in range(reference_year, reference_year - 30, -1):
        if year in years:
            streak += 1
        elif year != 2016 - 1:
            # The shipped history starts in 2016, so a missing 2015 is unknown, not a
            # year the organization sat out.
            break
    if not years:
        return 0.0, None
    if streak >= 3:
        text = f"Took part in GSoC every year {reference_year - streak + 1}-{reference_year}"
    else:
        text = f"Took part in GSoC in {len(recent)} of the last 5 years ({len(years)} in total)"
    return len(recent) / 5.0, text


def _capacity(org: OrgSummary) -> tuple[float, str | None]:
    n = org.num_projects_latest
    if not n:
        return 0.0, None
    plural = "s" if n != 1 else ""
    return (
        min(1.0, math.log2(1 + n) / math.log2(26)),
        f"{n} contributor project{plural} accepted in {org.latest_year}",
    )


def _ideas_facts(profile: OrgProfile, year: int | None) -> tuple[float, list[str], dict[str, int]]:
    """Beginner readiness from the ideas page, the facts behind it, and stated difficulty."""
    ideas = profile.ideas
    count = int(ideas.get("count") or 0)
    if _poorly_split(ideas):
        count = 0  # "1 idea" beside 18 accepted projects would mislead; say it was unclear
    difficulty = {k: int(v) for k, v in (ideas.get("difficulty") or {}).items()}
    sizes = {k: int(v) for k, v in (ideas.get("size") or {}).items()}
    parts: list[float] = [1.0 if profile.org.guide_url else 0.0]
    facts: list[str] = []
    when = f"{year} " if year else ""
    if count:
        parts.append(1.0)
        line = f"{count} idea{'s' if count != 1 else ''} on its {when}ideas page"
        stated = sum(difficulty.values())
        if stated:
            spread = ", ".join(
                f"{difficulty[d]} {d}" for d in ("easy", "medium", "hard") if difficulty.get(d)
            )
            line += f"; of the {stated} that state a difficulty: {spread}"
        facts.append(line)
    elif ideas.get("url"):
        parts.append(0.3)
    stated = sum(difficulty.values())
    if stated >= 3:
        parts.append((difficulty.get("easy", 0) + difficulty.get("medium", 0)) / stated)
    sized = sum(sizes.values())
    if sized >= 3:
        parts.append((sizes.get("small", 0) + sizes.get("medium", 0)) / sized)
    return sum(parts) / len(parts), facts, difficulty


def _time_fit(hours: int | None, sizes: dict[str, int]) -> tuple[bool | None, str | None]:
    """Whether any idea size the org states fits these hours, within the longest coding period."""
    sized = sum(sizes.values())
    if not hours or sized < 3:
        return None, None
    fits = [s for s in sizes if PROJECT_HOURS.get(s, 10**6) <= hours * LONGEST_CODING_WEEKS]
    if not fits:
        biggest = min((PROJECT_HOURS[s] for s in sizes if s in PROJECT_HOURS), default=350)
        return False, (
            f"Its ideas that state a size are all {'/'.join(sorted(sizes))}; at {hours} hours a "
            f"week the smallest ({biggest} hours) takes more than {LONGEST_CODING_WEEKS} weeks"
        )
    comfortable = [s for s in sizes if PROJECT_HOURS.get(s, 10**6) <= hours * STANDARD_WEEKS]
    if comfortable:
        return True, None
    return True, (
        f"At {hours} hours a week its {'/'.join(sorted(fits))} ideas need a longer coding "
        "period than the standard 12 weeks; ask the mentors early"
    )


def _mostly_needs(profile: OrgProfile, person: ContributorProfile) -> list[str]:
    """Languages and frameworks at least half of its ideas list that the person lacks."""
    ideas = profile.ideas
    total = int(ideas.get("blocks") or ideas.get("count") or 0)
    if total < 3:
        return []
    have: set[str] = set()
    for want in person.skills:
        for concept in want.concepts:
            have.add(concept)
            have.update(broader_of(concept))
            have.update(narrower_index().get(concept, ()))
    return [
        label(concept)
        for concept, count in sorted((ideas.get("skills") or {}).items(), key=lambda kv: -kv[1])
        if kind_of(concept) == SKILL
        and concept not in have
        and concept != "git"
        and count / total >= 0.5
    ][:2]


def _skills_to_learn(profile: OrgProfile, person: ContributorProfile) -> list[str]:
    """Skills its ideas often ask for that the person did not list."""
    ideas = profile.ideas
    total = int(ideas.get("blocks") or ideas.get("count") or 0)
    if not total:
        return []
    have: set[str] = set()
    for want in person.skills:
        for concept in want.concepts:
            have.add(concept)
            have.update(broader_of(concept))
            have.update(narrower_index().get(concept, ()))
    out = []
    for concept, count in (ideas.get("skills") or {}).items():
        if kind_of(concept) != SKILL or concept in have or concept in {"git"}:
            continue
        if count >= 2 or count / total >= 0.25:
            out.append(f"{label(concept)} ({min(count, total)} of {total} ideas)")
    return out[:4]


# ------------------------------------------------------------------ the index


@dataclass
class OrgIndex:
    """Profiles of every organization in one year's list, built once."""

    orgs: list[OrgSummary]
    profiles: list[OrgProfile]
    idf: dict[str, float]
    reference_year: int
    signals_year: int | None = None
    signals_date: str | None = None
    breadth: dict[str, tuple[float, float]] = field(default_factory=dict)
    _broad_cache: dict[tuple[str, ...], bool] = field(default_factory=dict, repr=False)
    _qualifier_cache: dict[str, int] = field(default_factory=dict, repr=False)

    @classmethod
    def build(
        cls,
        orgs: list[OrgSummary],
        *,
        descriptions: dict[str, str] | None = None,
        signals: dict[str, Any] | None = None,
        reference_year: int,
    ) -> OrgIndex:
        descriptions = descriptions or {}
        by_slug = (signals or {}).get("organizations") or {}
        # The ideas evidence names its year ("3 of 12 2026 ideas"), so last year's
        # pages still say what an organization works on before the new ones appear.
        signals_year = (signals or {}).get("year")
        profiles = [
            build_org_profile(
                org,
                description=descriptions.get(org.name, ""),
                signals=by_slug.get(org.slug or ""),
                signals_year=signals_year,
            )
            for org in orgs
        ]
        return cls(
            orgs=orgs,
            profiles=profiles,
            idf=idf_table(profiles),
            reference_year=reference_year,
            signals_year=signals_year,
            signals_date=(signals or {}).get("generated"),
            breadth=_breadth_factors(profiles),
        )

    def _broad(self, person: ContributorProfile) -> bool:
        """True when an interest matches so many organizations that fit says little."""
        key = tuple(w.raw for w in person.interests)
        if key not in self._broad_cache:
            self._broad_cache[key] = any(
                sum(1 for p in self.profiles if match_term(p, w).strength >= 0.5) >= SHARPEN_AT
                for w in person.interests
            )
        return self._broad_cache[key]

    def _telling(self, want: Want) -> list[re.Pattern[str]]:
        """Patterns for the words that narrow an interest and tell organizations apart."""
        out = []
        for word in want.qualifiers:
            body = r"[\s-]?".join(re.escape(part) for part in word.split("-"))
            pattern = re.compile(rf"(?<![a-z0-9]){body}[a-z0-9]*")
            if word not in self._qualifier_cache:
                self._qualifier_cache[word] = sum(
                    1 for p in self.profiles if pattern.search(p.text)
                )
            if 0 < self._qualifier_cache[word] <= QUALIFIER_MAX_SHARE * len(self.profiles):
                out.append(pattern)
        return out

    def coverage(self, person: ContributorProfile) -> list[str]:
        """Skills that few or no organizations use, said plainly."""
        notes = []
        for want in person.skills:
            if not want.concepts:
                continue
            users = sum(
                1
                for p in self.profiles
                if any(p.strength.get(c, 0.0) >= 0.5 for c in want.concepts)
            )
            if users <= 2:
                plural = "organization uses" if users == 1 else "organizations use"
                notes.append(
                    f"{'No' if users == 0 else users} {self.reference_year} GSoC "
                    f"{plural if users else 'organization uses'} {want.shown}, so these results "
                    "rest on your other skills and interests. Most would need you to learn "
                    "another language."
                )
        return notes

    def sharpen(
        self, person: ContributorProfile, *, broad: int = SHARPEN_AT
    ) -> list[dict[str, Any]]:
        """Narrower words for a vague profile, with how many organizations each matches.

        An interest that matches dozens of organizations ("ai") gets its narrower
        concepts (computer vision, LLMs). A common skill with no interest at all
        ("python") gets the subjects its organizations work on most.
        """

        def df(concept: str, cut: float = 0.5) -> int:
            return sum(1 for p in self.profiles if p.strength.get(concept, 0.0) >= cut)

        tips: list[dict[str, Any]] = []
        for want in person.interests:
            matches = sum(1 for p in self.profiles if match_term(p, want).strength >= 0.5)
            if matches < broad:
                continue
            narrower = {n for c in want.concepts for n in narrower_index().get(c, ())}
            options = sorted(
                ((label(n), df(n)) for n in narrower if kind_of(n) != SKILL),
                key=lambda kv: (-kv[1], kv[0]),
            )
            options = [(name, n) for name, n in options if 2 <= n < matches][:4]
            if options:
                tips.append(
                    {"word": want.raw, "kind": "interest", "matches": matches, "suggest": options}
                )
        if not person.interests:
            for want in person.skills:
                users = [
                    p
                    for p in self.profiles
                    if any(p.strength.get(c, 0.0) >= 0.7 for c in want.concepts)
                ]
                if len(users) < broad:
                    continue
                counts: dict[str, int] = {}
                for profile in users:
                    for concept, value in profile.strength.items():
                        if value >= 0.7 and kind_of(concept) != SKILL:
                            counts[concept] = counts.get(concept, 0) + 1
                options = sorted(
                    ((label(c), n) for c, n in counts.items() if n >= 3 and c != "science"),
                    key=lambda kv: (-kv[1], kv[0]),
                )[:5]
                if options:
                    tips.append(
                        {
                            "word": want.raw,
                            "kind": "skill",
                            "matches": len(users),
                            "suggest": options,
                        }
                    )
        return tips

    def rank(
        self,
        person: ContributorProfile,
        *,
        query: str = "",
        category: str = "",
        limit: int | None = None,
    ) -> list[OrgMatch]:
        """Organizations for this person, best first.

        `query` is free text to match as well; `category` must match the listing's
        category. With a query, a category, or a non-empty profile, organizations
        whose relevance is under FIT_MIN are left out; with none, every organization
        is listed, ordered by its track record (years in a row, project slots, and
        ideas readiness), then by its tie-breakers.
        """
        query = query.strip()
        category = category.strip().lower()
        ceiling = math.log(len(self.profiles) + 1) + 1.0
        query_person = build_profile(interests=[query]) if query else None
        query_wants = [*query_person.interests, *query_person.skills] if query_person else []
        if query and not query_wants:
            query_wants = [Want(raw=query, concepts=())]
        filtered = bool(query or category or not person.empty)
        matches: list[OrgMatch] = []
        for profile in self.profiles:
            match = self._score(profile, person, query, query_wants, category, ceiling)
            if match is None:
                continue
            if filtered and match.relevance < FIT_MIN:
                continue
            matches.append(match)
        matches.sort(
            key=lambda m: (
                -m.score,
                -m.org.num_projects_latest,
                -len(m.org.years_active),
                m.org.name,
            )
        )
        matches = _diversify(matches, len(person.interests))
        return matches[:limit] if limit else matches

    def _score(
        self,
        profile: OrgProfile,
        person: ContributorProfile,
        query: str,
        query_wants: list[Want],
        category: str,
        ceiling: float,
    ) -> OrgMatch | None:
        org = profile.org
        extra: list[str] = []
        if category:
            if not (org.category and category in org.category.lower()):
                return None
            extra.append(f"Category: {org.category}")
        interests = [match_term(profile, w, self.idf) for w in person.interests]
        for term in interests:
            telling = self._telling(term.want) if term.how != "word" else []
            if term.strength <= 0 or not telling:
                continue
            named = next((m.group(0) for t in telling if (m := t.search(profile.text))), None)
            if named:
                term.evidence = [f"names '{named}' in its listing or ideas", *term.evidence]
            else:
                term.strength *= QUALIFIER_MISS
        skills = [match_term(profile, w, self.idf) for w in person.skills]
        skill_scale, domain_scale = self.breadth.get(org.name, (1.0, 1.0))
        for term in skills:
            term.strength *= skill_scale
        for term in interests:
            term.strength *= domain_scale
        interest_fit = sum(t.strength for t in interests) / len(interests) if interests else None
        skill_fit = None
        if skills:
            weights = [_weight(t.want, self.idf, ceiling) for t in skills]
            coverage = sum(w * t.strength for w, t in zip(weights, skills, strict=True)) / sum(
                weights
            )
            best_skill = max(t.strength for t in skills)
            skill_fit = BEST_SKILL_WEIGHT * best_skill + (1 - BEST_SKILL_WEIGHT) * coverage
        if interest_fit is not None and skill_fit is not None:
            base = INTEREST_WEIGHT * interest_fit + (1 - INTEREST_WEIGHT) * skill_fit
            relevance = (1 - SYNERGY) * base + SYNERGY * min(interest_fit, skill_fit)
        elif interest_fit is not None:
            relevance = interest_fit
        elif skill_fit is not None:
            # Asked only for skills: show organizations that use one of them, not ones
            # that use a neighbour (C++ for C); neighbours still help when interests match.
            if not any(t.how in {"direct", "broader", "word"} for t in skills):
                return None
            implied = [match_term(profile, w).strength for w in person.implied_interests]
            implied_fit = sum(implied) / len(implied) if implied else skill_fit
            relevance = (1 - IMPLIED_WEIGHT) * skill_fit + IMPLIED_WEIGHT * implied_fit
        else:
            relevance = 1.0 if (category or not query) else 0.0

        # A newcomer is better served by fit than by a project's flagship organization.
        home = _named_after(org.name, [*interests, *skills]) if person.experience != "new" else None
        if home is not None:
            relevance = min(1.0, relevance + NAME_BOOST)
            extra.append(f"Named after {home}")

        if query:
            name_hit = _word_pattern(query.lower()).search(org.name.lower())
            q = max((match_term(profile, w).strength for w in query_wants), default=0.0)
            if name_hit:
                q = 1.0
                extra.append(f"Name matches '{query}'")
            elif q > 0:
                extra.append(f"Matches '{query}'")
            if q <= 0:
                return None
            relevance = q if person.empty else 0.5 * relevance + 0.5 * q

        continuity, years_text = _years_line(org, self.reference_year)
        capacity, capacity_text = _capacity(org)
        readiness, idea_facts, difficulty = _ideas_facts(profile, self.signals_year)
        level = person.experience
        prior_weights = (
            (0.3, 0.2, 0.5)
            if level == "new"
            else (0.5, 0.4, 0.1)
            if level == "experienced"
            else (0.4, 0.3, 0.3)
        )
        prior = (
            prior_weights[0] * continuity
            + prior_weights[1] * capacity
            + prior_weights[2] * readiness
        )
        score = relevance * (PRIOR_FLOOR + (1 - PRIOR_FLOOR) * prior)

        caveats: list[str] = []
        stated = sum(difficulty.values())
        if stated >= 4 and difficulty.get("hard", 0) / stated >= 0.7:
            caveats.append(
                f"{difficulty['hard']} of the {stated} ideas that state a difficulty are hard"
            )
            if level == "new":
                score *= HARD_FOR_NEW
        sizes = {k: int(v) for k, v in (profile.ideas.get("size") or {}).items()}
        fits, time_note = _time_fit(person.hours_per_week, sizes)
        if time_note:
            caveats.append(time_note)
        if fits is False:
            score *= TIME_MISFIT
        trend = _trend(org.projects_by_year)
        if trend:
            caveats.append(trend)
        main = _main_language(profile, person)
        if main:
            caveats.append(main)
            score *= OTHER_MAIN_LANGUAGE
        said = profile.participation
        said_year = int(said.get("year") or 0)
        if said.get("status") == "not_taking_part" and said_year > self.reference_year:
            caveats.insert(
                0,
                f"Said it will not take part in GSoC {said_year} (checked "
                f"{said.get('checked')}): {said.get('url')}",
            )
            score *= SITTING_OUT
        elif said.get("status") == "undecided" and said_year > self.reference_year:
            caveats.append(
                f"Had not decided about GSoC {said_year} (checked {said.get('checked')}): "
                f"{said.get('url')}"
            )
        elif said.get("status") == "reported" and said_year > self.reference_year:
            # Quoted, dated, and marked as a report: no year was named, so it is not
            # the organization's word on GSoC {said_year}, and the score stays.
            # Only what GitHub shows: private membership reads as a plain contributor,
            # so "not listed as a maintainer" is all that can be said of anyone else.
            who = (
                "a maintainer"
                if said.get("by_maintainer")
                else "someone GitHub does not list as a maintainer"
            )
            caveats.append(
                f'On {said.get("date")}, {who} wrote in its tracker: "{said.get("quote")}" '
                f"Not an official statement about GSoC {said_year}; check its channels: "
                f"{said.get('url')}"
            )
        ideas_unread = bool(profile.ideas.get("url")) and (
            not profile.ideas.get("count") or _poorly_split(profile.ideas)
        )
        if ideas_unread:
            caveats.append(_unread_ideas(str(profile.ideas.get("layout") or "")))
        needs = _mostly_needs(profile, person) if not person.empty else []
        if needs:
            caveats.append(f"Most of its ideas need {', '.join(needs)}, which you did not list")
        blocking = (
            bool(needs)
            or fits is False
            or (level == "new" and stated >= 4 and difficulty.get("hard", 0) / stated >= 0.7)
        )

        readiness_lines = [*idea_facts]
        if years_text:
            readiness_lines.append(years_text)
        if capacity_text:
            readiness_lines.append(capacity_text)
        active = int(profile.github.get("active_repos") or 0)
        if active:
            readiness_lines.append(f"{active} GitHub repositories pushed in the last year")
        labelled = int(profile.github.get("beginner_issues_year") or 0)
        if labelled >= MIN_LABELLED:
            # A habit, not a list of open issues: an assistant read "1 beginner-labelled
            # issue" as one open now. Zero is not shown either: MDAnalysis marks first
            # tasks "Difficulty-easy" and Neovim "complexity:low", which are not counted.
            readiness_lines.append(
                f"{labelled} GitHub issues with a common beginner label were opened in the "
                "past year (open or since closed); `issues --org` shows the ones open now"
            )

        # A fit needs something to fit: a category or a bare listing has none.
        fit = _fit_level(relevance, interests, skills) if (query or not person.empty) else None
        # A caveat that decides whether someone can start here, or a broad word that
        # matches dozens of organizations, keeps the fit from being called strong.
        if fit == "strong" and (blocking or self._broad(person)):
            fit = "good"
        direct = [t for t in interests if t.how in {"direct", "word"} and t.strength > 0]
        if (
            fit == "strong"
            and interests
            and not any(profile.sources(c) >= 2 for t in direct for c in t.want.concepts)
        ):
            fit = "good"  # one tag alone is not enough to call it strong
        if fit in {"strong", "good"} and interests and not direct:
            fit = "partial"  # no interest is named, only near ones
        return OrgMatch(
            org=org,
            profile=profile,
            score=round(100 * score, 1),
            relevance=round(relevance, 3),
            fit=fit,
            skill_fit=None if skill_fit is None else round(skill_fit, 3),
            interest_fit=None if interest_fit is None else round(interest_fit, 3),
            skills=skills,
            interests=interests,
            readiness=readiness_lines,
            caveats=caveats,
            skills_to_learn=_skills_to_learn(profile, person) if not person.empty else [],
            extra_reasons=extra,
            ideas_unread=ideas_unread,
        )


def _named_after(name: str, terms: list[TermMatch]) -> str | None:
    """The asked-for thing an organization is named after, when its evidence agrees.

    The name is read like any other text, so "game theory" in Gambit's name is
    mathematics, not games. A broad word ("Open Science ...") names no one subject.
    """
    named = set(find_concepts(name)) - GENERIC_PARENTS
    for term in terms:
        if term.how == "direct" and term.strength >= 0.5 and named & set(term.want.concepts):
            return term.want.shown
    return None


def _breadth_factors(profiles: list[OrgProfile]) -> dict[str, tuple[float, float]]:
    """Per organization, how much to scale skill and subject matches for its breadth."""

    def counts(profile: OrgProfile) -> tuple[int, int]:
        skills = domains = 0
        for concept, value in profile.strength.items():
            if value < BREADTH_THRESHOLD:
                continue
            if kind_of(concept) == SKILL:
                skills += 1
            else:
                domains += 1
        return skills, domains

    pairs = {p.org.name: counts(p) for p in profiles}
    if not pairs:
        return {}
    skill_median = max(1.0, statistics.median(s for s, _ in pairs.values()))
    domain_median = max(1.0, statistics.median(d for _, d in pairs.values()))

    def scale(n: int, median: float, power: float) -> float:
        if power <= 0 or n <= median:
            return 1.0
        return float((median / n) ** power)

    return {
        name: (
            scale(s, skill_median, SKILL_BREADTH_POWER),
            scale(d, domain_median, DOMAIN_BREADTH_POWER),
        )
        for name, (s, d) in pairs.items()
    }


def _main_language(profile: OrgProfile, person: ContributorProfile) -> str | None:
    """'Its code is mostly Rust (...)' when that language is not one the person knows."""
    github = profile.github
    active = int(github.get("active_repos") or 0)
    languages = github.get("languages") or {}
    if active < 3 or not languages or person.empty or not person.skills:
        return None
    # One family per language a person would learn (TypeScript and Vue count with
    # JavaScript); HTML and CSS repositories are mostly sites and docs, not the code.
    families: dict[str, dict[str, int]] = {}
    for lang, n in languages.items():
        for concept in language_concepts({lang: int(n)}):
            if concept in FAMILY_SKIP:
                continue
            root = "javascript" if "javascript" in broader_of(concept) else concept
            families.setdefault(root, {})[lang] = int(n)
    if not families:
        return None
    root, members = max(families.items(), key=lambda kv: sum(kv[1].values()))
    count = sum(members.values())
    if count / active < MAIN_LANGUAGE_SHARE:
        return None
    name = " and ".join(sorted(members, key=lambda k: -members[k])[:2])
    concepts = {root: count, **{c: count for lang in members for c in language_concepts({lang: 1})}}
    known: set[str] = set()
    for want in person.skills:
        for concept in want.concepts:
            known.add(concept)
            known.update(broader_of(concept))
            known.update(narrower_index().get(concept, ()))
    if not concepts or set(concepts) & known:
        return None
    return (
        f"Its code is mostly {name}: the main language of {count} of its {active} GitHub "
        "repositories pushed in the last year"
    )


def _poorly_split(ideas: dict[str, Any]) -> bool:
    """True when the page split into many blocks but few of them are ideas."""
    real = int(ideas.get("count") or 0)
    blocks = int(ideas.get("blocks") or real)
    return real < 3 and blocks >= 6


def _unread_ideas(layout: str) -> str:
    if layout in {"unreachable", "error"}:
        return "Its ideas page could not be fetched automatically; open it in a browser"
    return "This tool could not pick out ideas on its ideas page; open it to read them"


def _trend(projects_by_year: dict[int, int]) -> str | None:
    years = sorted(projects_by_year)
    if len(years) < 3:
        return None
    latest = projects_by_year[years[-1]]
    baseline = (projects_by_year[years[-2]] + projects_by_year[years[-3]]) / 2
    if baseline and latest / baseline <= 0.6 and baseline - latest >= 2:
        return (
            f"Fewer projects in {years[-1]} ({latest}) than in the two years before "
            f"({projects_by_year[years[-3]]} and {projects_by_year[years[-2]]})"
        )
    return None


def _fit_level(relevance: float, interests: list[TermMatch], skills: list[TermMatch]) -> str:
    if relevance >= FIT_STRONG and (not interests or any(t.how == "direct" for t in interests)):
        return "strong"
    if relevance >= FIT_GOOD:
        return "good"
    return "partial"


def _diversify(matches: list[OrgMatch], interest_count: int, window: int = 30) -> list[OrgMatch]:
    """With several interests, make sure each one shows up near the top.

    A greedy re-rank over the first `window` results: an organization that covers
    an interest nobody above it covers gets a small lift (after Carbonell and
    Goldstein's maximal marginal relevance, 1998).
    """
    if interest_count < 2 or len(matches) < 3:
        return matches
    head, tail = matches[:window], matches[window:]
    picked: list[OrgMatch] = []
    covered: set[int] = set()
    while head:

        def gain(m: OrgMatch) -> float:
            new = {i for i, t in enumerate(m.interests) if t.strength >= 0.5 and i not in covered}
            return m.score + 100 * DIVERSITY * len(new) / interest_count

        best = max(head, key=gain)
        head.remove(best)
        picked.append(best)
        covered.update(i for i, t in enumerate(best.interests) if t.strength >= 0.5)
    return picked + tail


def rank_orgs(
    orgs: list[OrgSummary],
    *,
    technologies: list[str] | None = None,
    interests: list[str] | None = None,
    experience: str | None = None,
    hours_per_week: int | None = None,
    reference_year: int,
    descriptions: dict[str, str] | None = None,
    signals: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[OrgMatch]:
    """One-call convenience for scripts and tests."""
    index = OrgIndex.build(
        orgs, descriptions=descriptions, signals=signals, reference_year=reference_year
    )
    person = build_profile(
        technologies=technologies,
        interests=interests,
        experience=experience,
        hours_per_week=hours_per_week,
    )
    return index.rank(person, limit=limit)
