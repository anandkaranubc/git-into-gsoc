"""Check a pull request against the repository's own rules before a reviewer does.

`orient` reads what a repository expects (sign-off, changelog entries, tests,
the pull request template, AI disclosure, gates that close pull requests).
This module applies those expectations to one real pull request and reports
pass, warn, and fail findings with the evidence behind each. It never edits
anything; the contributor fixes their own branch. The idea comes from
ContribOS's pre-submit `check` (MIT); this version works from the GitHub API
alone, without a clone.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from git_into_gsoc.github.orientation import CONVENTIONAL_RE
from git_into_gsoc.github.pulls import FAILED_CONCLUSIONS

Status = Literal["pass", "warn", "fail"]

# Research behind the size check: first patches that land are small (Turzo,
# Sultana and Bosu 2025). These are gentle limits, not rules.
LARGE_LINES = 400
LARGE_FILES = 15

_ISSUE_REF_RE = re.compile(
    r"(?:\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|part of|refs?|see)\s+)?"
    r"(?:[\w.-]+/[\w.-]+)?#\d+|github\.com/[\w.-]+/[\w.-]+/issues/\d+",
    re.I,
)
_ITEM_RE = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+)$", re.M)
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_EMPHASIS_RE = re.compile(r"(?<![\w*])(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1(?![\w*])")
_AI_MENTION_RE = re.compile(
    r"\b(?:ai|llm|chatgpt|copilot|claude|gemini|cursor|assisted-by|generated)\b", re.I
)
_RELEASE_NOTE_RE = re.compile(r"release notes?|changelog|news entry|whats.?new", re.I)
_TEST_PATH_RE = re.compile(
    r"(?:^|/)(?:tests?|spec|__tests__|testing)(?:/|$)|(?:^|/)test_[^/]+$|_test\.[a-z]+$|"
    r"\.(?:test|spec)\.[a-z]+$|Test\.java$",
    re.I,
)
_PROSE_FILE_RE = re.compile(r"\.(?:md|rst|txt|adoc)$", re.I)
_DOC_PATH_RE = re.compile(
    r"(?:^|/)(?:docs?|documentation)(?:/|$)|\.(?:md|rst|txt|adoc)$|(?:^|/)(?:readme|changelog)",
    re.I,
)
_CHANGELOG_PATH_RE = re.compile(r"(?:^|/)(?:changelog|changes|news|history|whats_?new)", re.I)


@dataclass
class Finding:
    id: str
    status: Status
    title: str
    detail: str


def _is_code(path: str) -> bool:
    return not _TEST_PATH_RE.search(path) and not _DOC_PATH_RE.search(path)


def _plain(text: str) -> str:
    text = _MD_EMPHASIS_RE.sub(r"\2", _MD_LINK_RE.sub(r"\1", text))
    return re.sub(r"\s+", " ", text).strip()


def _short(text: str, limit: int = 90) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


def unticked_items(body: str) -> list[str]:
    """Checklist items left unticked, in plain text.

    Templates sometimes offer exclusive options ("*either* no AI was used" /
    "*or* AI use is disclosed below"). Ticking one option settles the group; a
    group with none ticked is reported once, by its first option.
    """
    items = [(mark != " ", _plain(text)) for mark, text in _ITEM_RE.findall(body)]
    unticked: list[str] = []
    i = 0
    while i < len(items):
        group = [items[i]]
        if items[i][1].lower().startswith("either"):
            while i + len(group) < len(items) and re.match(r"or\b", items[i + len(group)][1], re.I):
                group.append(items[i + len(group)])
        if not any(ticked for ticked, _ in group):
            unticked.append(group[0][1])
        i += len(group)
    return unticked


def check_pull_request(
    pull: dict[str, Any],
    files: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    rules: dict[str, Any],
    pr_template: str = "",
    test_dirs: list[str] | None = None,
    news_dir: str | None = None,
) -> dict[str, Any]:
    """Findings for one pull request, given the repository's rules from `conventions()`.

    `rules` is the dictionary `orient` builds, including `gates`. Every finding
    says what was looked at, so the contributor can check it themselves.
    """
    findings: list[Finding] = []
    body = str(pull.get("body") or "")
    title = str(pull.get("title") or "")
    base = str((pull.get("base") or {}).get("ref") or "the default branch")
    paths = [str(f.get("filename") or "") for f in files if f.get("filename")]
    gates = rules.get("gates") or []

    if pull.get("merged_at"):
        findings.append(Finding("state", "pass", "Already merged", "Nothing left to check."))
    elif str(pull.get("state") or "") == "closed":
        findings.append(
            Finding(
                "state",
                "warn",
                "Closed without merging",
                "Read the last comments to see why before opening a new one.",
            )
        )

    if str(pull.get("mergeable_state") or "").lower() == "dirty":
        findings.append(
            Finding(
                "conflict",
                "fail",
                f"Merge conflict with {base}",
                f"Rebase your branch on {base}, resolve the conflict, and push.",
            )
        )

    failing = sorted(
        {
            str(c.get("name"))
            for c in checks
            if str(c.get("conclusion") or "").lower() in FAILED_CONCLUSIONS and c.get("name")
        }
    )
    if failing:
        # Commit statuses (Prow, Jenkins) link their own log pages; GitHub Actions logs
        # are read separately.
        links = {
            str(c.get("name")): str(c["url"])
            for c in checks
            if c.get("url") and str(c.get("name")) in failing
        }
        logs = "; ".join(f"{name}: {url}" for name, url in list(links.items())[:4])
        findings.append(
            Finding(
                "checks",
                "fail",
                "Failing checks: " + ", ".join(failing[:4]),
                f"Read each log, and check whether the same job also fails on {base} before changing code."
                + (f" Logs: {logs}." if logs else ""),
            )
        )
    elif checks:
        findings.append(
            Finding(
                "checks",
                "pass",
                "Checks are passing or still running",
                f"{len(checks)} check run(s) on the latest commit.",
            )
        )

    issue_gate = next((g for g in gates if "reference an issue" in g.get("gate", "")), None)
    if _ISSUE_REF_RE.search(body):
        findings.append(
            Finding("issue_link", "pass", "Links an issue", "The description references an issue.")
        )
    elif issue_gate:
        findings.append(
            Finding(
                "issue_link",
                "fail",
                "No linked issue, and this repository requires one",
                f"{issue_gate['gate']} ({issue_gate['source']}). Add 'Fixes #N' to the description.",
            )
        )
    else:
        findings.append(
            Finding(
                "issue_link",
                "warn",
                "No linked issue",
                "Add 'Fixes #N' (or 'Part of #N') so reviewers see the context and the issue closes on merge.",
            )
        )

    if len(re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()) < 40:
        findings.append(
            Finding(
                "description",
                "warn",
                "The description is very short",
                "Say what was wrong, what you changed and why, and how you tested it.",
            )
        )

    template_items = len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", pr_template, flags=re.M))
    unchecked = unticked_items(body)
    if template_items and not _ITEM_RE.search(body):
        findings.append(
            Finding(
                "checklist",
                "warn",
                "The template's checklist is missing",
                f"The pull request template has a {template_items}-item checklist; copy it in and tick what you did.",
            )
        )
    elif unchecked:
        shown = "; ".join(_short(item).rstrip(".") for item in unchecked[:3])
        findings.append(
            Finding(
                "checklist",
                "warn",
                f"{len(unchecked)} checklist item(s) unticked",
                f"{shown}. Tick them, or say why they do not apply.",
            )
        )

    if rules.get("ai_disclosure_in_pr_template") and not _AI_MENTION_RE.search(body):
        findings.append(
            Finding(
                "ai_disclosure",
                "warn",
                "No AI disclosure",
                "The template asks whether AI tools were used. Answer it honestly, even if the answer is none.",
            )
        )

    dco = (rules.get("dco") or {}).get("required")
    if dco and commits:
        unsigned = [
            c
            for c in commits
            if "Signed-off-by:" not in str((c.get("commit") or {}).get("message") or "")
        ]
        if unsigned:
            findings.append(
                Finding(
                    "sign_off",
                    "fail",
                    f"{len(unsigned)} of {len(commits)} commit(s) lack a sign-off",
                    f"This repository requires Signed-off-by lines. Run `git rebase --signoff origin/{base}` and push with --force-with-lease.",
                )
            )
        else:
            findings.append(
                Finding(
                    "sign_off",
                    "pass",
                    "Every commit is signed off",
                    "Signed-off-by found on each commit.",
                )
            )

    if (rules.get("conventional_commits") or {}).get("expected"):
        subjects = [
            str((c.get("commit") or {}).get("message") or "").splitlines()[0]
            for c in commits
            if (c.get("commit") or {}).get("message")
        ]
        off = [s for s in subjects if not CONVENTIONAL_RE.match(s)]
        if not CONVENTIONAL_RE.match(title) and off:
            findings.append(
                Finding(
                    "commit_style",
                    "warn",
                    "Title and commits do not use type(scope): subject",
                    f"Most commits here do (for example 'fix(parser): ...'). Your title: '{title[:70]}'.",
                )
            )

    code = [p for p in paths if _is_code(p)]
    # docs/testing/manual-testing.md is a page about testing, not a test.
    tests = [p for p in paths if _TEST_PATH_RE.search(p) and not _PROSE_FILE_RE.search(p)]
    if code and not tests:
        where = f" (tests here live in {', '.join((test_dirs or [])[:2])}/)" if test_dirs else ""
        findings.append(
            Finding(
                "tests",
                "warn",
                "Code changed but no tests changed",
                f"Add or update a test that fails without your change{where}.",
            )
        )
    elif tests:
        findings.append(Finding("tests", "pass", "Includes test changes", ", ".join(tests[:3])))

    changelog = rules.get("changelog") or {}
    if changelog.get("expected"):
        in_dir = bool(news_dir) and any(p.startswith(f"{news_dir}/") for p in paths)
        touched = in_dir or any(_CHANGELOG_PATH_RE.search(p) for p in paths)
        in_body = bool(_RELEASE_NOTE_RE.search(body)) and not news_dir
        if touched or in_body:
            findings.append(
                Finding(
                    "changelog",
                    "pass",
                    "Has a changelog or release-notes entry",
                    "Found in the changed files or the description.",
                )
            )
        else:
            where = (
                f"a new file in {news_dir}/"
                if news_dir
                else "the entry the contributing guide or template asks for"
            )
            findings.append(
                Finding(
                    "changelog",
                    "warn",
                    "No changelog entry",
                    f"This repository expects {where}; "
                    + "; ".join(changelog.get("evidence") or []),
                )
            )

    lines = int(pull.get("additions") or 0) + int(pull.get("deletions") or 0)
    changed = int(pull.get("changed_files") or len(paths))
    if lines > LARGE_LINES or changed > LARGE_FILES:
        findings.append(
            Finding(
                "size",
                "warn",
                f"Large: {lines} lines in {changed} files",
                "First pull requests that land are usually small. Consider splitting it, or say in the description why it cannot be.",
            )
        )

    if pull.get("draft"):
        findings.append(
            Finding(
                "draft",
                "warn",
                "Still a draft",
                "Mark it ready for review when the checks pass and the findings above are handled.",
            )
        )

    fails = sum(1 for f in findings if f.status == "fail")
    warns = sum(1 for f in findings if f.status == "warn")
    if fails:
        verdict = f"Fix {fails} problem(s) before asking for review."
    elif warns:
        verdict = (
            "No blockers. Read the warnings: each one is a common reason for another review round."
        )
    else:
        verdict = "Ready for review by these checks. Reviewers still decide."
    return {
        "findings": [asdict(f) for f in findings],
        "verdict": verdict,
        "what_happens_next": [
            g["gate"] for g in gates if "reference an issue" not in g.get("gate", "")
        ],
        "files_changed": len(paths),
        "lines_changed": lines,
    }
