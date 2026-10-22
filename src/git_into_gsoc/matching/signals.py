"""Evidence about each organization, gathered ahead of time and shipped with the package.

The official listing says what an organization calls itself. Two other public
sources say what it actually works on:

* its **ideas page**: how many ideas, the stated difficulty and size of each,
  and the skills and subjects they name, and
* its **GitHub repositories**: how many were pushed to in the last year, and
  their languages and topics.

Reading 183 ideas pages and as many repository lists takes minutes, so
`python -m git_into_gsoc.matching.signals` does it once and writes
``data/org_signals.json``. The snapshot-refresh workflow runs it on the first
Monday of each month (the organization snapshot itself is refreshed weekly).
Ranking reads that file offline and says how old it is. Nothing here is a
prediction: every number is a count of something a person can open and check.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from git_into_gsoc.coach import PROJECT_HOURS
from git_into_gsoc.matching.concepts import (
    SKILL,
    find_concepts,
    find_tag_concepts,
    kind_of,
    resolve,
)
from git_into_gsoc.matching.ideas import is_real_idea, skill_concepts

SIGNALS_FILE = "org_signals.json"
# MediaWiki section headings end in an "[edit]" link.
_EDIT_LINK = re.compile(r"\s*\[\s*edit(?:\s+source)?\s*\]\s*$", re.I)
MAX_IDEAS_KEPT = 40
MAX_TITLE = 100


def _data_dir() -> Path:
    return Path(str(resources.files("git_into_gsoc").joinpath("data")))


@lru_cache(maxsize=1)
def load_signals() -> dict[str, Any]:
    """``{"generated": date, "year": int, "organizations": {slug: {...}}}``, or empty."""
    path = _data_dir() / SIGNALS_FILE
    if not path.is_file():
        return {"generated": None, "year": None, "organizations": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"generated": None, "organizations": {}}


def signals_for(slug: str | None) -> dict[str, Any]:
    if not slug:
        return {}
    return dict((load_signals().get("organizations") or {}).get(slug) or {})


# ------------------------------------------------------------------ summarise


def _top(counter: Counter[str], n: int) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n])


def summarize_ideas(ideas: list[dict[str, Any]], *, layout: str, url: str) -> dict[str, Any]:
    """Counts and a short list from parsed ideas (dicts shaped like ProjectIdea).

    A parser sometimes splits one idea into blocks with titles such as
    "Description" or "Skills". Their text still counts as evidence, but they are
    left out of the idea count and the list of ideas shown to people.
    """
    real = [
        i
        for i in ideas
        if is_real_idea(
            str(i.get("title") or ""), labelled=bool(i.get("difficulty") or i.get("size"))
        )
    ]
    difficulty: Counter[str] = Counter()
    size: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    mentions: Counter[str] = Counter()
    mentors: set[str] = set()
    kept: list[dict[str, Any]] = []
    for idea in ideas:
        if idea.get("difficulty"):
            difficulty[str(idea["difficulty"])] += 1
        if idea.get("size"):
            size[str(idea["size"])] += 1
        labelled: set[str] = set()
        for skill in idea.get("skills") or []:
            labelled.update(skill_concepts(str(skill)))
        text = " ".join([str(idea.get("title") or ""), str(idea.get("description") or "")])
        named = set(find_concepts(text)) | labelled
        skills.update(labelled)
        mentions.update(named)
        mentors.update(str(m).lower() for m in idea.get("mentors") or [])
        if len(kept) < MAX_IDEAS_KEPT and any(idea is r for r in real):
            title = _EDIT_LINK.sub("", str(idea.get("title") or "")).strip()
            entry: dict[str, Any] = {"t": title[:MAX_TITLE]}
            if idea.get("difficulty"):
                entry["d"] = idea["difficulty"]
            if idea.get("size"):
                entry["s"] = idea["size"]
                # Hours the page states that are not the size's own (MetaBrainz's 300):
                # the time fit then uses them.
                if idea.get("hours") and idea["hours"] != PROJECT_HOURS.get(idea["size"]):
                    entry["h"] = idea["hours"]
            concepts = sorted(labelled) + sorted(named - labelled)
            if concepts:
                entry["k"] = concepts[:8]
            kept.append(entry)
    return {
        "url": url,
        "layout": layout,
        "count": len(real),
        # Every block the parser found, headings included: the base for evidence counts.
        "blocks": len(ideas),
        "difficulty": dict(difficulty),
        "size": dict(size),
        "skills": _top(skills, 20),
        "mentions": _top(mentions, 30),
        "mentors": len(mentors),
        "ideas": kept,
    }


def summarize_repos(
    repos: list[dict[str, Any]], owners: list[str], *, now: datetime
) -> dict[str, Any]:
    """Languages and topics of the repositories pushed to in the last year."""
    cutoff = now - timedelta(days=365)
    active = []
    for repo in repos:
        if repo.get("archived") or repo.get("fork"):
            continue
        pushed = str(repo.get("pushed_at") or "")
        try:
            when = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when >= cutoff:
            active.append(repo)
    languages: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    for repo in active:
        language = str(repo.get("language") or "")
        if language:
            languages[language] += 1
        named: set[str] = set()
        for topic in repo.get("topics") or []:
            named.update(find_tag_concepts(str(topic).replace("-", " ")))
        named.update(find_concepts(str(repo.get("description") or "")))
        topics.update(named)
    return {
        "owners": owners,
        "active_repos": len(active),
        "languages": _top(languages, 10),
        "concepts": _top(topics, 25),
    }


def language_concepts(languages: dict[str, int]) -> dict[str, int]:
    """GitHub language names ("Jupyter Notebook", "C++") as skill concepts."""
    out: Counter[str] = Counter()
    for name, count in languages.items():
        lowered = name.lower()
        key = "python" if lowered == "jupyter notebook" else None
        if key is None:
            found = resolve(lowered)
            key = next((k for k in found.concepts if kind_of(k) == SKILL), None)
            if found.corrected_from:
                key = None  # GitHub's names are exact; never guess at them
        if key:
            out[key] += int(count)
    return dict(out)


# ---------------------------------------------------------------------- build


def _ideas_for(toolkit: Any, raw: dict[str, Any], ttl: int) -> dict[str, Any] | None:
    # The same reading `ideas` shows: one reader, so the snapshot cannot drift from it.
    url = raw.get("ideas_link")
    if not url:
        return None
    doc, _ = toolkit.read_ideas_page(str(url), ttl=ttl)
    if doc is None:
        return {"url": url, "layout": "unreachable", "count": 0}
    return summarize_ideas([i.model_dump() for i in doc.ideas], layout=doc.layout, url=str(url))


# The labels recommend searches for its starter issues, so the count matches them.
BEGINNER_SEARCH_LABELS = (
    "good first issue",
    "good-first-issue",
    "starter",
    "beginner",
    "easy",
    "first-timers-only",
)


CANARY_SHARE = 0.8


def search_trustworthy(toolkit: Any, previous: dict[str, dict[str, Any]] | None = None) -> bool:
    """Whether this run's searches with an OR group can be trusted: a canary.

    One label alone, then that label OR another, over the same busy organization:
    a working engine never finds fewer for the OR. On the 2026-10-22 refresh, GitHub
    Actions' built-in token got empty or wrong answers to every OR group (40
    beginner-label counts went to 0, Apache's 1,929 to 28, and three participation
    statements were lost), while plain searches worked. When the canary fails, the
    run keeps last month's search results instead of replacing them.
    """
    busiest = max(
        (previous or {}).items(),
        key=lambda kv: int((kv[1].get("github") or {}).get("beginner_issues_year") or 0),
        default=("", {}),
    )[1]
    owner = ((busiest.get("github") or {}).get("owners") or ["fossasia"])[0]
    since = (datetime.now(UTC) - timedelta(days=365)).date().isoformat()
    one = toolkit.github.beginner_issues_opened([owner], since=since, labels=["good first issue"])
    either = toolkit.github.beginner_issues_opened(
        [owner], since=since, labels=["good first issue", "beginner"]
    )
    # Totals for big result sets are approximate (Apache: 1,864 alone, 1,862 with the
    # OR); the failure was far larger (1,929 to 28), so allow a small shortfall.
    return bool(one) and either is not None and either >= CANARY_SHARE * one


def _github_for(
    toolkit: Any, owners: list[str], now: datetime, *, searches: bool = True
) -> dict[str, Any] | None:
    """Repository evidence, or None when there are no owners or every listing failed."""
    from git_into_gsoc.errors import GigError

    if not owners:
        return None
    repos: list[dict[str, Any]] = []
    listed = 0
    for owner in owners[:3]:
        try:
            repos.extend(toolkit.github.list_owner_repos(owner))
            listed += 1
        except GigError:
            continue
    if not listed:
        return None
    summary = summarize_repos(repos, owners[:3], now=now)
    if not searches:
        return summary  # last month's count stands (see search_trustworthy)
    # Over the first three owners only (as the listing above), so for an organization
    # with more it is a lower bound; "N issues opened" stays true.
    labelled = toolkit.github.beginner_issues_opened(
        owners[:3],
        since=(now - timedelta(days=365)).date().isoformat(),
        labels=list(BEGINNER_SEARCH_LABELS),
    )
    if labelled is not None:
        summary["beginner_issues_year"] = labelled
    return summary


_FAILED_LAYOUTS = {"unreachable", "error"}


def keep_previous(
    fresh: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Where a page or API failed this time, keep what the last refresh found.

    One bad month must not wipe an organization's evidence from the shipped file.
    A page that cannot be fetched counts as failed, and so does a page at the same
    address that suddenly yields no ideas: some hosts serve automated readers in
    the cloud a stub page (BRL-CAD's and cBioPortal's did on GitHub's runners). A
    new address with no ideas yet, such as next year's page, is taken as it is.
    """
    merged: dict[str, dict[str, Any]] = {}
    for slug, entry in fresh.items():
        old = previous.get(slug) or {}
        kept = dict(entry)
        ideas = entry.get("ideas") or {}
        before = old.get("ideas") or {}
        emptied = not ideas.get("count") and ideas.get("url") == before.get("url")
        if before.get("count") and (ideas.get("layout") in _FAILED_LAYOUTS or emptied):
            kept["ideas"] = before
        if "github" not in entry and old.get("github"):
            kept["github"] = old["github"]
        elif "beginner_issues_year" in (old.get("github") or {}) and "beginner_issues_year" not in (
            kept.get("github") or {}
        ):
            # The count's search failed this time; last month's figure stands.
            kept["github"] = {
                **kept["github"],
                "beginner_issues_year": old["github"]["beginner_issues_year"],
            }
        failed = kept.pop("_participation_failed", False)
        if old.get("participation") and (failed or "participation" not in kept):
            # A statement not found again stays, with its old `checked` date: the
            # search reads only the newest issues, and a post does not stop being true
            # because it scrolled out of them. A newer statement replaces it.
            kept["participation"] = old["participation"]
        merged[slug] = kept
    return merged


_SAID = {"not_taking_part", "undecided", "posted", "reported"}


def _participation_for(toolkit: Any, owners: list[str], now: datetime) -> dict[str, Any]:
    """What an organization posted about the coming GSoC, for the evidence file.

    Only a statement is kept (sitting out, undecided, or a post about the year), so
    the file stays small and stable; a failed check is marked so the last one stays.
    """
    from git_into_gsoc.service import participation_from

    year = toolkit.settings.target_year
    found = participation_from(toolkit.gsoc_posts_for(owners[:3], year=year, bodies=True))
    if found["status"] == "unknown":
        return {"_participation_failed": True}
    if found["status"] not in _SAID:
        return {}
    said = {
        "status": found["status"],
        "url": found.get("url"),
        "year": year,
        "checked": now.date().isoformat(),
    }
    if found["status"] == "reported":
        said.update(
            quote=found.get("title"),
            date=found.get("date"),
            by_maintainer=found.get("by_maintainer"),
        )
    return {"participation": said}


def build_signals(
    official: list[dict[str, Any]],
    toolkit: Any,
    *,
    previous: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Ideas-page and GitHub evidence for each organization in the official list.

    Ideas pages are fetched without any GitHub credentials; only the repository
    listings go to the GitHub API. Failures keep the `previous` evidence.
    """
    from git_into_gsoc.gsoc.client import github_refs

    now = datetime.now(UTC)
    ttl = toolkit.settings.archive_ttl_seconds
    searches = search_trustworthy(toolkit, previous)
    if not searches:
        print(
            "Searches with an OR group failed the canary check: keeping last month's "
            "beginner-label counts and participation. Run the refresh with a personal "
            "read-only token to refresh them.",
            file=sys.stderr,
        )

    def one(raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        owners, _ = github_refs(
            raw.get("source_code"), raw.get("ideas_link"), raw.get("contributor_guidance_url")
        )
        entry: dict[str, Any] = {}
        try:
            ideas = _ideas_for(toolkit, raw, ttl)
        except Exception as exc:  # one broken page must not stop the refresh
            ideas = {"url": raw.get("ideas_link"), "layout": "error", "count": 0}
            print(f"ideas page failed for {raw.get('slug')}: {exc}", file=sys.stderr)
        if ideas:
            entry["ideas"] = ideas
        github = _github_for(toolkit, owners, now, searches=searches)
        if github:
            entry["github"] = github
        if owners:
            entry.update(
                _participation_for(toolkit, owners, now)
                if searches
                else {"_participation_failed": True}
            )
        return str(raw.get("slug") or raw.get("name")), entry

    with ThreadPoolExecutor(max_workers=8) as pool:
        fresh = dict(sorted(pool.map(one, official)))
    return keep_previous(fresh, previous or {})


def write_signals(payload: dict[str, Any], out: Path) -> Path:
    from git_into_gsoc.gsoc.snapshot import _write_json

    path = out / SIGNALS_FILE
    _write_json(path, payload, sort_keys=True)
    return path


def main(argv: list[str] | None = None) -> int:
    """Refresh ``data/org_signals.json`` from live sources (maintainers only)."""
    from git_into_gsoc.config import LATEST_ARCHIVED_YEAR, get_settings
    from git_into_gsoc.service import GSoCToolkit

    args = list(sys.argv[1:] if argv is None else argv)
    year = int(args[0]) if args else LATEST_ARCHIVED_YEAR
    # One search per organization for its posts about the coming year: stay a little
    # under GitHub's 30 searches a minute, so the whole list gets checked.
    os.environ.setdefault("GIG_SEARCH_MIN_INTERVAL_SECONDS", "2.5")
    get_settings.cache_clear()
    toolkit = GSoCToolkit()
    official = toolkit.official.organizations(year)
    if not official:
        print(f"No official organization list published for {year}", file=sys.stderr)
        return 1
    before = load_signals()
    previous = (before.get("organizations") or {}) if before.get("year") == year else {}
    payload = {
        "generated": datetime.now(UTC).date().isoformat(),
        "year": year,
        "organizations": build_signals(official, toolkit, previous=previous),
    }
    path = write_signals(payload, _data_dir())
    print(f"wrote {path} ({path.stat().st_size // 1024} KiB)")
    load_signals.cache_clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
