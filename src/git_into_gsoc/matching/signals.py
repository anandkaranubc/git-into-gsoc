"""Evidence about each organization, gathered ahead of time and shipped with the package.

The official listing says what an organization calls itself. Two other public
sources say what it actually works on:

* its **ideas page**: how many ideas, the stated difficulty and size of each,
  and the skills and subjects they name, and
* its **GitHub repositories**: how many were pushed to in the last year, and
  their languages and topics.

Reading 183 ideas pages and as many repository lists takes minutes, so
`python -m git_into_gsoc.matching.signals` does it once (weekly, with the
organization snapshot) and writes ``data/org_signals.json``. Ranking reads
that file offline and says how old it is. Nothing here is a prediction: every
number is a count of something a person can open and check.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from git_into_gsoc.matching.concepts import (
    SKILL,
    find_concepts,
    find_tag_concepts,
    kind_of,
    resolve,
)

SIGNALS_FILE = "org_signals.json"
MAX_IDEAS_KEPT = 40
MAX_TITLE = 100
_FOLLOW_SUB_PAGES = 8


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
    """Counts and a short list from parsed ideas (dicts shaped like ProjectIdea)."""
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
            labelled.update(find_tag_concepts(str(skill)))
        text = " ".join([str(idea.get("title") or ""), str(idea.get("description") or "")])
        named = set(find_concepts(text)) | labelled
        skills.update(labelled)
        mentions.update(named)
        mentors.update(str(m).lower() for m in idea.get("mentors") or [])
        if len(kept) < MAX_IDEAS_KEPT:
            entry: dict[str, Any] = {"t": str(idea.get("title") or "")[:MAX_TITLE]}
            if idea.get("difficulty"):
                entry["d"] = idea["difficulty"]
            if idea.get("size"):
                entry["s"] = idea["size"]
            concepts = sorted(labelled) + sorted(named - labelled)
            if concepts:
                entry["k"] = concepts[:8]
            kept.append(entry)
    return {
        "url": url,
        "layout": layout,
        "count": len(ideas),
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
    from git_into_gsoc.gsoc.project_ideas import fetch_ideas_document, issues_page_target
    from git_into_gsoc.service import _looks_like_ideas_page

    url = raw.get("ideas_link")
    if not url:
        return None
    target = issues_page_target(url)
    doc = (
        toolkit._ideas_from_issues(url, *target)
        if target
        else fetch_ideas_document(toolkit.http, url, ttl)
    )
    if doc is None:
        return {"url": url, "layout": "unreachable", "count": 0}
    if doc.layout == "index" and doc.sub_pages:
        followed = 0
        for page in [p for p in doc.sub_pages if _looks_like_ideas_page(p)][:_FOLLOW_SUB_PAGES]:
            child = fetch_ideas_document(toolkit.http, page["url"], ttl)
            if child is not None and child.ideas:
                doc.ideas.extend(child.ideas)
                followed += 1
        if not followed and doc.fallback_ideas:
            doc.ideas = list(doc.fallback_ideas)
            doc.layout = "headings"
    return summarize_ideas([i.model_dump() for i in doc.ideas], layout=doc.layout, url=str(url))


def _github_for(toolkit: Any, owners: list[str], now: datetime) -> dict[str, Any] | None:
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
    return summarize_repos(repos, owners[:3], now=now)


_FAILED_LAYOUTS = {"unreachable", "error"}


def keep_previous(
    fresh: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Where a page or API failed this time, keep what the last refresh found.

    One bad week must not wipe an organization's evidence from the shipped file.
    """
    merged: dict[str, dict[str, Any]] = {}
    for slug, entry in fresh.items():
        old = previous.get(slug) or {}
        kept = dict(entry)
        ideas = entry.get("ideas") or {}
        if ideas.get("layout") in _FAILED_LAYOUTS and (old.get("ideas") or {}).get("count"):
            kept["ideas"] = old["ideas"]
        if "github" not in entry and old.get("github"):
            kept["github"] = old["github"]
        merged[slug] = kept
    return merged


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
        github = _github_for(toolkit, owners, now)
        if github:
            entry["github"] = github
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
    from git_into_gsoc.config import LATEST_ARCHIVED_YEAR
    from git_into_gsoc.service import GSoCToolkit

    args = list(sys.argv[1:] if argv is None else argv)
    year = int(args[0]) if args else LATEST_ARCHIVED_YEAR
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
