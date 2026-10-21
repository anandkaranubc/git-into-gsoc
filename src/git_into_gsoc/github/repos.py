"""Pure helpers for repository intelligence (no I/O, easy to test)."""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlparse

KNOWN_BOTS = {
    "dependabot",
    "renovate",
    "pre-commit-ci",
    "github-actions",
    "allcontributors",
    "codecov",
    "imgbot",
    "snyk-bot",
    "greenkeeper",
}
OUTSIDER_ROLES = {"CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}
MIN_OUTSIDER_SAMPLE = 10  # below this, the outsider merge rate is shown but not scored
MIN_REPLY_SAMPLE = 5  # below this, the first-reply time is shown but not scored
BEGINNER_LABELS = (
    "good first issue",
    "good-first-issue",
    "good first bug",
    "first-timers-only",
    "beginner",
    "beginner friendly",
    "beginner-friendly",
    "easy",
    "starter",
    "newcomer",
    "difficulty: easy",
    "level: easy",
)
TOOLCHAIN_FILES: dict[str, str] = {
    "pyproject.toml": "Python project (pyproject.toml)",
    "setup.py": "Python project (setup.py)",
    "requirements.txt": "Python requirements.txt",
    "environment.yml": "Conda environment.yml",
    "tox.ini": "tox test runner",
    "noxfile.py": "nox sessions",
    "package.json": "Node.js (package.json)",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "Yarn",
    "Cargo.toml": "Rust (Cargo)",
    "go.mod": "Go modules",
    "pom.xml": "Java (Maven)",
    "build.gradle": "JVM (Gradle)",
    "build.gradle.kts": "JVM (Gradle Kotlin)",
    "CMakeLists.txt": "C/C++ (CMake)",
    "meson.build": "Meson build",
    "Makefile": "Makefile targets",
    "Dockerfile": "Dockerfile",
    "docker-compose.yml": "Docker Compose",
    ".pre-commit-config.yaml": "pre-commit hooks (run before pushing)",
    "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)",
    "pubspec.yaml": "Dart/Flutter",
    "DESCRIPTION": "R package",
    "Project.toml": "Julia project",
}


def is_bot(user: dict[str, Any] | None) -> bool:
    """Bots by type, by the [bot] suffix, by a known list, or by a -bot/-ci/-robot name.

    Project bots such as sympy-bot or k8s-ci-robot are ordinary user accounts to
    the API, so the name heuristic is needed to keep them out of response times.
    """
    login = str((user or {}).get("login") or "").lower()
    if (user or {}).get("type") == "Bot" or login.endswith("[bot]"):
        return True
    if login in KNOWN_BOTS or login.removesuffix("-bot") in KNOWN_BOTS:
        return True
    return login.endswith(("-bot", "_bot", "-robot", "-ci", "-automation", "bot-ci"))


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


@dataclass(frozen=True)
class PullStats:
    sampled: int
    merge_rate: float | None
    median_hours: float | None  # merged PRs only: time to merge, not time to first reply
    outsider_sampled: int
    outsider_merge_rate: float | None
    outside_authors_merged: int  # distinct people without write access who got a PR merged
    median_first_response_hours: float | None = None  # outside PRs, first human reply
    first_response_sampled: int = 0  # outside PRs the reply figure is based on
    median_outsider_size: int | None = None  # lines changed in merged outside PRs
    insiders_known: bool = False


def _hours_between(start: str | None, end: str | None) -> float | None:
    a, b = _dt(start), _dt(end)
    return (b - a).total_seconds() / 3600 if a and b else None


def pull_stats(pulls: list[dict[str, Any]], *, insiders: frozenset[str] | None = None) -> PullStats:
    """Merge behaviour of closed PRs, ignoring bots, split by author association.

    GitHub evaluates ``author_association`` when the list is fetched, so anyone
    whose PR has merged shows as CONTRIBUTOR and FIRST_TIME_CONTRIBUTOR never
    appears on a merged PR. Outsiders are therefore everyone without write
    access (CONTRIBUTOR, NONE, first-timers), and breadth is measured as the
    number of distinct outside authors merged rather than "first-timers". When
    the repository's assignable users are known (GraphQL path), anyone in that
    set counts as an insider regardless of association.
    """
    human = [p for p in pulls if not is_bot(p.get("user"))]
    merged = [p for p in human if p.get("merged_at")]
    hours = [
        h
        for h in (_hours_between(p.get("created_at"), p.get("merged_at")) for p in merged)
        if h is not None
    ]

    def outsider(pull: dict[str, Any]) -> bool:
        login = str((pull.get("user") or {}).get("login") or "")
        if insiders is not None and login in insiders:
            return False
        return pull.get("author_association") in OUTSIDER_ROLES

    outsiders = [p for p in human if outsider(p)]
    outsider_merged = [p for p in outsiders if p.get("merged_at")]
    authors = {str((p.get("user") or {}).get("login")) for p in outsider_merged}
    responses = [
        h
        for h in (
            _hours_between(p.get("created_at"), p.get("first_response_at")) for p in outsiders
        )
        if h is not None
    ]
    sizes = [
        int(p.get("additions") or 0) + int(p.get("deletions") or 0)
        for p in outsider_merged
        if "additions" in p
    ]
    return PullStats(
        sampled=len(human),
        merge_rate=len(merged) / len(human) if human else None,
        median_hours=statistics.median(hours) if hours else None,
        outsider_sampled=len(outsiders),
        outsider_merge_rate=len(outsider_merged) / len(outsiders) if outsiders else None,
        outside_authors_merged=len(authors),
        median_first_response_hours=statistics.median(responses) if responses else None,
        first_response_sampled=len(responses),
        median_outsider_size=int(statistics.median(sizes)) if sizes else None,
        insiders_known=insiders is not None,
    )


def _number_from_url(url: str | None) -> int | None:
    tail = str(url or "").rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def attach_first_replies(
    pulls: list[dict[str, Any]], comments: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Fill ``first_response_at`` on PRs from repo-wide comment listings (REST, no token).

    ``comments`` are the newest issue comments and review comments of the whole
    repository, so only PRs created after the oldest comment in that window can be
    judged; older PRs are left untouched. Returns the PRs and how many were
    inside the window. Replies by the author or by bots do not count.
    """
    if not comments or not pulls:
        return pulls, 0
    stamps = [str(c.get("created_at")) for c in comments if c.get("created_at")]
    if not stamps:
        return pulls, 0
    window_start = min(stamps)
    earliest: dict[int, str] = {}
    by_number_author: dict[int, str] = {
        int(p["number"]): str((p.get("user") or {}).get("login") or "")
        for p in pulls
        if p.get("number") is not None
    }
    for comment in comments:
        number = _number_from_url(comment.get("issue_url") or comment.get("pull_request_url"))
        if number is None or number not in by_number_author:
            continue
        user = comment.get("user") or {}
        login = str(user.get("login") or "")
        if not login or login == by_number_author[number] or is_bot(user):
            continue
        at = str(comment.get("created_at") or "")
        if at and (number not in earliest or at < earliest[number]):
            earliest[number] = at
    covered = 0
    for pull in pulls:
        number = pull.get("number")
        created = str(pull.get("created_at") or "")
        if number is None or not created or created < window_start:
            continue
        covered += 1
        reply = earliest.get(int(number))
        if reply and reply >= created:
            pull["first_response_at"] = reply
    return pulls, covered


def pick_beginner_label(labels: list[dict[str, Any]]) -> str | None:
    names = {str(label.get("name") or "").lower(): str(label.get("name")) for label in labels}
    for wanted in BEGINNER_LABELS:
        if wanted in names:
            return names[wanted]
    for lower, original in names.items():
        if "good first" in lower or "beginner" in lower or "first-timer" in lower:
            return original
    return None


def detect_toolchain(entries: list[dict[str, Any]]) -> tuple[list[str], bool]:
    """Toolchain hints from a repo root listing, plus whether a dev container exists."""
    names = {str(e.get("name")) for e in entries}
    hints = [label for name, label in TOOLCHAIN_FILES.items() if name in names]
    return hints, ".devcontainer" in names or ".devcontainer.json" in names


def contributing_path(profile: dict[str, Any]) -> str | None:
    """Repo-relative path of CONTRIBUTING from a community-profile payload."""
    html_url = ((profile.get("files") or {}).get("contributing") or {}).get("html_url")
    if not html_url:
        return None
    parts = urlparse(str(html_url)).path.split("/")
    if "blob" in parts:
        index = parts.index("blob")
        return unquote("/".join(parts[index + 2 :])) or None
    return None


_CHANNEL_NEEDLES = {
    "discord": "Discord",
    "slack": "Slack",
    "zulip": "Zulip",
    "matrix": "Matrix",
    "element.io": "Matrix",
    "gitter": "Gitter",
    "irc": "IRC",
    "mailing list": "Mailing list",
    "discourse": "Discourse forum",
    "discussions": "GitHub Discussions",
}


def channels_in(text: str) -> list[str]:
    lower = text.lower()
    return list(dict.fromkeys(name for needle, name in _CHANNEL_NEEDLES.items() if needle in lower))


def repo_lead_score(
    repo: dict[str, Any],
    *,
    beginner_issues: int,
    ideas_mention: bool,
    language: str | None,
    now: datetime | None = None,
) -> tuple[float, list[str]]:
    now = now or datetime.now(UTC)
    score = 0.0
    reasons: list[str] = []
    if ideas_mention:
        score += 35
        reasons.append("Named on the GSoC ideas page")
    if beginner_issues:
        score += min(25.0, 6 * math.log2(1 + beginner_issues))
        reasons.append(f"{beginner_issues} open beginner issue(s)")
    pushed = _dt(repo.get("pushed_at"))
    if pushed:
        days = (now - pushed).days
        if days <= 14:
            score += 15
            reasons.append("Pushed in the last 2 weeks")
        elif days <= 90:
            score += 8
            reasons.append(f"Pushed {days}d ago")
    stars = int(repo.get("stargazers_count") or 0)
    score += min(12.0, 1.5 * math.log2(1 + stars))
    if language and str(repo.get("language") or "").lower() == language.lower():
        score += 10
        reasons.append(f"Written in {repo.get('language')}")
    return round(score, 1), reasons


def mentioned_repos(text: str, owners: list[str], repos: list[dict[str, Any]]) -> set[str]:
    """Repos referenced on an ideas page by URL or (distinctive) name."""
    found: set[str] = set()
    lower = text.lower()
    for owner in owners:
        for match in re.findall(rf"github\.com/{re.escape(owner.lower())}/([a-z0-9._-]+)", lower):
            found.add(f"{owner.lower()}/{match.removesuffix('.git')}")
    for repo in repos:
        name = str(repo.get("name") or "").lower()
        if len(name) >= 5 and re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", lower):
            found.add(str(repo.get("full_name") or "").lower())
    return found
