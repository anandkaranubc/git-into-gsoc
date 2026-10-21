"""Build GitHub issue search queries that survive advanced search.

GitHub's advanced issue search treats repeated qualifiers as AND, so
`org:a org:b` returns nothing. Grouping them as `(org:a OR org:b)` returns
the union under both the legacy and the advanced engine (checked live on
2026-10-21).

Limits, also checked live on 2026-10-21: GitHub rejects a query with 16 or more
owner filters (`org:`, `user:`, `repo:`) with "Ownership filters limit of 16
exceeded". Its 256-character limit does not count qualifiers: a 724-character
query of qualifiers worked. Orgs past either limit are left out, never sent.
"""

from __future__ import annotations

import re

from git_into_gsoc.scoring.org_match import canonical
from git_into_gsoc.validation import search_term

MAX_QUERY_CHARS = 720
MAX_OWNER_FILTERS = 15

# Someone who writes one of these can usually work in the other; a project's
# repositories are often split between them (a JavaScript site, a TypeScript app).
RELATED_LANGUAGES = {"javascript": ["typescript"], "typescript": ["javascript"]}


_IDENTIFIER_QUALIFIERS = {"repo", "org", "user", "author", "commenter", "reviewed-by", "assignee"}


def _identifier(value: str) -> str:
    return value.strip()


def _label_value(value: str) -> str:
    """Labels keep colons, slashes and emoji; quotes and backslashes cannot be part of one."""
    cleaned = re.sub(r"\s+", " ", value.replace('"', "").replace("\\", "")).strip()
    return f'"{cleaned}"' if re.search(r"[^\w-]", cleaned) else cleaned


def or_group(qualifier: str, values: list[str]) -> str:
    """`qualifier:v` for one value, `(qualifier:a OR qualifier:b)` for several.

    Logins and owner/repo names are validated upstream and passed through as is;
    free-text values such as labels are cleaned and quoted when they contain spaces.
    """
    if qualifier in _IDENTIFIER_QUALIFIERS:
        clean = _identifier
    elif qualifier == "label":
        clean = _label_value
    else:
        clean = search_term
    terms = [f"{qualifier}:{clean(value)}" for value in values if value and value.strip()]
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return "(" + " OR ".join(terms) + ")"


def language_group(language: str) -> str:
    """`language:x`, or an OR group with its close relatives (JS and TS)."""
    main = canonical(language)
    return or_group("language", [main, *RELATED_LANGUAGES.get(main, [])])


def build_issue_query(
    *, base: list[str], labels: list[str], orgs: list[str], extra: list[str] | None = None
) -> str:
    """Base qualifiers, a label group, then as many orgs as GitHub accepts."""
    parts = [*base, *(extra or [])]
    label_group = or_group("label", labels)
    if label_group:
        parts.append(label_group)
    query = " ".join(parts)
    owners_used = len(re.findall(r"(?:^|[\s(])-?(?:org|user|repo):", query))
    kept: list[str] = []
    for org in dict.fromkeys(o for o in orgs if o and o.strip()):
        candidate = f"{query} {or_group('org', [*kept, org])}"
        if len(candidate) > MAX_QUERY_CHARS or owners_used + len(kept) >= MAX_OWNER_FILTERS:
            break
        kept.append(org)
    if kept:
        query = f"{query} {or_group('org', kept)}"
    return query
