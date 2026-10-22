"""What organizations post in their own repositories about a coming GSoC year.

Organizations announce plans in issues: Oppia opens a "GSoC 2027 Preparation"
tracker, Nominatim says it has "not yet decided", and Wagtail said "No GSoC on
Wagtail core in 2027" months before the official list. One search finds these
posts; a sentence that names GSoC and says the org will not take part, or has
not decided, sets the status, and only when a maintainer wrote it.
"""

from __future__ import annotations

import re
from typing import Any

from git_into_gsoc.github.availability import MAINTAINER_ROLES
from git_into_gsoc.text import clean_untrusted

_GSOC = re.compile(r"\bgsoc\b|summer of code", re.I)
_NOT_TAKING_PART = re.compile(
    r"\bno gsoc\b|won[\u2019']?t (?:be )?(?:take|taking) part|won[\u2019']?t (?:participate|apply)|"
    r"will not (?:take part|participate|apply)|not (?:be )?(?:taking|take) part|"
    r"not participating|not applying|(?:skip|skipping) gsoc|decided (?:not|against)|"
    r"decision (?:to not|not to)|not (?:be )?involved",
    re.I,
)
_UNDECIDED = re.compile(
    r"not (?:yet )?decided|haven[\u2019']?t (?:yet )?decided|undecided|not (?:yet )?confirmed|"
    r"no decision",
    re.I,
)
_SENTENCES = re.compile(r"(?<=[.!?\n])\s+")


_ANY_YEAR = re.compile(r"(?<![#\d])20\d\d(?!\d)")
# Markdown around a quoted sentence: "[text](url)" keeps the text, a stray "](url)" goes.
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_TAIL = re.compile(r"\]\([^)]*\)")


def body_search_terms(since: str) -> list[str]:
    """Qualifiers for issues updated since `since` whose body names GSoC, by either name.

    The OR group needs GitHub's advanced search, which `search_issues` asks for.
    """
    return ["is:issue", '(gsoc OR "summer of code")', "in:body", f"updated:>={since}"]


def upcoming_year(created: str) -> int | None:
    """The GSoC a post written on `created` (YYYY-MM-DD) means by "this year".

    From September, after a program ends, people talk about the next one; in January
    and February the next one is the current calendar year. Between March and August
    a program is under way, so "this year" is that one, not the coming one.
    """
    try:
        year, month = int(created[:4]), int(created[5:7])
    except (TypeError, ValueError):
        return None
    if month >= 9:
        return year + 1
    if month <= 2:
        return year
    return None


def reported_statements(items: list[dict[str, Any]], *, year: int) -> list[dict[str, Any]]:
    """Sentences in issue bodies that say an organization will skip, or has not decided
    about, GSoC `year`, without naming the year: as posts with status "reported".

    SymPy's tracker said, in October 2026 and with no year, "we will not participate
    in GSoC this year". A sentence that names another year is left out, and so is one
    whose year cannot be told from its date. These are reports, not the organization's
    own word, so they never set a status by themselves.
    """
    found: list[dict[str, Any]] = []
    for item in items:
        if "pull_request" in item:
            continue
        created = str(item.get("created_at") or "")[:10]
        body = str(item.get("body") or "")[:6000]
        for sentence in _SENTENCES.split(body):
            if not _GSOC.search(sentence) or _status(sentence) == "mentions":
                continue
            years = {int(y) for y in _ANY_YEAR.findall(sentence)}
            if years and year not in years:
                continue  # about another program
            if not years and upcoming_year(created) != year:
                continue
            by_maintainer = str(item.get("author_association") or "") in MAINTAINER_ROLES
            # A maintainer naming the year speaks for the organization, as in a title.
            status = _status(sentence) if by_maintainer and year in years else "reported"
            text = _MD_TAIL.sub("", _MD_LINK.sub(r"\1", sentence))
            parts = str(item.get("repository_url") or "").rstrip("/").split("/")
            found.append(
                {
                    "repo": "/".join(parts[-2:]),
                    "number": int(item.get("number") or 0),
                    "title": clean_untrusted(text.strip(" #*->[]"), limit=240),
                    "url": str(item.get("html_url") or ""),
                    "state": str(item.get("state") or ""),
                    "created_at": created,
                    "author": clean_untrusted((item.get("user") or {}).get("login"), limit=40),
                    "by_maintainer": by_maintainer,
                    "source": "body",
                    "status": status,
                }
            )
            break
    return found


def search_terms(year: int) -> list[str]:
    """Qualifiers for one issue search: both words anywhere in the title."""
    return ["is:issue", "gsoc", str(int(year)), "in:title"]


def _status(text: str) -> str:
    for sentence in _SENTENCES.split(text):
        if not _GSOC.search(sentence):
            continue
        if _NOT_TAKING_PART.search(sentence):
            return "not_taking_part"
        if _UNDECIDED.search(sentence):
            return "undecided"
    return "mentions"


def gsoc_posts(items: list[dict[str, Any]], *, year: int) -> list[dict[str, Any]]:
    """Issues whose title names GSoC and `year`, newest maintainer news first."""
    year_re = re.compile(rf"(?<![#\d]){int(year)}(?!\d)")
    posts: list[dict[str, Any]] = []
    for item in items:
        if "pull_request" in item:
            continue
        title = clean_untrusted(item.get("title"), limit=200)
        if not (_GSOC.search(title) and year_re.search(title)):
            continue
        parts = str(item.get("repository_url") or "").rstrip("/").split("/")
        by_maintainer = str(item.get("author_association") or "") in MAINTAINER_ROLES
        body = str(item.get("body") or "")[:4000]
        status = _status(f"{title}.\n{body}") if by_maintainer else "mentions"
        posts.append(
            {
                "repo": "/".join(parts[-2:]),
                "number": int(item.get("number") or 0),
                "title": title,
                "url": str(item.get("html_url") or ""),
                "state": str(item.get("state") or ""),
                "created_at": str(item.get("created_at") or "")[:10],
                "author": clean_untrusted((item.get("user") or {}).get("login"), limit=40),
                "by_maintainer": by_maintainer,
                "status": status,
            }
        )
    order = {"not_taking_part": 0, "undecided": 1, "mentions": 2}
    posts.sort(key=lambda p: p["created_at"], reverse=True)
    posts.sort(key=lambda p: (order[p["status"]], not p["by_maintainer"]))
    return posts


def wiki_post(text: str, *, year: int, repo: str) -> dict[str, Any] | None:
    """A statement about `year` on a project's wiki home page, as a post, or None.

    Learning Unlimited said on its wiki, and nowhere in an issue, that it would
    not take part in GSoC 2027. A wiki sentence counts only when it names GSoC
    and the year and says the organization will not take part or has not
    decided. Anyone may be able to edit a wiki, so it is not marked as written
    by a maintainer.
    """
    year_re = re.compile(rf"(?<![#\d]){int(year)}(?!\d)")
    for sentence in _SENTENCES.split(text[:20000]):
        if not (_GSOC.search(sentence) and year_re.search(sentence)):
            continue
        status = _status(sentence)
        if status == "mentions":
            continue
        return {
            "repo": repo,
            "number": 0,
            "title": clean_untrusted(sentence.strip(" #*-"), limit=200),
            "url": f"https://github.com/{repo}/wiki",
            "state": "wiki",
            "created_at": "",
            "author": "",
            "by_maintainer": False,
            "source": "wiki",
            "status": status,
        }
    return None
