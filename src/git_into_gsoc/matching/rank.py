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
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from git_into_gsoc.coach import LONGEST_CODING_WEEKS, PROJECT_HOURS
from git_into_gsoc.matching.concepts import (
    CONCEPTS,
    SKILL,
    broader_of,
    kind_of,
    label,
    narrower_index,
)
from git_into_gsoc.matching.orgs import OrgProfile, build_org_profile, idf_table
from git_into_gsoc.matching.profile import ContributorProfile, Want, build_profile
from git_into_gsoc.models import OrgSummary

# How much a match through a neighbouring concept counts.
VIA_BROADER_SKILL = 0.3  # wants React, the org uses JavaScript
VIA_BROADER_DOMAIN = 0.35  # wants computer vision, the org does machine learning
VIA_RELATED = 0.35  # wants astronomy, the org does physics
WORD_IN_TAG, WORD_IN_TEXT = 1.0, 0.6
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
# How far the tie-breakers can move a score: from x0.8 to x1.0.
PRIOR_FLOOR = 0.8
HARD_FOR_NEW = 0.85
TIME_MISFIT = 0.85
FIT_STRONG, FIT_GOOD, FIT_MIN = 0.7, 0.45, 0.12
DIVERSITY = 0.08
STANDARD_WEEKS = 12


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
    fit: str
    skill_fit: float | None = None
    interest_fit: float | None = None
    skills: list[TermMatch] = field(default_factory=list)
    interests: list[TermMatch] = field(default_factory=list)
    readiness: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    skills_to_learn: list[str] = field(default_factory=list)
    extra_reasons: list[str] = field(default_factory=list)

    def reasons(self) -> list[str]:
        """Short reasons: direct matches first, then matches through a neighbour."""
        terms = [("topic", t) for t in self.interests] + [("skill", t) for t in self.skills]
        direct = [t.reason(k) for k, t in terms if t.strength > 0 and t.how in {"direct", "word"}]
        nearby = [
            t.reason(k) for k, t in terms if t.strength > 0 and t.how not in {"direct", "word"}
        ]
        return [*self.extra_reasons, *direct, *nearby, *self.readiness[:3]]

    def evidence(self) -> list[str]:
        lines = []
        for kind, terms in (("Topic", self.interests), ("Skill", self.skills)):
            for term in terms:
                if term.strength <= 0 or not term.evidence:
                    continue
                via = f" (through {term.via})" if term.via else ""
                lines.append(f"{kind} {term.want.shown}{via}: " + "; ".join(term.evidence))
        return lines


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


def match_term(profile: OrgProfile, want: Want) -> TermMatch:
    """How strongly an organization covers one thing the person asked for."""
    best = TermMatch(want=want, strength=0.0, how="none")

    def central(concept: str) -> float:
        share = min(1.0, profile.sources(concept) / CENTRAL_SOURCES)
        return profile.strength.get(concept, 0.0) * (
            CENTRALITY_FLOOR + (1 - CENTRALITY_FLOOR) * share
        )

    for concept in want.concepts:
        own = central(concept)
        if own > best.strength:
            best = TermMatch(want, own, "direct", None, profile.best_evidence(concept))
        factor = VIA_BROADER_SKILL if kind_of(concept) == SKILL else VIA_BROADER_DOMAIN
        for parent in broader_of(concept):
            value = factor * profile.strength.get(parent, 0.0)
            if value > best.strength:
                best = TermMatch(
                    want, value, "broader", label(parent), profile.best_evidence(parent)
                )
        for other in _related_index().get(concept, ()):
            value = VIA_RELATED * profile.strength.get(other, 0.0)
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
    difficulty = {k: int(v) for k, v in (ideas.get("difficulty") or {}).items()}
    sizes = {k: int(v) for k, v in (ideas.get("size") or {}).items()}
    parts: list[float] = [1.0 if profile.org.guide_url else 0.0]
    facts: list[str] = []
    when = f"{year} " if year else ""
    if count:
        parts.append(1.0)
        line = f"{count} ideas on its {when}ideas page"
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


def _skills_to_learn(profile: OrgProfile, person: ContributorProfile) -> list[str]:
    """Skills its ideas often ask for that the person did not list."""
    ideas = profile.ideas
    total = int(ideas.get("count") or 0)
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
            out.append(f"{label(concept)} ({count} of {total} ideas)")
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
        )

    def rank(
        self,
        person: ContributorProfile,
        *,
        query: str = "",
        category: str = "",
        limit: int | None = None,
    ) -> list[OrgMatch]:
        query = query.strip()
        category = category.strip().lower()
        ceiling = math.log(len(self.profiles) + 1) + 1.0
        query_wants = build_profile(interests=[query]).interests if query else []
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
        interests = [match_term(profile, w) for w in person.interests]
        skills = [match_term(profile, w) for w in person.skills]
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
        if profile.ideas.get("url") and not profile.ideas.get("count"):
            caveats.append(_unread_ideas(str(profile.ideas.get("layout") or "")))

        readiness_lines = [*idea_facts]
        if years_text:
            readiness_lines.append(years_text)
        if capacity_text:
            readiness_lines.append(capacity_text)
        active = int(profile.github.get("active_repos") or 0)
        if active:
            readiness_lines.append(f"{active} GitHub repositories pushed in the last year")

        fit = _fit_level(relevance, interests, skills)
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
        )


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
