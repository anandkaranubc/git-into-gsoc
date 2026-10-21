"""GitHub REST API client focused on contributor intelligence."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.errors import InputError
from git_into_gsoc.github.availability import assess_issue
from git_into_gsoc.http_client import CachedHttpClient, HttpError, NotFoundError
from git_into_gsoc.models import (
    Availability,
    ContributionGuide,
    IssueAssessment,
    IssueCandidate,
    RepoHealth,
)
from git_into_gsoc.scoring.health import score_repo_health
from git_into_gsoc.scoring.issues import score_issue
from git_into_gsoc.validation import parse_repo, search_term, validate_login

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

MAX_QUERY_CHARS = 256

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


def _repo_from_item(item: dict[str, Any]) -> str:
    url = str(item.get("repository_url") or "")
    parts = url.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else ""


def _candidate_from_search(item: dict[str, Any]) -> IssueCandidate | None:
    repo_name = _repo_from_item(item)
    if "/" not in repo_name or not item.get("number"):
        return None
    labels = [
        lab.get("name") if isinstance(lab, dict) else str(lab) for lab in item.get("labels") or []
    ]
    return IssueCandidate(
        repo=repo_name,
        number=int(item["number"]),
        title=item.get("title") or "",
        url=item.get("html_url") or "",
        labels=[x for x in labels if x],
        created_at=_parse_dt(item.get("created_at")),
        updated_at=_parse_dt(item.get("updated_at")),
        comments=int(item.get("comments") or 0),
        author=(item.get("user") or {}).get("login"),
        body_excerpt=_excerpt(item.get("body")),
    )


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

    def _api(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: int | None = None,
        use_cache: bool = True,
        accept: str | None = None,
    ) -> Any:
        url = f"{self.settings.github_api_url.rstrip('/')}/{quote(path.lstrip('/'), safe='/')}"
        headers = self._headers()
        if accept:
            headers["Accept"] = accept
        return self.http.get_json(url, headers=headers, params=params, ttl=ttl, use_cache=use_cache)

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
        owner, repo = parse_repo(f"{owner}/{repo}")
        data = self._api(f"repos/{owner}/{repo}")
        return data if isinstance(data, dict) else {}

    def get_user(self, username: str) -> dict[str, Any]:
        data = self._api(f"users/{validate_login(username)}")
        return data if isinstance(data, dict) else {}

    def list_user_repos(self, username: str, *, per_page: int = 30) -> list[dict[str, Any]]:
        data = self._api(
            f"users/{validate_login(username)}/repos",
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
        owner, repo = parse_repo(f"{owner}/{repo}")
        data = self._api(f"repos/{owner}/{repo}/issues/{int(number)}", ttl=300)
        return data if isinstance(data, dict) else {}

    def get_issue_timeline(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        owner, repo = parse_repo(f"{owner}/{repo}")
        try:
            data = self._api(
                f"repos/{owner}/{repo}/issues/{int(number)}/timeline",
                params={"per_page": 100},
                ttl=300,
            )
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
        owner, repo = parse_repo(f"{owner}/{repo}")
        try:
            self._api(f"repos/{owner}/{repo}/contents/{path}")
            return True
        except NotFoundError:
            return False
        except HttpError:
            return False

    def get_raw_file(self, owner: str, repo: str, path: str) -> str | None:
        owner, repo = parse_repo(f"{owner}/{repo}")
        url = f"{self.settings.github_api_url.rstrip('/')}/repos/{owner}/{repo}/contents/" + quote(
            path.lstrip("/"), safe="/"
        )
        headers = self._headers()
        headers["Accept"] = "application/vnd.github.raw+json"
        try:
            return self.http.get_text(url, headers=headers)
        except HttpError:
            return None

    def repo_health(self, full_name: str) -> RepoHealth:
        owner, repo = parse_repo(full_name)
        full_name = f"{owner}/{repo}"
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
        orgs: list[str] | None = None,
        repo: str | None = None,
        label: str | None = None,
        max_results: int = 10,
        per_repo: int = 2,
        org_names: dict[str, str] | None = None,
    ) -> list[IssueCandidate]:
        """Search open beginner issues, then verify the most promising ones.

        One search call excludes assigned, PR-linked, and archived-repo issues up
        front; timelines are fetched in parallel only for the top candidates.
        """
        owners = [
            validate_login(o, kind="organization") for o in [*(orgs or []), *([org] if org else [])]
        ]
        base = ["is:issue", "is:open", "no:assignee", "-linked:pr", "archived:false"]
        if language:
            base.append(f"language:{search_term(language)}")
        if repo:
            owner_name, repo_name = parse_repo(repo)
            base.append(f"repo:{owner_name}/{repo_name}")
        since = (datetime.now(UTC) - timedelta(days=365)).date().isoformat()
        base.append(f"updated:>={since}")
        for owner in dict.fromkeys(owners):
            if len(" ".join(base)) + len(owner) + 5 > MAX_QUERY_CHARS - 30:
                break
            base.append(f"org:{owner}")

        wanted = max(1, min(max_results, 30))
        items: list[dict[str, Any]] = []
        for lab in [label] if label else ["good first issue", "help wanted"]:
            query = " ".join([*base, f"label:{search_term(lab)}"])
            items.extend(self.search_issues(query, per_page=min(100, wanted * 5)))
            if len({i.get("id") for i in items}) >= wanted * 3:
                break

        seen: set[int] = set()
        prelim: list[IssueCandidate] = []
        per_repo_count: dict[str, int] = {}
        for item in items:
            if item.get("id") in seen or item.get("pull_request"):
                continue
            seen.add(int(item.get("id") or 0))
            candidate = _candidate_from_search(item)
            if candidate is None:
                continue
            owner_key = candidate.repo.split("/")[0].lower()
            candidate.gsoc_org = (org_names or {}).get(owner_key)
            prelim.append(score_issue(candidate))
        prelim.sort(key=lambda c: -c.beginner_score)

        shortlist: list[IssueCandidate] = []
        for candidate in prelim:
            if per_repo_count.get(candidate.repo, 0) >= per_repo:
                continue
            per_repo_count[candidate.repo] = per_repo_count.get(candidate.repo, 0) + 1
            shortlist.append(candidate)
            if len(shortlist) >= wanted + 4:
                break

        raw_by_key = {(c.repo, c.number): c for c in shortlist}
        issues_by_key = {
            (_repo_from_item(i), int(i["number"])): i for i in items if i.get("number")
        }
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            futures = {
                key: pool.submit(
                    self.get_issue_timeline, key[0].split("/")[0], key[0].split("/")[1], key[1]
                )
                for key in raw_by_key
            }
            for key, future in futures.items():
                candidate = raw_by_key[key]
                assessment = assess_issue(issues_by_key.get(key, {}), future.result())
                candidate.assessment = assessment
                candidate.availability = assessment.availability
                candidate.availability_reason = assessment.reason
                score_issue(candidate)

        shortlist.sort(key=lambda c: (c.availability != Availability.AVAILABLE, -c.beginner_score))
        return shortlist[:wanted]

    def assess(self, full_name: str, number: int) -> tuple[dict[str, Any], IssueAssessment]:
        owner, repo = parse_repo(full_name)
        issue = self.get_issue(owner, repo, number)
        if issue.get("pull_request"):
            raise InputError(
                f"{owner}/{repo}#{number} is a pull request, not an issue",
                hint="Pass the issue number the PR addresses.",
            )
        timeline = self.get_issue_timeline(owner, repo, number)
        return issue, assess_issue(issue, timeline)

    def check_issue_availability(self, full_name: str, number: int) -> tuple[Availability, str]:
        try:
            _, assessment = self.assess(full_name, number)
        except NotFoundError:
            return Availability.UNKNOWN, "Issue not found"
        except HttpError as exc:
            return Availability.UNKNOWN, f"Could not fetch issue: {exc}"
        return assessment.availability, assessment.reason

    def contribution_guide(self, full_name: str) -> ContributionGuide:
        owner, repo = parse_repo(full_name)
        full_name = f"{owner}/{repo}"
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
