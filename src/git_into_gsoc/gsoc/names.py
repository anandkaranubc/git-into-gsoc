"""Match an organization name someone typed to the organization they meant.

Names are compared word by word, never as squashed substrings: "R project" must
not land inside "simulatoR PROJECT", and "Tor" must not land inside "invenTOR".
Words such as "the", "project", or "foundation" are ignored when comparing, so
"GNU Mailman Project", "GNU Mailman", and "mailman" all mean the same org.

Each candidate gets a level, and the highest level wins. Organizations in the
current list beat past ones at the same level. When several organizations
still tie, nothing is guessed: `AmbiguousNameError` lists them.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

from git_into_gsoc.errors import AmbiguousNameError

# Short forms people type for an organization's main project.
ALIASES = {"postgres": "postgresql", "py": "python", "golang": "go", "k8s": "kubernetes"}

FILLER = frozenset(
    {
        "a",
        "and",
        "association",
        "community",
        "for",
        "foundation",
        "inc",
        "initiative",
        "language",
        "of",
        "org",
        "organisation",
        "organization",
        "programming",
        "project",
        "software",
        "the",
    }
)
_STOP = frozenset({"the", "of", "for", "and", "a"})

EXACT = 100  # same letters and digits, ignoring case and punctuation
CORE = 95  # same words once filler words are dropped
JOINED = 85  # the name's words, run together ("rocketchat", "ns3", "52north")
WORDS = 80  # every word typed is a whole word of the name
ACRONYM = 75  # initials ("PSF")
PREFIX = 70  # every word typed is most of a word of the name ("tensor")


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def _squash(value: str) -> str:
    return "".join(_words(value))


def _core(words: list[str]) -> list[str]:
    return [w for w in words if w not in FILLER] or words


def core_key(name: str) -> str:
    """The name without filler words, for matching the same org across sources."""
    return " ".join(_core(_words(name)))


def same_org(a: str, b: str) -> bool:
    return bool(_squash(a)) and (_squash(a) == _squash(b) or core_key(a) == core_key(b))


def match_level(query: str, name: str) -> int:
    """How well `query` names `name`; 0 when it does not.

    A common short form counts as well as what was typed, so "postgres" names
    PostgreSQL exactly.
    """
    level = _match_level(query, name)
    expanded = " ".join(ALIASES.get(w, w) for w in _words(query))
    if expanded != " ".join(_words(query)):
        level = max(level, _match_level(expanded, name))
    return level


def _match_level(query: str, name: str) -> int:
    q_words, n_words = _words(query), _words(name)
    if not q_words or not n_words:
        return 0
    if "".join(q_words) == "".join(n_words):
        return EXACT
    q_core, n_core = _core(q_words), _core(n_words)
    if q_core == n_core:
        return CORE
    joined = "".join(q_words)
    for start in range(len(n_words)):
        run = ""
        for word in n_words[start:]:
            run += word
            if run == joined:
                return JOINED
            if len(run) >= len(joined):
                break
    if all(w in n_words for w in q_core):
        return WORDS
    initials = "".join(w[0] for w in n_words if w not in _STOP)
    if len(joined) >= 3 and joined.isalpha() and joined == initials:
        return ACRONYM
    # Most of a word, so "tensor" finds TensorFlow but "meta" does not find Metasploit.
    if all(
        any(n == w or (len(w) >= 4 and n.startswith(w) and len(w) >= 0.6 * len(n)) for n in n_words)
        for w in q_core
    ):
        return PREFIX
    return 0


def resolve_name(query: str, current: Iterable[str], past: Iterable[str] = ()) -> str | None:
    """The one organization `query` names, or None.

    Raises AmbiguousNameError when several fit equally well.
    """
    current = list(dict.fromkeys(current))
    known = {_squash(n) for n in current} | {core_key(n) for n in current}
    # A past record of a current org (renamed slightly) is the same org; keep the current one.
    past = [
        n
        for n in dict.fromkeys(past)
        if _squash(n) not in known and core_key(n) not in known and _squash(n)
    ]
    scored = [(match_level(query, n), 1, n) for n in current]
    scored += [(match_level(query, n), 0, n) for n in past]
    scored = [s for s in scored if s[0] > 0]
    if not scored:
        return None
    best = max(level for level, _, _ in scored)
    top = [s for s in scored if s[0] == best]
    if any(is_current for _, is_current, _ in top):
        top = [s for s in top if s[1]]
    if len(top) == 1:
        return top[0][2]
    raise AmbiguousNameError(query, sorted(n for _, _, n in top))


def suggest_names(query: str, names: Iterable[str], limit: int = 5) -> list[str]:
    """Close names for a query that matched nothing (typos, split or partial words)."""
    wanted = _squash(query)
    if len(wanted) < 3:
        return []
    by_key: dict[str, str] = {}
    for name in names:
        by_key.setdefault(_squash(name), name)
        for word in _core(_words(name)):
            by_key.setdefault(word, name)
    close = difflib.get_close_matches(wanted, list(by_key), n=limit * 3, cutoff=0.75)
    return list(dict.fromkeys(by_key[key] for key in close))[:limit]
