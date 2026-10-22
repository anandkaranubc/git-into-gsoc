"""Issue-to-code pointers: where to start reading for one issue, with evidence.

Nothing here suggests a fix. It extracts paths, stack frames, blob links and
identifiers from the issue text, resolves them against the repository tree,
and learns from past fixes: which pull requests closed similar labelled
issues and what those PRs touched. Every pointer carries its reason and a
confidence label so a beginner can judge it.
"""

from __future__ import annotations

import re
import statistics
from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.text import clean_untrusted

SOURCE_EXTENSIONS = (
    "py|pyx|pyi|js|jsx|ts|tsx|mjs|cjs|go|rs|c|cc|cpp|cxx|h|hpp|java|kt|rb|php|cs|swift|scala|"
    "m|mm|sh|ps1|r|jl|lua|dart|ex|exs|erl|hs|ml|md|rst|txt|yml|yaml|toml|json|ini|cfg|xml|html|css|scss"
)
_BLOB_RE = re.compile(
    r"https?://github\.com/([\w.-]+/[\w.-]+)/blob/[^/\s]+/([^\s#)\]>\"']+)(?:#L(\d+))?", re.I
)
_FRAME_RE = re.compile(r"File \"([^\"]+)\", line (\d+)")
_FRAME_AT_RE = re.compile(r"\bat\s+(?:[\w.$<>]+\s+\()?((?:[\w.-]+/)+[\w.-]+):(\d+)")
_PATH_RE = re.compile(rf"(?<![\w/@])((?:[\w.-]+/)*[\w-]+\.(?:{SOURCE_EXTENSIONS}))\b")
_BACKTICK_RE = re.compile(r"`(\S[^`\n]{1,78}\S)`")
_IDENT_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*(?:_[A-Za-z0-9]+)+|[a-z]+(?:[A-Z][a-z0-9]+){2,})\b"
)
_STOP_WORDS = {
    "github",
    "python",
    "javascript",
    "typescript",
    "error",
    "traceback",
    "import",
    "module",
    "issue",
    "pull",
    "request",
    "version",
    "latest",
    "master",
    "main",
    "function",
    "class",
}
_WEIGHTS = {"blob_url": 5.0, "stack_frame": 3.0, "path": 1.5, "backtick": 2.0, "identifier": 1.0}
_IGNORED_DIRS = ("node_modules/", "vendor/", "third_party/", "extern/", "dist/", "build/")
_DOCS_RE = re.compile(r"(?:^|/)(?:docs?|changelog|whats_new|news|release|readme)[^/]*", re.I)
_TESTS_RE = re.compile(
    r"(?:^|/)(?:tests?|specs?|__tests__|testing|testsuite|autotests?|unittests?|e2e)(?:/|$)"
    r"|(?:^|/)test_[^/]+$|_test\.[a-z]+$|\.(?:test|spec)\.[a-z]+$|_spec\.rb$",
    re.I,
)
CLOSING_WINDOW_SECONDS = 5


def extract_mentions(
    text: str, *, repo: str | None = None, limit: int = 30
) -> list[dict[str, Any]]:
    """Paths, stack frames, blob links and identifiers mentioned in an issue, weighted."""
    text = text or ""
    found: dict[str, dict[str, Any]] = {}

    def add(kind: str, value: str, line: int | None = None) -> None:
        value = value.strip().strip(".,;:")
        if not value:
            return
        key = value
        entry = found.get(key)
        if entry is None:
            entry = {"text": value, "kind": kind, "weight": 0.0, "line": line, "count": 0}
            found[key] = entry
        entry["weight"] += _WEIGHTS[kind]
        entry["count"] += 1
        if line and not entry.get("line"):
            entry["line"] = line
        if _WEIGHTS[kind] > _WEIGHTS[entry["kind"]]:
            entry["kind"] = kind

    for match in _BLOB_RE.finditer(text):
        if repo and match.group(1).lower() != repo.lower():
            continue
        add("blob_url", match.group(2), int(match.group(3)) if match.group(3) else None)
    for match in _FRAME_RE.finditer(text):
        add("stack_frame", match.group(1), int(match.group(2)))
    for match in _FRAME_AT_RE.finditer(text):
        add("stack_frame", match.group(1), int(match.group(2)))
    stripped = _BLOB_RE.sub(" ", _FRAME_RE.sub(" ", text))
    for match in _PATH_RE.finditer(stripped):
        value = match.group(1)
        if value.lower() in {"readme.md", "contributing.md"} or value.count(".") > 3:
            continue
        add("path", value)
    for match in _BACKTICK_RE.finditer(stripped):
        value = match.group(1).strip()
        if value.startswith("-") or (" " in value and not _PATH_RE.fullmatch(value)):
            continue
        if _PATH_RE.fullmatch(value):
            add("path", value)
        elif (
            re.fullmatch(r"[A-Za-z_][\w.]*", value)
            and len(value) >= 3
            and value.lower() not in _STOP_WORDS
        ):
            add("backtick", value)
    for match in _IDENT_RE.finditer(stripped):
        value = match.group(1)
        if len(value) >= 8 and value.lower() not in _STOP_WORDS and not value.startswith("http"):
            add("identifier", value)
    ranked = sorted(found.values(), key=lambda m: (-m["weight"], m["text"]))
    return ranked[:limit]


def _name_key(name: str) -> str:
    """distance_transform, DistanceTransform, and distance-transform compare equal."""
    return name.replace("_", "").replace("-", "").lower()


_PROSE_RE = re.compile(r"\.(?:md|rst|txt|adoc)$|(?:^|/)(?:contributing|changelog|readme)", re.I)


def code_first(paths: list[str]) -> list[str]:
    """Code files before docs, changelogs, and release notes, keeping search order.

    Code search for kornia's distance_transform found the real file, then two
    changelog entries; a beginner looking for where to start reading needs code.
    """
    return sorted(paths, key=lambda p: bool(_PROSE_RE.search(p) or _DOCS_RE.search(p)))


def resolve_paths(
    mentions: list[dict[str, Any]], tree_paths: list[str], *, limit: int = 8
) -> list[dict[str, Any]]:
    """Match mentioned paths against the real tree: exact, then suffix, then basename."""
    by_path: dict[str, dict[str, Any]] = {}
    lower_tree = [p for p in tree_paths if not p.startswith(_IGNORED_DIRS)]
    by_basename: dict[str, list[str]] = {}
    by_stem: dict[str, list[str]] = {}
    for path in lower_tree:
        name = path.rsplit("/", 1)[-1]
        by_basename.setdefault(name.lower(), []).append(path)
        by_stem.setdefault(_name_key(name.split(".", 1)[0]), []).append(path)

    def record(path: str, mention: dict[str, Any], how: str, factor: float) -> None:
        entry = by_path.setdefault(
            path, {"path": path, "score": 0.0, "lines": [], "reasons": [], "confidence": how}
        )
        entry["score"] += mention["weight"] * factor
        if mention.get("line") and mention["line"] not in entry["lines"]:
            entry["lines"].append(mention["line"])
        reason = f"{mention['kind'].replace('_', ' ')}: {mention['text']}"
        if reason not in entry["reasons"]:
            entry["reasons"].append(reason)
        order = [
            "blob link",
            "stack trace",
            "exact path",
            "suffix match",
            "basename match",
            "file name match",
        ]
        if order.index(how) < order.index(entry["confidence"]):
            entry["confidence"] = how

    tree_set = set(lower_tree)
    for mention in mentions:
        if mention["kind"] in {"identifier", "backtick"} and not _PATH_RE.fullmatch(
            mention["text"]
        ):
            # kornia's "distance_transform bug" names kornia/contrib/distance_transform.py.
            # Matching file names needs no code search, so it works without a token.
            key = _name_key(mention["text"])
            hits = by_stem.get(key, []) if len(key) >= 6 else []
            if 0 < len(hits) <= 3:
                for hit in hits:
                    record(hit, mention, "file name match", 0.6)
            continue
        value = mention["text"].replace("\\", "/").lstrip("./")
        how = {"blob_url": "blob link", "stack_frame": "stack trace"}.get(
            mention["kind"], "exact path"
        )
        if value in tree_set:
            record(value, mention, how, 1.0)
            continue
        suffix_hits = [p for p in lower_tree if p.endswith("/" + value) or p == value]
        if not suffix_hits:
            parts = value.split("/")
            for size in range(len(parts) - 1, 0, -1):
                tail = "/".join(parts[-size:])
                suffix_hits = [p for p in lower_tree if p.endswith("/" + tail) or p == tail]
                if suffix_hits:
                    break
        if suffix_hits and len(suffix_hits) <= 3:
            for hit in suffix_hits:
                record(
                    hit,
                    mention,
                    how if mention["kind"] in {"blob_url", "stack_frame"} else "suffix match",
                    0.8,
                )
            continue
        base_hits = by_basename.get(value.rsplit("/", 1)[-1].lower(), [])
        if 0 < len(base_hits) <= 2:
            for hit in base_hits:
                record(hit, mention, "basename match", 0.4)
    ranked = sorted(by_path.values(), key=lambda e: (-e["score"], e["path"]))
    for entry in ranked:
        entry["score"] = round(entry["score"], 1)
        entry["lines"] = sorted(entry["lines"])[:5]
    return ranked[:limit]


# Words that say little about where in the code an issue lives.
_TITLE_FILLER = {
    "a",
    "add",
    "adds",
    "after",
    "all",
    "an",
    "and",
    "are",
    "as",
    "be",
    "bug",
    "but",
    "by",
    "can",
    "cannot",
    "do",
    "does",
    "doesn",
    "for",
    "from",
    "get",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "join",
    "make",
    "missing",
    "more",
    "new",
    "no",
    "not",
    "of",
    "on",
    "one",
    "or",
    "out",
    "should",
    "some",
    "support",
    "that",
    "the",
    "this",
    "to",
    "two",
    "up",
    "use",
    "using",
    "when",
    "while",
    "with",
    "fix",
    "fixes",
    "methods",
    "method",
    "update",
    "improve",
    "allow",
    "option",
    "version",
    "work",
    "works",
    "find",
    "bugs",
    "crash",
    "crashes",
    "wrong",
    "broken",
    "fails",
    "failing",
    "incorrect",
    "error",
    "errors",
    "issue",
    "issues",
    "rewrite",
    "system",
}


def title_keywords(title: str, *, limit: int = 2, exclude: tuple[str, ...] = ()) -> list[str]:
    """The most distinctive words of an issue title, for a code search when no file is named.

    Longer words first: "assumption" says more about where to look than "find".
    """
    skip = _TITLE_FILLER | _STOP_WORDS | {e.lower() for e in exclude}
    words = re.findall(r"[a-z][a-z0-9_]+", (title or "").lower())
    picked = list(dict.fromkeys(w for w in words if len(w) >= 4 and w not in skip))
    return sorted(picked, key=lambda w: -len(w))[:limit]


def rank_similar(
    title: str, items: list[dict[str, Any]], *, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    """Closed issues sharing the most title words first; False when none share any."""
    wanted = set(title_keywords(title, limit=6))

    def shared(item: dict[str, Any]) -> int:
        return len(wanted & set(title_keywords(str(item.get("title") or ""), limit=6)))

    scored = [(shared(item), index, item) for index, item in enumerate(items)]
    if not any(score for score, _, _ in scored):
        return items[:limit], False
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [item for _, _, item in scored[:limit]], True


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def closing_pull_request(
    issue: dict[str, Any], timeline: list[dict[str, Any]], *, repo: str
) -> dict[str, Any] | None:
    """The same-repo merged PR that closed the issue (merged within seconds of the close),
    else the most recent same-repo merged PR before the close as a 'likely fix'."""
    closed_at = _dt(issue.get("closed_at"))
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for event in timeline:
        if event.get("event") != "cross-referenced":
            continue
        source = (event.get("source") or {}).get("issue") or {}
        pr = source.get("pull_request") or {}
        if not pr or not pr.get("merged_at"):
            continue
        full = str((source.get("repository") or {}).get("full_name") or "")
        if full and full.lower() != repo.lower():
            continue
        merged_at = _dt(pr.get("merged_at"))
        if merged_at is None or not source.get("number"):
            continue
        candidates.append(
            (
                merged_at,
                {
                    "number": int(source["number"]),
                    "url": source.get("html_url"),
                    "title": clean_untrusted(source.get("title"), limit=120),
                    "author": (source.get("user") or {}).get("login"),
                    "merged_at": merged_at.isoformat(),
                    "opened_at": (_dt(source.get("created_at")) or merged_at).isoformat(),
                },
            )
        )
    if not candidates:
        return None
    if closed_at is not None:
        for merged_at, pr in candidates:
            if abs((merged_at - closed_at).total_seconds()) <= CLOSING_WINDOW_SECONDS:
                return {**pr, "confidence": "closing PR"}
        before = [(m, pr) for m, pr in candidates if m <= closed_at]
        if before:
            merged_at, pr = max(before, key=lambda item: item[0])
            return {**pr, "confidence": "likely fix"}
    merged_at, pr = max(candidates, key=lambda item: item[0])
    return {**pr, "confidence": "likely fix"}


def fix_norm(fixes: list[dict[str, Any]]) -> dict[str, Any]:
    """What fixes of similar issues look like here: files touched, tests, docs."""
    samples = [f for f in fixes if f.get("files")]
    if not samples:
        return {"sample": 0}
    counts = [len(f["files"]) for f in samples]
    tests = sum(1 for f in samples if any(_TESTS_RE.search(p) for p in f["files"]))
    docs = sum(1 for f in samples if any(_DOCS_RE.search(p) for p in f["files"]))
    dirs: dict[str, int] = {}
    for fix in samples:
        for path in fix["files"]:
            top = path.rsplit("/", 1)[0] if "/" in path else "."
            dirs[top] = dirs.get(top, 0) + 1
    common = sorted(dirs.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {
        "sample": len(samples),
        "median_files": int(statistics.median(counts)),
        "max_files": max(counts),
        "touches_tests_pct": round(100 * tests / len(samples)),
        "touches_docs_pct": round(100 * docs / len(samples)),
        "common_directories": [{"path": d, "fixes": n} for d, n in common],
    }


def days_between(start: str | None, end: str | None) -> int | None:
    a, b = _dt(start), _dt(end)
    if a is None or b is None:
        return None
    return max(0, round((b - a).total_seconds() / 86400))
