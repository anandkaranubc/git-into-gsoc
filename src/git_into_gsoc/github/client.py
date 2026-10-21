"""GitHub REST API client focused on contributor intelligence."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.models import Availability, ContributionGuide, IssueCandidate, RepoHealth
from git_into_gsoc.scoring.health import score_repo_health
from git_into_gsoc.scoring.issues import score_issue

BEGINNER_LABELS = (
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner friendly",
    "beginner-friendly",
    "easy",
    "starter",
    "first-timers-only",
    "hacktoberfest",
    "help wanted",
    "help-wanted",
    "newcomer",
    "gsoc",
    "outreachy",
)

COMMUNITY_FILE_CANDIDATES = (
    "CONTRIBUTING.md",
    "CONTRIBUTING.rst",
    "CONTRIBUTING",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/CODE_OF_CONDUCT.md",
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _excerpt(text: str | None, limit: int = 400) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


class GitHubClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http: CachedHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)
        self.token = self.settings.resolve_github_token()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _api(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.github_api_url.rstrip('/')}/{path.lstrip('/')}"
        return self.http.get_json(url, headers=self._headers(), params=params)

    def rate_limit(self) -> dict[str, Any]:
        data = self._api("rate_limit")
        core = data.get("resources", {}).get("core", {})
        return {
            "limit": core.get("limit"),
            "remaining": core.get("remaining"),
            "reset": core.get("reset"),
            "authenticated": bool(self.token),
        }

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        data = self._api(f"repos/{owner}/{repo}")
        return data if isinstance(data, dict) else {}

    def get_user(self, username: str) -> dict[str, Any]:
        data = self._api(f"users/{username}")
        return data if isinstance(data, dict) else {}

    def list_user_repos(self, username: str, *, per_page: int = 30) -> list[dict[str, Any]]:
        data = self._api(
            f"users/{username}/repos",
            params={"sort": "updated", "per_page": per_page, "type": "owner"},
        )
        return data if isinstance(data, list) else []

    def search_repos(
        self,
        query: str,
        *,
        per_page: int = 10,
        sort: str = "stars",
    ) -> list[dict[str, Any]]:
        data = self._api(
            "search/repositories",
            params={"q": query, "per_page": per_page, "sort": sort},
        )
        return data.get("items", []) if isinstance(data, dict) else []

    def search_issues(
        self,
        query: str,
        *,
        per_page: int = 20,
        sort: str = "updated",
    ) -> list[dict[str, Any]]:
        data = self._api(
            "search/issues",
            params={"q": query, "per_page": per_page, "sort": sort, "order": "desc"},
        )
        return data.get("items", []) if isinstance(data, dict) else []

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        data = self._api(f"repos/{owner}/{repo}/issues/{number}")
        return data if isinstance(data, dict) else {}

    def get_issue_timeline(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        url = (
            f"{self.settings.github_api_url.rstrip('/')}"
            f"/repos/{owner}/{repo}/issues/{number}/timeline"
        )
        headers = self._headers()
        headers["Accept"] = "application/vnd.github+json"
        try:
            data = self.http.get_json(url, headers=headers, use_cache=False)
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def list_pulls(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "closed",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        data = self._api(
            f"repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page, "sort": "updated", "direction": "desc"},
        )
        return data if isinstance(data, list) else []

    def contents_exists(self, owner: str, repo: str, path: str) -> bool:
        try:
            self._api(f"repos/{owner}/{repo}/contents/{quote(path)}")
            return True
        except HttpError as exc:
            if exc.status_code == 404:
                return False
            return False

    def get_raw_file(self, owner: str, repo: str, path: str) -> str | None:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
        try:
            return self.http.get_text(url, headers=self._headers())
        except HttpError:
            return None

    def repo_health(self, full_name: str) -> RepoHealth:
        if "/" not in full_name:
            raise ValueError("Repository must be in owner/repo form")
        owner, repo = full_name.split("/", 1)
        raw = self.get_repo(owner, repo)
        has_contributing = any(
            self.contents_exists(owner, repo, p)
            for p in (
                "CONTRIBUTING.md",
                ".github/CONTRIBUTING.md",
                "CONTRIBUTING",
                "docs/CONTRIBUTING.md",
            )
        )
        has_coc = any(
            self.contents_exists(owner, repo, p)
            for p in ("CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md")
        )
        has_ci = any(
            self.contents_exists(owner, repo, p)
            for p in (
                ".github/workflows",
                ".travis.yml",
                ".circleci/config.yml",
                "Jenkinsfile",
                ".gitlab-ci.yml",
            )
        )

        pulls = self.list_pulls(owner, repo, state="closed", per_page=40)
        merged = [p for p in pulls if p.get("merged_at")]
        merge_rate = (len(merged) / len(pulls)) if pulls else None
        pr_hours: list[float] = []
        for pull in merged[:20]:
            created = _parse_dt(pull.get("created_at"))
            merged_at = _parse_dt(pull.get("merged_at"))
            if created and merged_at:
                pr_hours.append((merged_at - created).total_seconds() / 3600.0)
        median_pr_hours = sorted(pr_hours)[len(pr_hours) // 2] if pr_hours else None

        labels_present = False
        try:
            sample = self.search_issues(
                f'repo:{full_name} is:issue is:open label:"good first issue"',
                per_page=1,
            )
            labels_present = bool(sample)
        except HttpError:
            labels_present = False

        health = RepoHealth(
            full_name=raw.get("full_name", full_name),
            url=raw.get("html_url", f"https://github.com/{full_name}"),
            description=raw.get("description"),
            language=raw.get("language"),
            stars=int(raw.get("stargazers_count") or 0),
            forks=int(raw.get("forks_count") or 0),
            open_issues=int(raw.get("open_issues_count") or 0),
            archived=bool(raw.get("archived")),
            disabled=bool(raw.get("disabled")),
            pushed_at=_parse_dt(raw.get("pushed_at")),
            license=(raw.get("license") or {}).get("spdx_id"),
            has_contributing=has_contributing,
            has_code_of_conduct=has_coc,
            has_ci=has_ci,
            merge_rate=merge_rate,
            median_pr_hours=median_pr_hours,
            beginner_labels_present=labels_present,
        )
        return score_repo_health(health)

    def find_beginner_issues(
        self,
        *,
        language: str | None = None,
        org: str | None = None,
        repo: str | None = None,
        labels: list[str] | None = None,
        topics: list[str] | None = None,
        max_results: int = 15,
        min_stars: int = 50,
    ) -> list[IssueCandidate]:
        label_terms = labels or ["good first issue", "help wanted"]
        label_query = " ".join(f'label:"{label}"' for label in label_terms[:3])
        parts = ["is:issue", "is:open", "no:assignee", label_query]
        if language:
            parts.append(f"language:{language}")
        if org:
            parts.append(f"org:{org}")
        if repo:
            parts.append(f"repo:{repo}")
        if topics:
            for topic in topics[:3]:
                parts.append(f"topic:{topic}")
        if min_stars > 0 and not repo:
            parts.append(f"stars:>={min_stars}")

        items = self.search_issues(" ".join(parts), per_page=min(max_results * 2, 30))
        candidates: list[IssueCandidate] = []
        for item in items:
            repository_url = item.get("repository_url") or ""
            repo_name = "/".join(repository_url.rstrip("/").split("/")[-2:])
            if not repo_name or "/" not in repo_name:
                # search result may include repository object
                repo_obj = item.get("repository") or {}
                repo_name = repo_obj.get("full_name") or ""
            if not repo_name:
                continue
            labels_list = [
                (lab.get("name") if isinstance(lab, dict) else str(lab))
                for lab in item.get("labels", [])
            ]
            candidate = IssueCandidate(
                repo=repo_name,
                number=int(item["number"]),
                title=item.get("title") or "",
                url=item.get("html_url") or "",
                labels=[x for x in labels_list if x],
                created_at=_parse_dt(item.get("created_at")),
                updated_at=_parse_dt(item.get("updated_at")),
                comments=int(item.get("comments") or 0),
                author=(item.get("user") or {}).get("login"),
                body_excerpt=_excerpt(item.get("body")),
            )
            availability, reason = self.check_issue_availability(repo_name, candidate.number)
            candidate.availability = availability
            candidate.availability_reason = reason
            candidates.append(score_issue(candidate))

        # Prefer available issues, then score
        candidates.sort(
            key=lambda c: (
                0 if c.availability == Availability.AVAILABLE else 1,
                -c.beginner_score,
            )
        )
        return candidates[:max_results]

    def check_issue_availability(self, full_name: str, number: int) -> tuple[Availability, str]:
        owner, repo = full_name.split("/", 1)
        try:
            issue = self.get_issue(owner, repo, number)
        except HttpError as exc:
            return Availability.UNKNOWN, f"Could not fetch issue: {exc}"

        if issue.get("state") != "open":
            return Availability.CLOSED, "Issue is closed"

        if issue.get("assignee") or issue.get("assignees"):
            logins = [a.get("login") for a in (issue.get("assignees") or []) if a.get("login")]
            who = ", ".join(logins) if logins else "someone"
            return Availability.ASSIGNED, f"Assigned to {who}"

        body = (issue.get("body") or "").lower()
        claim_phrases = (
            "i am working on this",
            "i'll take this",
            "i will take this",
            "assigned to me",
            "working on it",
            "claiming this",
        )
        updated = _parse_dt(issue.get("updated_at"))
        stale_days = None
        if updated:
            stale_days = (datetime.now(UTC) - updated.astimezone(UTC)).days

        timeline = self.get_issue_timeline(owner, repo, number)
        linked_open_prs = 0
        for event in timeline:
            event_type = event.get("event")
            if event_type in {"cross-referenced", "connected", "referenced"}:
                source = event.get("source", {}).get("issue") or event.get("source", {})
                # pull_request may be an empty dict - still means it's a PR
                if (
                    isinstance(source, dict)
                    and "pull_request" in source
                    and source.get("state") == "open"
                ):
                    linked_open_prs += 1

        comments = int(issue.get("comments") or 0)
        if linked_open_prs:
            return (
                Availability.LIKELY_TAKEN,
                f"{linked_open_prs} open linked PR(s) detected",
            )

        # Lightweight comment claim heuristic via search of recent comment text is limited;
        # use body + recency signals.
        if any(p in body for p in claim_phrases):
            return Availability.LIKELY_TAKEN, "Issue body suggests someone claimed it"

        if stale_days is not None and stale_days > 180 and comments == 0:
            return Availability.STALE, f"No activity for {stale_days} days"

        if comments >= 8:
            return (
                Availability.LIKELY_TAKEN,
                f"High comment activity ({comments}); verify before starting",
            )

        return Availability.AVAILABLE, "Open, unassigned, no linked open PR detected"

    def contribution_guide(self, full_name: str) -> ContributionGuide:
        owner, repo = full_name.split("/", 1)
        contributing_path = None
        contributing_text = ""
        for path in (
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/CONTRIBUTING.md",
            "CONTRIBUTING.rst",
            "CONTRIBUTING",
        ):
            text = self.get_raw_file(owner, repo, path)
            if text:
                contributing_path = f"https://github.com/{full_name}/blob/HEAD/{path}"
                contributing_text = text
                break

        coc_url = None
        for path in ("CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"):
            if self.contents_exists(owner, repo, path):
                coc_url = f"https://github.com/{full_name}/blob/HEAD/{path}"
                break

        setup_hints: list[str] = []
        channels: list[str] = []
        labels: list[str] = []
        lower = contributing_text.lower()
        for needle, hint in (
            ("npm install", "Node/npm toolchain detected"),
            ("pnpm", "pnpm toolchain detected"),
            ("yarn", "Yarn toolchain detected"),
            ("pip install", "Python/pip toolchain detected"),
            ("poetry", "Poetry toolchain detected"),
            ("cargo ", "Rust/Cargo toolchain detected"),
            ("go mod", "Go modules toolchain detected"),
            ("gradle", "Gradle toolchain detected"),
            ("maven", "Maven toolchain detected"),
            ("docker", "Docker mentioned in contributing docs"),
            ("pre-commit", "pre-commit hooks expected"),
            ("make ", "Makefile targets may exist"),
        ):
            if needle in lower:
                setup_hints.append(hint)

        for needle in ("discord", "slack", "zulip", "irc", "matrix", "mailing list", "discourse"):
            if needle in lower:
                channels.append(needle)

        for label in BEGINNER_LABELS:
            if label in lower:
                labels.append(label)

        if not labels:
            labels = ["good first issue", "help wanted"]

        return ContributionGuide(
            repo=full_name,
            contributing_url=contributing_path,
            contributing_excerpt=_excerpt(contributing_text, 1200),
            code_of_conduct_url=coc_url,
            setup_hints=setup_hints or ["Read README.md and CONTRIBUTING.md before coding"],
            communication_channels=channels,
            beginner_issue_labels=labels,
        )

    def infer_profile_languages(self, username: str) -> dict[str, Any]:
        user = self.get_user(username)
        repos = self.list_user_repos(username, per_page=50)
        counts: dict[str, int] = {}
        for repo in repos:
            lang = repo.get("language")
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return {
            "login": user.get("login", username),
            "name": user.get("name"),
            "bio": user.get("bio"),
            "public_repos": user.get("public_repos"),
            "followers": user.get("followers"),
            "html_url": user.get("html_url"),
            "languages": [{"name": n, "repos": c} for n, c in ranked[:10]],
            "top_language": ranked[0][0] if ranked else None,
        }
