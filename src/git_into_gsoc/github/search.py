"""Build GitHub issue search queries that survive advanced search.

GitHub's advanced issue search treats repeated qualifiers as AND, so
`org:a org:b` returns nothing. Grouping them as `(org:a OR org:b)` returns
the union under both the legacy and the advanced engine (checked live on
2026-10-21). Queries are capped at GitHub's 256 characters.
"""

from __future__ import annotations

import re

from git_into_gsoc.validation import search_term

MAX_QUERY_CHARS = 256


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


def build_issue_query(
    *, base: list[str], labels: list[str], orgs: list[str], extra: list[str] | None = None
) -> str:
    """Base qualifiers, a label group, then as many orgs as fit in the length budget."""
    parts = [*base, *(extra or [])]
    label_group = or_group("label", labels)
    if label_group:
        parts.append(label_group)
    query = " ".join(parts)
    kept: list[str] = []
    for org in dict.fromkeys(o for o in orgs if o and o.strip()):
        candidate = f"{query} {or_group('org', [*kept, org])}"
        if len(candidate) > MAX_QUERY_CHARS:
            break
        kept.append(org)
    if kept:
        query = f"{query} {or_group('org', kept)}"
    return query
