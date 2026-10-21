"""Organization matching / ranking."""

from __future__ import annotations

from git_into_gsoc.models import OrgSummary


def score_org_match(
    org: OrgSummary,
    *,
    query: str = "",
    technologies: list[str] | None = None,
    topics: list[str] | None = None,
    category: str = "",
    prefer_year: int = 2026,
) -> tuple[float, list[str]]:
    technologies = technologies or []
    topics = topics or []
    score = 0.0
    reasons: list[str] = []

    haystack = " ".join(
        [
            org.name,
            org.description,
            " ".join(org.topics),
            " ".join(org.technologies),
            org.category or "",
        ]
    ).lower()

    if query:
        tokens = [t for t in query.split() if t]
        hits = sum(1 for t in tokens if t in haystack)
        if hits:
            score += 20 + 10 * hits
            reasons.append(f"Matched query tokens ({hits}/{len(tokens)})")
        elif query in haystack:
            score += 25
            reasons.append("Matched full query string")
        else:
            return 0.0, []

    tech_set = {t.lower() for t in org.technologies}
    topic_set = {t.lower() for t in org.topics}

    for tech in technologies:
        if tech in tech_set or tech in haystack:
            score += 18
            reasons.append(f"Technology fit: {tech}")

    for topic in topics:
        if topic in topic_set or topic in haystack:
            score += 14
            reasons.append(f"Topic fit: {topic}")

    if category and org.category and category in org.category.lower():
        score += 12
        reasons.append(f"Category fit: {org.category}")

    # Continuity / experience mentoring
    years = org.years_active
    if prefer_year in years:
        score += 20
        reasons.append(f"Participated in {prefer_year}")
    if len(years) >= 5:
        score += 15
        reasons.append(f"Long-term mentoring org ({len(years)} years)")
    elif len(years) >= 2:
        score += 8
        reasons.append(f"Multi-year participant ({len(years)} years)")

    if org.num_projects_latest:
        if 3 <= org.num_projects_latest <= 40:
            score += 8
            reasons.append(f"{org.num_projects_latest} projects in latest year")
        elif org.num_projects_latest > 40:
            score += 4
            reasons.append("Large org — more slots but more competition")

    if org.irc_channel or org.mailing_list or org.contact_email:
        score += 5
        reasons.append("Public contact channel listed")

    if not reasons and not query and not technologies and not topics and not category:
        # browsing mode — base rank by continuity
        score = 10 + 2 * len(years)
        reasons.append("Browse rank by mentoring continuity")

    return round(score, 1), reasons
