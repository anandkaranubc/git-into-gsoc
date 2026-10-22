"""Pull requests that look like the same work as an issue but never link it.

A pull request that names no issue leaves no trace on the issue's timeline: an open
README rewrite next to a README issue, or a merged fix whose issue nobody closed. A
pull request counts here only when its title shares at least three of the issue
title's distinctive words, and at least 60% of them, and does not say it is for a
different issue. Measured on 2026-10-22 on open "good first issue" issues: tuned on
56 issues from 16 GSoC organizations (8 flagged, all the same work on review), then
checked on 57 issues from 16 other organizations (4 flagged, all the same work). Two
shared words, or a pull request for another issue, matched unrelated work.
"""

from __future__ import annotations

import re
from typing import Any

# Words that appear in titles of every kind of change, so sharing them proves nothing.
# Words under four letters are skipped anyway.
_COMMON = frozenset(
    """
    with without from into onto over under about after before when while were been
    being this that these those there here could should would will might must does done
    have adds added adding fixes fixed fixing update updates updated updating support
    supports issue issues bugs error errors problem problems feature features request
    improve improves improvement make makes uses using used more less some each other
    missing remove removes removed allow allows enable disable change changes changed
    docs documentation readme test tests testing code file files page pages example
    examples where which what instead also only just than then
    """.split()  # noqa: SIM905 (one word list reads better than 98 lines)
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.]{2,}")
_REF_RE = re.compile(r"#(\d+)\b")
MIN_SHARED = 3
MIN_SHARE = 0.6


def title_words(title: str) -> list[str]:
    """The distinctive words of a title, lower-cased, in order, without repeats."""
    found: list[str] = []
    for word in _WORD_RE.findall(title or ""):
        word = word.lower().strip(".")
        if len(word) >= 4 and word not in _COMMON and word not in found:
            found.append(word)
    return found


def same_work(issue_number: int, words: list[str], pull: dict[str, Any]) -> list[str]:
    """The issue's title words that `pull`'s title shares, or [] when it looks unrelated."""
    if len(words) < MIN_SHARED:
        return []
    title = str(pull.get("title") or "")
    shared = [w for w in words if w in set(title_words(title))]
    if len(shared) < MIN_SHARED or len(shared) / len(words) < MIN_SHARE:
        return []
    # "Fix part of #26840: migrate ..." is another issue's work, however alike it reads.
    refs = {int(n) for n in _REF_RE.findall(f"{title} {pull.get('body') or ''}")}
    if refs and issue_number not in refs:
        return []
    return shared
