"""GitHub REST API client focused on contributor intelligence."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.errors import InputError
from git_into_gsoc.github.availability import MAINTAINER_ROLES, assess_issue, unverified_assessment
from git_into_gsoc.github.ecosystems import fetch_commit_stats
from git_into_gsoc.github.evidence import summarize_activity
from git_into_gsoc.github.graphql import PullAnalysis, fetch_pull_analysis
from git_into_gsoc.github.repos import (
    MIN_REPLY_SAMPLE,
    attach_first_replies,
    channels_in,
    contributing_path,
    detect_toolchain,
    pick_beginner_label,
    pull_stats,
)
from git_into_gsoc.github.search import build_issue_query
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

MAX_QUERY_CHARS = 256
MAX_COMMENT_PAGES = 3  # at most 200 extra comments per endpoint when the sample is short


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


def _license_name(license_obj: Any) -> str | None:
    """SPDX id when GitHub recognises the license, otherwise its display name."""
    if not isinstance(license_obj, dict):
        return None
    spdx = str(license_obj.get("spdx_id") or "")
    if spdx and spdx != "NOASSERTION":
        return spdx
    name = str(license_obj.get("name") or "")
    return name or None


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
        filed_by_maintainer=str(item.get("author_association") or "") in MAINTAINER_ROLES,
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
        """Issue search on GitHub's advanced engine; group repeated qualifiers with OR."""
        data = self._api(
            "search/issues",
            params={
                "q": query,
                "per_page": per_page,
                "sort": sort,
                "order": "desc",
                "advanced_search": "true",
            },
        )
        return data.get("items", []) if isinstance(data, dict) else []

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        owner, repo = parse_repo(f"{owner}/{repo}")
        data = self._api(f"repos/{owner}/{repo}/issues/{int(number)}", ttl=300)
        return data if isinstance(data, dict) else {}

    def get_pull(self, owner: str, repo: str, number: int) -> dict[str, Any] | None:
        owner, repo = parse_repo(f"{owner}/{repo}")
        try:
            data = self._api(f"repos/{owner}/{repo}/pulls/{int(number)}", ttl=900)
        except HttpError:
            return None
        return data if isinstance(data, dict) else None

    def get_issue_timeline(self, owner: str, repo: str, number: int) -> list[dict[str, Any]] | None:
        """Timeline events for an issue, or None when GitHub could not be reached."""
        owner, repo = parse_repo(f"{owner}/{repo}")
        try:
            data = self._api(
                f"repos/{owner}/{repo}/issues/{int(number)}/timeline",
                params={"per_page": 100},
                ttl=300,
            )
        except HttpError:
            return None
        return data if isinstance(data, list) else []

    def list_pulls(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "closed",
        per_page: int = 30,
        sort: str = "updated",
    ) -> list[dict[str, Any]]:
        data = self._api(
            f"repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page, "sort": sort, "direction": "desc"},
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

    def community_profile(self, owner: str, repo: str) -> dict[str, Any]:
        try:
            data = self._api(f"repos/{owner}/{repo}/community/profile")
        except HttpError:
            return {}
        return data if isinstance(data, dict) else {}

    def workflow_count(self, owner: str, repo: str) -> int:
        try:
            data = self._api(f"repos/{owner}/{repo}/actions/workflows", params={"per_page": 1})
        except HttpError:
            return 0
        return int(data.get("total_count") or 0) if isinstance(data, dict) else 0

    def list_labels(self, owner: str, repo: str) -> list[dict[str, Any]]:
        try:
            data = self._api(f"repos/{owner}/{repo}/labels", params={"per_page": 100})
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def count_open_issues_with_label(self, owner: str, repo: str, label: str) -> int:
        try:
            data = self._api(
                f"repos/{owner}/{repo}/issues",
                params={"labels": label, "state": "open", "per_page": 100},
                ttl=900,
            )
        except HttpError:
            return 0
        return sum(1 for i in data if "pull_request" not in i) if isinstance(data, list) else 0

    def root_listing(self, owner: str, repo: str) -> list[dict[str, Any]]:
        try:
            data = self._api(f"repos/{owner}/{repo}/contents/")
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def list_assignees(self, owner: str, repo: str) -> frozenset[str] | None:
        """Logins that can be assigned issues: the public proxy for write access (one call)."""
        try:
            data = self._api(
                f"repos/{owner}/{repo}/assignees",
                params={"per_page": 100},
                ttl=self.settings.archive_ttl_seconds,
            )
        except HttpError:
            return None
        if not isinstance(data, list):
            return None
        return frozenset(
            str(u.get("login")) for u in data if isinstance(u, dict) and u.get("login")
        )

    def recent_comments(self, owner: str, repo: str, *, page: int = 1) -> list[dict[str, Any]]:
        """One page (100) of issue comments plus one of review comments, newest first."""
        out: list[dict[str, Any]] = []
        for path in ("issues/comments", "pulls/comments"):
            try:
                data = self._api(
                    f"repos/{owner}/{repo}/{path}",
                    params={"sort": "created", "direction": "desc", "per_page": 100, "page": page},
                )
            except HttpError:
                continue
            if isinstance(data, list):
                out.extend(c for c in data if isinstance(c, dict))
        return out

    def pull_analysis(self, owner: str, repo: str) -> PullAnalysis | None:
        """GraphQL PR analysis (insiders, first human reply); None without a token."""
        if not self.token:
            return None
        return fetch_pull_analysis(
            self.http,
            api_url=self.settings.github_api_url,
            token=self.token,
            owner=owner,
            repo=repo,
            ttl=self.settings.cache_ttl_seconds,
        )

    def repo_health(self, full_name: str) -> RepoHealth:
        """~6 core API calls: metadata, community profile, workflows, PRs, labels, issues.

        With a token, one GraphQL query replaces the PR listing and adds the
        insider set and time to first human reply (cost: about 4 points).
        """
        owner, repo = parse_repo(full_name)
        raw = self.get_repo(owner, repo)
        owner, repo = (raw.get("full_name") or f"{owner}/{repo}").split("/", 1)
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            profile_f = pool.submit(self.community_profile, owner, repo)
            workflows_f = pool.submit(self.workflow_count, owner, repo)
            analysis_f = pool.submit(self.pull_analysis, owner, repo)
            labels_f = pool.submit(self.list_labels, owner, repo)
            commits_f = pool.submit(
                fetch_commit_stats,
                self.http,
                api_url=self.settings.ecosystems_commits_api_url,
                owner=owner,
                repo=repo,
                ttl=self.settings.archive_ttl_seconds,
            )
            profile, workflows = profile_f.result(), workflows_f.result()
            analysis, labels = analysis_f.result(), labels_f.result()
            commits = commits_f.result()
        if analysis is not None:
            stats = pull_stats(analysis.pulls, insiders=analysis.insiders)
            pr_source = "graphql"
        else:
            # Most recently created, like the GraphQL path; sorting by update time
            # pulls in old PRs that were merely closed or relabelled recently. The
            # assignees endpoint gives the same insider set without a token.
            with ThreadPoolExecutor(max_workers=3) as pool:
                pulls_f = pool.submit(
                    self.list_pulls, owner, repo, state="closed", per_page=60, sort="created"
                )
                insiders_f = pool.submit(self.list_assignees, owner, repo)
                comments_f = pool.submit(self.recent_comments, owner, repo)
                pulls, insiders = pulls_f.result(), insiders_f.result()
                comments = comments_f.result()
            pulls, _ = attach_first_replies(pulls, comments)
            stats = pull_stats(pulls, insiders=insiders)
            # Busy repositories burn through 100 comments in a day or two; widen the
            # window (two more pages at most) until the reply figure rests on enough PRs.
            page = 1
            while (
                stats.first_response_sampled < MIN_REPLY_SAMPLE
                and page < MAX_COMMENT_PAGES
                and len(comments) >= 100 * page
            ):
                page += 1
                more = self.recent_comments(owner, repo, page=page)
                if not more:
                    break
                comments.extend(more)
                pulls, _ = attach_first_replies(pulls, comments)
                stats = pull_stats(pulls, insiders=insiders)
            pr_source = "rest"
        files = profile.get("files") or {}
        label = pick_beginner_label(labels)
        open_beginner = self.count_open_issues_with_label(owner, repo, label) if label else None
        health = RepoHealth(
            full_name=f"{owner}/{repo}",
            url=raw.get("html_url", f"https://github.com/{owner}/{repo}"),
            description=raw.get("description"),
            language=raw.get("language"),
            stars=int(raw.get("stargazers_count") or 0),
            forks=int(raw.get("forks_count") or 0),
            open_issues=int(raw.get("open_issues_count") or 0),
            archived=bool(raw.get("archived")),
            disabled=bool(raw.get("disabled")),
            pushed_at=_parse_dt(raw.get("pushed_at")),
            license=_license_name(raw.get("license")),
            topics=list(raw.get("topics") or []),
            has_contributing=bool(files.get("contributing")),
            has_code_of_conduct=bool(
                files.get("code_of_conduct") or files.get("code_of_conduct_file")
            ),
            has_issue_template=bool(files.get("issue_template")),
            has_pr_template=bool(files.get("pull_request_template")),
            has_ci=workflows > 0,
            prs_sampled=stats.sampled,
            merge_rate=stats.merge_rate,
            median_pr_hours=stats.median_hours,
            outsider_prs_sampled=stats.outsider_sampled,
            outsider_merge_rate=stats.outsider_merge_rate,
            outside_authors_merged=stats.outside_authors_merged,
            median_first_response_hours=stats.median_first_response_hours,
            first_response_sampled=stats.first_response_sampled,
            median_outsider_pr_size=stats.median_outsider_size,
            insiders_known=stats.insiders_known,
            pr_source=pr_source,
            committers_last_year=commits.committers_last_year if commits else None,
            newcomer_committers_last_year=(
                commits.newcomer_committers_last_year if commits else None
            ),
            bus_factor=commits.bus_factor if commits else None,
            beginner_label=label,
            open_beginner_issues=open_beginner,
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
        labels: list[str] | None = None,
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

        wanted = max(1, min(max_results, 30))
        labels = list(labels or ([label] if label else ["good first issue", "help wanted"]))
        # One request: the label group is OR-ed, repeated orgs are OR-ed, so GitHub's
        # advanced search cannot AND them away. Results keep the preferred label first.
        query = build_issue_query(base=base, labels=labels, orgs=list(dict.fromkeys(owners)))
        items: list[dict[str, Any]] = self.search_issues(query, per_page=min(100, wanted * 5))
        if labels[0] != "help wanted":
            preferred = {labels[0].lower()}
            items.sort(
                key=lambda i: (
                    not any(
                        str((lab or {}).get("name", lab)).lower() in preferred
                        for lab in i.get("labels") or []
                    )
                )
            )

        seen: set[int] = set()
        prelim: list[IssueCandidate] = []
        per_repo_count: dict[str, int] = {}
        for item in items:
            if item.get("id") in seen or "pull_request" in item:
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
                timeline = future.result()
                if timeline is None:
                    assessment = unverified_assessment()
                else:
                    assessment = assess_issue(issues_by_key.get(key, {}), timeline)
                candidate.assessment = assessment
                candidate.availability = assessment.availability
                candidate.availability_reason = assessment.reason
                score_issue(candidate)

        shortlist.sort(key=lambda c: (c.availability != Availability.AVAILABLE, -c.beginner_score))
        return shortlist[:wanted]

    def assess(self, full_name: str, number: int) -> tuple[dict[str, Any], IssueAssessment]:
        owner, repo = parse_repo(full_name)
        issue = self.get_issue(owner, repo, number)
        if "pull_request" in issue:
            raise InputError(
                f"{owner}/{repo}#{number} is a pull request, not an issue",
                hint="Pass the issue number the PR addresses.",
            )
        timeline = self.get_issue_timeline(owner, repo, number)
        if timeline is None:
            return issue, unverified_assessment()
        return issue, assess_issue(issue, timeline)

    def contribution_guide(self, full_name: str) -> ContributionGuide:
        owner, repo = parse_repo(full_name)
        full_name = f"{owner}/{repo}"
        with ThreadPoolExecutor(max_workers=3) as pool:
            profile_f = pool.submit(self.community_profile, owner, repo)
            root_f = pool.submit(self.root_listing, owner, repo)
            labels_f = pool.submit(self.list_labels, owner, repo)
            profile, root, labels = profile_f.result(), root_f.result(), labels_f.result()
        files = profile.get("files") or {}
        path = contributing_path(profile)
        text = (self.get_raw_file(owner, repo, path) if path else None) or ""
        coc = files.get("code_of_conduct_file") or files.get("code_of_conduct") or {}
        toolchain, devcontainer = detect_toolchain(root)
        hints = list(toolchain)
        if devcontainer:
            hints.insert(0, "Dev container available: open in Codespaces/VS Code for a ready env")
        if not hints:
            hints.append("Read README.md and CONTRIBUTING.md before coding")
        beginner = [str(lab.get("name")) for lab in labels if pick_beginner_label([lab])]
        return ContributionGuide(
            repo=full_name,
            contributing_url=(files.get("contributing") or {}).get("html_url"),
            contributing_excerpt=_excerpt(text, 1500),
            code_of_conduct_url=coc.get("html_url"),
            toolchain=toolchain,
            devcontainer=devcontainer,
            setup_hints=hints,
            communication_channels=channels_in(text),
            beginner_issue_labels=beginner or ["good first issue"],
        )

    def list_owner_repos(self, owner: str) -> list[dict[str, Any]]:
        owner = validate_login(owner, kind="GitHub org/user")
        params = {"sort": "pushed", "per_page": 100, "type": "public"}
        try:
            data = self._api(f"orgs/{owner}/repos", params=params)
        except NotFoundError:
            data = self._api(f"users/{owner}/repos", params={**params, "type": "owner"})
        return data if isinstance(data, list) else []

    def beginner_issue_counts(self, owner: str) -> dict[str, int]:
        """Open, unassigned beginner issues per repo for one GitHub owner (1 search call)."""
        owner = validate_login(owner, kind="GitHub org/user")
        query = f'org:{owner} is:issue is:open no:assignee archived:false label:"good first issue"'
        try:
            items = self.search_issues(query, per_page=100)
        except NotFoundError:
            items = self.search_issues(query.replace("org:", "user:", 1), per_page=100)
        counts: dict[str, int] = {}
        for item in items:
            repo = _repo_from_item(item).lower()
            counts[repo] = counts.get(repo, 0) + 1
        return counts

    def user_activity(
        self,
        username: str,
        *,
        owners: list[str] | None = None,
        repo: str | None = None,
        per_query: int = 50,
    ) -> dict[str, Any]:
        """A contributor's PRs, issues, threads joined, and reviews in a scope (4 searches)."""
        login = validate_login(username)
        scope: list[str] = []
        if repo:
            owner_name, repo_name = parse_repo(repo)
            scope.append(f"repo:{owner_name}/{repo_name}")
        for owner in dict.fromkeys(validate_login(o, kind="organization") for o in owners or []):
            scope.append(f"org:{owner}")
        if not scope:
            raise InputError(
                "Contribution evidence needs an org or a repo to search in",
                hint="Pass a GSoC org name, a GitHub org, or owner/repo.",
            )
        base = " ".join(scope)
        queries = {
            "prs": f"is:pr author:{login} {base}",
            "issues": f"is:issue author:{login} {base}",
            "discussions": f"commenter:{login} -author:{login} {base}",
            "reviews": f"is:pr reviewed-by:{login} -author:{login} {base}",
        }
        results: dict[str, list[dict[str, Any]]] = {}
        for key, query in queries.items():
            try:
                results[key] = self.search_issues(query, per_page=per_query, sort="created")
            except HttpError as exc:
                if key in {"discussions", "reviews"}:
                    results[key] = []
                    continue
                raise exc
        return summarize_activity(
            login,
            prs=results["prs"],
            issues=results["issues"],
            discussions=results["discussions"],
            reviews=results["reviews"],
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

    # ------------------------------------------------------ orientation reads

    def git_tree(self, owner: str, repo: str, ref: str) -> dict[str, Any]:
        """Whole file tree in one call (GitHub caps it at 100,000 entries / 7 MB)."""
        owner, repo = parse_repo(f"{owner}/{repo}")
        try:
            data = self._api(
                f"repos/{owner}/{repo}/git/trees/{quote(ref, safe='')}",
                params={"recursive": "1"},
                ttl=86400,
            )
        except HttpError:
            return {}
        return data if isinstance(data, dict) else {}

    def languages(self, owner: str, repo: str) -> dict[str, int]:
        try:
            data = self._api(f"repos/{owner}/{repo}/languages", ttl=86400)
        except HttpError:
            return {}
        return {str(k): int(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def list_commits(
        self, owner: str, repo: str, *, since: str, per_page: int = 100
    ) -> list[dict[str, Any]]:
        try:
            data = self._api(
                f"repos/{owner}/{repo}/commits", params={"since": since, "per_page": per_page}
            )
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def list_pull_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        try:
            data = self._api(
                f"repos/{owner}/{repo}/pulls/{int(number)}/files",
                params={"per_page": 100},
                ttl=604800,
            )
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def check_runs(self, owner: str, repo: str, ref: str) -> list[dict[str, Any]]:
        """Check runs on a commit with their status and conclusion (short cache)."""
        try:
            data = self._api(
                f"repos/{owner}/{repo}/commits/{quote(ref, safe='')}/check-runs",
                params={"per_page": 50},
                ttl=300,
            )
        except HttpError:
            return []
        runs = data.get("check_runs") if isinstance(data, dict) else None
        return [
            {"name": r.get("name"), "status": r.get("status"), "conclusion": r.get("conclusion")}
            for r in runs or []
            if isinstance(r, dict)
        ]

    def branch_rules(self, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        """Active ruleset rules on a branch (readable without a token for public repos).

        Classic branch protection is visible only to admins, so an empty list means
        "no rulesets found", not "no rules".
        """
        try:
            data = self._api(f"repos/{owner}/{repo}/rules/branches/{quote(branch, safe='')}")
        except HttpError:
            return []
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def check_run_names(self, owner: str, repo: str, ref: str) -> list[str]:
        """Names of check runs and status contexts on a commit (CLA/DCO/CI detection)."""
        names: list[str] = []
        try:
            runs = self._api(
                f"repos/{owner}/{repo}/commits/{quote(ref, safe='')}/check-runs",
                params={"per_page": 50},
                ttl=604800,
            )
            if isinstance(runs, dict):
                names.extend(
                    str(r.get("name")) for r in runs.get("check_runs") or [] if r.get("name")
                )
        except HttpError:
            pass
        try:
            status = self._api(
                f"repos/{owner}/{repo}/commits/{quote(ref, safe='')}/status", ttl=604800
            )
            if isinstance(status, dict):
                names.extend(
                    str(s.get("context")) for s in status.get("statuses") or [] if s.get("context")
                )
        except HttpError:
            pass
        return list(dict.fromkeys(names))

    def search_code(self, query: str, *, per_page: int = 10) -> list[dict[str, Any]]:
        """Code search (authenticated only, 10 requests/minute); returns path hits."""
        data = self._api("search/code", params={"q": query, "per_page": per_page}, ttl=3600)
        return data.get("items", []) if isinstance(data, dict) else []
