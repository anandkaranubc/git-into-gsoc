"""Organization matching and ranking.

Relevance (technology/topic/query fit) decides *whether* an org matches;
continuity and capacity signals decide *order* among relevant orgs. Terms are
canonicalised through an alias table and matched on word boundaries, so `c`
does not match every description and `go` does not match `google`.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import NamedTuple

from git_into_gsoc.models import OrgSummary

ALIASES: dict[str, str] = {
    "js": "javascript",
    "node": "nodejs",
    "node.js": "nodejs",
    "ts": "typescript",
    "golang": "go",
    "cpp": "c++",
    "cplusplus": "c++",
    "py": "python",
    "python3": "python",
    "rs": "rust",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "llm": "large language models",
    "llms": "large language models",
    "k8s": "kubernetes",
    "reactjs": "react",
    "react.js": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "csharp": "c#",
    "postgres": "postgresql",
    "web development": "web",
    "webdev": "web",
    "bio": "bioinformatics",
}
_SPLIT = re.compile(r"\s*(?:/|,|\band\b)\s*")


def canonical(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.strip().lower())
    return ALIASES.get(cleaned, cleaned)


def expand_terms(terms: list[str] | set[str]) -> set[str]:
    """Canonicalise and split compound tags like `c/c++` into `{c, c++}`."""
    out: set[str] = set()
    for term in terms:
        value = canonical(term)
        if not value:
            continue
        out.add(value)
        if "/" in value or "," in value:
            out.update(canonical(part) for part in _SPLIT.split(value) if part.strip())
    return out


@lru_cache(maxsize=2048)
def _word_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w+#]){re.escape(term)}(?![\w+#])", re.IGNORECASE)


def mentions(text: str, term: str) -> bool:
    """Word-boundary match that treats `+` and `#` as word characters (c++, c#)."""
    return bool(term) and bool(_word_pattern(term).search(text))


class MatchResult(NamedTuple):
    score: float
    reasons: list[str]
    relevant: bool


def score_org_match(
    org: OrgSummary,
    *,
    query: str = "",
    technologies: list[str] | None = None,
    topics: list[str] | None = None,
    category: str = "",
    reference_year: int = 2026,
    search_text: str = "",
) -> MatchResult:
    tech_tags = expand_terms(org.technologies)
    topic_tags = expand_terms(org.topics)
    text = " ".join([org.name, org.description, search_text])
    wanted_tech = expand_terms(technologies or [])
    wanted_topics = expand_terms(topics or [])
    filtered = bool(query.strip() or wanted_tech or wanted_topics or category.strip())

    relevance = 0.0
    reasons: list[str] = []

    for tech in sorted(wanted_tech):
        if tech in tech_tags:
            relevance += 20
            reasons.append(f"Uses {tech}")
        elif tech in topic_tags:
            relevance += 10
            reasons.append(f"Topic tag {tech}")
        elif len(tech) > 2 and mentions(text, tech):
            relevance += 5
            reasons.append(f"Mentions {tech}")

    for topic in sorted(wanted_topics):
        if topic in topic_tags or topic in tech_tags:
            relevance += 16
            reasons.append(f"Topic: {topic}")
        elif any(mentions(tag, topic) or mentions(topic, tag) for tag in topic_tags):
            relevance += 10
            reasons.append(f"Related topic: {topic}")
        elif org.category and mentions(org.category, topic):
            relevance += 8
            reasons.append(f"Category: {org.category}")
        elif len(topic) > 2 and mentions(text, topic):
            relevance += 5
            reasons.append(f"Mentions {topic}")

    if query.strip():
        tokens = [canonical(t) for t in query.split() if len(t) > 1]
        name_hits = [t for t in tokens if mentions(org.name, t)]
        tag_hits = [t for t in tokens if t in tech_tags or t in topic_tags]
        text_hits = [t for t in tokens if mentions(text, t)]
        if name_hits:
            relevance += 25
            reasons.append(f"Name matches '{' '.join(name_hits)}'")
        if tag_hits:
            relevance += 10 * len(tag_hits)
        if text_hits and not name_hits:
            relevance += 4 * len(text_hits)
            reasons.append(f"Matches '{' '.join(text_hits)}'")
        if not (name_hits or tag_hits or text_hits):
            return MatchResult(0.0, [], False)

    if category.strip() and org.category and mentions(org.category, category.strip().lower()):
        relevance += 10
        reasons.append(f"Category: {org.category}")

    if filtered and relevance == 0:
        return MatchResult(0.0, [], False)

    quality = 0.0
    years = org.years_active
    if reference_year in years:
        quality += 15
        reasons.append(f"Accepted in {reference_year}")
    recent = [y for y in years if reference_year - 4 <= y <= reference_year]
    quality += min(12.0, 3.0 * len(recent))
    if len(years) >= 8:
        quality += 4
        reasons.append(f"Veteran mentoring org ({len(years)} years)")
    elif len(recent) >= 3:
        reasons.append(f"Mentored {len(recent)} of the last 5 years")

    if org.num_projects_latest:
        quality += min(10.0, 2.5 * math.log2(1 + org.num_projects_latest))
        reasons.append(f"{org.num_projects_latest} projects in {org.latest_year or 'latest year'}")
    trend = slot_trend(org.projects_by_year)
    if trend == "growing":
        quality += 3
        reasons.append("Slots growing")
    elif trend == "shrinking":
        quality -= 2

    if org.ideas_url:
        quality += 3
    if org.github_orgs:
        quality += 2

    score = relevance * 1.5 + quality if filtered else 10 + quality
    return MatchResult(round(score, 1), reasons, True)


def slot_trend(projects_by_year: dict[int, int]) -> str | None:
    """Compare the latest year's project count with the mean of the two before it."""
    years = sorted(projects_by_year)
    if len(years) < 3:
        return None
    latest = projects_by_year[years[-1]]
    baseline = (projects_by_year[years[-2]] + projects_by_year[years[-3]]) / 2
    if baseline == 0:
        return None
    ratio = latest / baseline
    if ratio >= 1.25:
        return "growing"
    if ratio <= 0.75:
        return "shrinking"
    return "steady"
