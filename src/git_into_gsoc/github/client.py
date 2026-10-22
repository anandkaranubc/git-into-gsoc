"""GitHub REST API client: repositories, issues, pull requests, and what they say about
how a project treats newcomers."""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.errors import InputError, RateLimitError
from git_into_gsoc.github.announcements import (
    body_search_terms,
    gsoc_posts,
    reported_statements,
    search_terms,
    wiki_post,
)
from git_into_gsoc.github.availability import (
    MAINTAINER_ROLES,
    assess_issue,
    imported_jira_key,
    unverified_assessment,
)
from git_into_gsoc.github.ecosystems import fetch_commit_stats
from git_into_gsoc.github.evidence import summarize_activity
from git_into_gsoc.github.graphql import PullAnalysis, fetch_pull_analysis
from git_into_gsoc.github.related import MIN_SHARED, same_work, title_words
from git_into_gsoc.github.repos import (
    attach_first_replies,
    channels_in,
    closed_outside_unmerged,
    contributing_path,
    detect_toolchain,
    landed_elsewhere,
    mirror_source,
    pick_beginner_label,
    pull_stats,
    readme_contributing_section,
    readme_path,
)
from git_into_gsoc.github.search import build_issue_query, language_group
from git_into_gsoc.http_client import CachedHttpClient, HttpError, NotFoundError
from git_into_gsoc.models import (
    Availability,
    ContributionGuide,
    IssueAssessment,
    IssueCandidate,
    RepoHealth,
)
from git_into_gsoc.scoring.health import MIN_REPLY_SAMPLE, score_repo_health
from git_into_gsoc.scoring.issues import score_issue
from git_into_gsoc.text import clean_untrusted
from git_into_gsoc.validation import parse_repo, validate_login

MAX_COMMENT_PAGES = 3  # at most 200 extra comments per endpoint when the sample is short


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _excerpt(text: str | None, limit: int = 400) -> str:
    """One line of an issue body, with HTML comments removed: GitHub hides them from
    people, so they are the easiest place to leave text only a model would read."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", clean_untrusted(text, limit=limit)).strip()


def _license_name(license_obj: Any) -> str | None:
    """SPDX id when GitHub recognises the license, otherwise its display name."""
    if not isinstance(license_obj, dict):
        return None
    spdx = str(license_obj.get("spdx_id") or "")
    if spdx and spdx != "NOASSERTION":
        return spdx
    name = str(license_obj.get("name") or "")
    return name or None


def explain_not_found(path: str) -> tuple[str, str] | None:
    """A plain message and hint for a 404 on a repository, issue, or user, else None."""
    parts = [p for p in path.split("/") if p]
    if len(parts) == 2 and parts[0] == "users":
        return (
            f"No GitHub user or organization is named {parts[1]}",
            "Check the spelling of the username.",
        )
    if len(parts) < 3 or parts[0] != "repos":
        return None
    repo = f"{parts[1]}/{parts[2]}"
    if len(parts) == 3:
        return (
            f"GitHub has no public repository {repo}",
            f"Check the spelling at https://github.com/{repo}; it may also be private, renamed, "
            "or deleted.",
        )
    if len(parts) == 5 and parts[3] in {"issues", "pulls"} and parts[4].isdigit():
        return (
            f"{repo} has no issue or pull request #{parts[4]}",
            f"Check the number at https://github.com/{repo}/issues; a misspelled repository "
            "name gives the same answer.",
        )
    return None


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
        title=clean_untrusted(item.get("title"), limit=256),
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
    """Every GitHub read the tool makes, through the shared caching HTTP client.

    Two kinds of method. Reads of the thing the person asked for (`get_repo`,
    `get_issue`, `assess`, `repo_health`) raise `HttpError` or `NotFoundError` with a
    message that says what to try. Reads that only feed a score or a list
    (`get_issue_timeline`, `list_assignees`, `recent_comments`, ...) swallow HTTP
    errors and return an empty value or None, so one failed call cannot sink a whole
    report; what the report then says about the gap is the caller's job. A token
    raises the request limit and turns on the GraphQL path in `repo_health`; nothing
    needs one.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        http: CachedHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)
        self.token = self.settings.resolve_github_token()
        # Set when a timeline read hit the request limit, so a list of issues marked
        # "unknown" can say why instead of failing quietly.
        self.rate_limited: RateLimitError | None = None

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
        try:
            return self.http.get_json(
                url, headers=headers, params=params, ttl=ttl, use_cache=use_cache
            )
        except NotFoundError as exc:
            explained = explain_not_found(path)
            if explained is None:
                raise
            raise NotFoundError(
                explained[0], status_code=404, url=exc.url, hint=explained[1]
            ) from exc

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

    def authenticated_login(self) -> str | None:
        """The username the token belongs to, or None without a token."""
        if not self.token:
            return None
        data = self._api("user", use_cache=False)
        login = data.get("login") if isinstance(data, dict) else None
        return validate_login(login) if isinstance(login, str) else None

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

    def merged_pull_requests_elsewhere(self, username: str) -> int | None:
        """How many of this person's pull requests were merged in repositories they do not own.

        One search call; None when the search is unavailable (no token and the
        search limit is used up, for example).
        """
        login = validate_login(username)
        try:
            data = self._api(
                "search/issues",
                params={"q": f"is:pr is:merged author:{login} -user:{login}", "per_page": 1},
            )
        except HttpError:
            return None
        if not isinstance(data, dict) or "total_count" not in data:
            return None
        return int(data.get("total_count") or 0)

    def beginner_issues_opened(
        self, owners: list[str], *, since: str, labels: list[str]
    ) -> int | None:
        """Issues opened since `since` (YYYY-MM-DD) with a beginner label, open or closed.

        One search call; None when the search fails. It shows whether an organization
        marks first tasks on GitHub at all, which a count of open issues on one day
        cannot.
        """
        logins = [validate_login(o, kind="organization") for o in owners if o]
        if not logins:
            return None
        query = build_issue_query(
            base=["is:issue", f"created:>={since}"], labels=labels, orgs=logins
        )
        try:
            # The label OR group needs the advanced engine; the classic one returns 0.
            data = self._api(
                "search/issues", params={"q": query, "per_page": 1, "advanced_search": "true"}
            )
        except HttpError:
            return None
        if not isinstance(data, dict) or "total_count" not in data:
            return None
        return int(data.get("total_count") or 0)

    def gsoc_year_posts(
        self, owners: list[str], year: int, *, bodies: bool = False
    ) -> list[dict[str, Any]]:
        """Issues in these owners' repositories whose title names GSoC and `year` (one search).

        With `bodies`, a second search reads recent issue bodies for a statement that
        names no year (status "reported"), for the monthly evidence.
        """
        logins = [validate_login(o, kind="organization") for o in dict.fromkeys(owners)]
        if not logins:
            return []
        query = build_issue_query(base=search_terms(year), labels=[], orgs=logins)
        posts = gsoc_posts(self.search_issues(query, per_page=30, sort="created"), year=year)
        if bodies:
            since = (datetime.now(UTC) - timedelta(days=150)).date().isoformat()
            query = build_issue_query(base=body_search_terms(since), labels=[], orgs=logins)
            # Most recently updated first; a statement older than the newest 50 GSoC
            # mentions in a busy organization is missed until it is updated again.
            posts += reported_statements(self.search_issues(query, per_page=50), year=year)
        return self._wiki_posts(logins[:2], year) + posts

    def wiki_year_posts(self, owners: list[str], year: int) -> list[dict[str, Any]]:
        """Only the wiki statements of `gsoc_year_posts`. They take no search, so they
        can still be read when GitHub's search limit stops the rest."""
        logins = [validate_login(o, kind="organization") for o in dict.fromkeys(owners)]
        return self._wiki_posts(logins[:2], year)

    def _wiki_posts(self, owners: list[str], year: int) -> list[dict[str, Any]]:
        """Statements about `year` on the wiki home pages of each owner's two biggest repos."""
        found: list[dict[str, Any]] = []
        for owner in owners:
            try:
                repos = self.list_owner_repos(owner)
            except HttpError:
                continue
            with_wiki = sorted(
                (
                    r
                    for r in repos
                    if r.get("has_wiki") and not r.get("archived") and not r.get("fork")
                ),
                key=lambda r: -int(r.get("stargazers_count") or 0),
            )
            for repo in with_wiki[:2]:
                full = str(repo.get("full_name") or "")
                if "/" not in full:
                    continue
                try:
                    text = self.http.get_text(
                        f"https://raw.githubusercontent.com/wiki/{full}/Home.md",
                        ttl=self.settings.archive_ttl_seconds,
                    )
                except HttpError:
                    continue  # no wiki pages, or the wiki is private
                post = wiki_post(text, year=year, repo=full)
                if post:
                    found.append(post)
        return found

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
        except RateLimitError as err:
            self.rate_limited = err
            return None
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
        try:
            return self._raw_file(owner, repo, path)
        except HttpError:
            return None

    def _raw_file(self, owner: str, repo: str, path: str) -> str | None:
        """The file's text, or None when it does not exist. Raises HttpError when GitHub
        does not answer, so `repo_health` can tell the two apart."""
        owner, repo = parse_repo(f"{owner}/{repo}")
        url = f"{self.settings.github_api_url.rstrip('/')}/repos/{owner}/{repo}/contents/" + quote(
            path.lstrip("/"), safe="/"
        )
        headers = self._headers()
        headers["Accept"] = "application/vnd.github.raw+json"
        try:
            return self.http.get_text(url, headers=headers)
        except NotFoundError:
            return None

    def _readme_guide_path(self, owner: str, repo: str, profile: dict[str, Any]) -> str | None:
        """The README's path when it has a section on contributing worth following.

        One cached request, made only for a repository with no CONTRIBUTING file. Raises
        HttpError when GitHub does not send the README: that is unread, not a README
        without a guide.
        """
        if (profile.get("files") or {}).get("contributing"):
            return None
        path = readme_path(profile)
        text = self._raw_file(owner, repo, path) if path else None
        return path if text and readme_contributing_section(text) else None

    def community_profile(self, owner: str, repo: str) -> dict[str, Any]:
        return self._community_profile(owner, repo) or {}

    def workflow_count(self, owner: str, repo: str) -> int:
        return self._workflow_count(owner, repo) or 0

    def list_labels(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return self._list_labels(owner, repo) or []

    def count_open_issues_with_label(self, owner: str, repo: str, label: str) -> tuple[int, int]:
        """Open issues with the label, and how many of them are assigned to someone."""
        return self._count_open_issues_with_label(owner, repo, label) or (0, 0)

    # The same reads for `repo_health`, which must tell "GitHub did not answer" (None)
    # from "the repository has none": a rate limit used to read as no CONTRIBUTING guide,
    # no Code of Conduct, and no CI, and lowered the grade by up to 28 points. A 404 is
    # an answer.
    def _community_profile(self, owner: str, repo: str) -> dict[str, Any] | None:
        try:
            data = self._api(f"repos/{owner}/{repo}/community/profile")
        except NotFoundError:
            return {}
        except HttpError:
            return None
        return data if isinstance(data, dict) else {}

    def _workflow_count(self, owner: str, repo: str) -> int | None:
        try:
            data = self._api(f"repos/{owner}/{repo}/actions/workflows", params={"per_page": 1})
        except NotFoundError:
            return 0
        except HttpError:
            return None
        return int(data.get("total_count") or 0) if isinstance(data, dict) else 0

    def _list_labels(self, owner: str, repo: str) -> list[dict[str, Any]] | None:
        try:
            data = self._api(f"repos/{owner}/{repo}/labels", params={"per_page": 100})
        except NotFoundError:
            return []
        except HttpError:
            return None
        return data if isinstance(data, list) else []

    def _count_open_issues_with_label(
        self, owner: str, repo: str, label: str
    ) -> tuple[int, int] | None:
        try:
            data = self._api(
                f"repos/{owner}/{repo}/issues",
                params={"labels": label, "state": "open", "per_page": 100},
                ttl=900,
            )
        except NotFoundError:
            return 0, 0
        except HttpError:
            return None
        issues = [i for i in data if "pull_request" not in i] if isinstance(data, list) else []
        assigned = sum(1 for i in issues if i.get("assignee") or i.get("assignees"))
        return len(issues), assigned

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
            profile_f = pool.submit(self._community_profile, owner, repo)
            workflows_f = pool.submit(self._workflow_count, owner, repo)
            analysis_f = pool.submit(self.pull_analysis, owner, repo)
            labels_f = pool.submit(self._list_labels, owner, repo)
            commits_f = pool.submit(
                fetch_commit_stats,
                self.http,
                api_url=self.settings.ecosystems_commits_api_url,
                owner=owner,
                repo=repo,
                ttl=self.settings.archive_ttl_seconds,
            )
            profile_or_none, workflows_or_none = profile_f.result(), workflows_f.result()
            analysis, labels_or_none = analysis_f.result(), labels_f.result()
            commits = commits_f.result()
        unread = [
            name
            for name, value in (
                ("community profile", profile_or_none),
                ("workflows", workflows_or_none),
                ("labels", labels_or_none),
            )
            if value is None
        ]
        profile = profile_or_none or {}
        workflows = workflows_or_none or 0
        labels = labels_or_none or []
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
        # Closed outside pull requests whose change a maintainer applied another
        # way: one commit listing covers every candidate.
        source_pulls = analysis.pulls if analysis is not None else pulls
        source_insiders = analysis.insiders if analysis is not None else insiders
        candidates = closed_outside_unmerged(source_pulls, insiders=source_insiders)[:15]
        if candidates:
            oldest = min(str(p.get("created_at") or "") for p in candidates)
            recent = self.list_commits(owner, repo, since=oldest) if oldest else []
            landed = landed_elsewhere(candidates, recent)
            if landed:
                stats = pull_stats(source_pulls, insiders=source_insiders, landed=frozenset(landed))
        files = profile.get("files") or {}
        contributing_source = "file" if files.get("contributing") else None
        if contributing_source is None:
            # It runs after the pull request reads, so it is the read most likely to
            # meet the limit.
            try:
                if self._readme_guide_path(owner, repo, profile):
                    contributing_source = "readme"
            except HttpError:
                unread.append("README")
        label = pick_beginner_label(labels)
        if label and raw.get("has_issues") is False:
            # Issues are turned off (the project tracks work elsewhere), yet GitHub's
            # default labels remain. None are open here, and the issues endpoint answers
            # 410, which retrying never changes.
            counted: tuple[int, int] | None = (0, 0)
        else:
            counted = self._count_open_issues_with_label(owner, repo, label) if label else None
        if label and counted is None:
            unread.append("beginner issues")
        open_beginner, assigned_beginner = counted or (None, None)
        health = RepoHealth(
            full_name=f"{owner}/{repo}",
            url=raw.get("html_url", f"https://github.com/{owner}/{repo}"),
            description=clean_untrusted(raw.get("description"), limit=350) or None,
            language=raw.get("language"),
            stars=int(raw.get("stargazers_count") or 0),
            forks=int(raw.get("forks_count") or 0),
            open_issues=int(raw.get("open_issues_count") or 0),
            archived=bool(raw.get("archived")),
            disabled=bool(raw.get("disabled")),
            pushed_at=_parse_dt(raw.get("pushed_at")),
            license=_license_name(raw.get("license")),
            topics=list(raw.get("topics") or []),
            has_contributing=contributing_source is not None,
            contributing_source=contributing_source,
            has_code_of_conduct=bool(
                files.get("code_of_conduct") or files.get("code_of_conduct_file")
            ),
            has_issue_template=bool(files.get("issue_template")),
            has_pr_template=bool(files.get("pull_request_template")),
            has_ci=workflows > 0,
            unread=unread,
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
            outside_landed_elsewhere=stats.outside_landed_elsewhere,
            pr_source=pr_source,
            committers_last_year=commits.committers_last_year if commits else None,
            newcomer_committers_last_year=(
                commits.newcomer_committers_last_year if commits else None
            ),
            bus_factor=commits.bus_factor if commits else None,
            beginner_label=label,
            open_beginner_issues=open_beginner,
            assigned_beginner_issues=assigned_beginner,
        )
        return score_repo_health(health)

    def find_beginner_issues(
        self,
        *,
        language: str | list[str] | None = None,
        org: str | None = None,
        orgs: list[str] | None = None,
        repo: str | None = None,
        label: str | None = None,
        labels: list[str] | None = None,
        max_results: int = 10,
        per_repo: int = 2,
        org_names: dict[str, str] | None = None,
        created_after: str | None = None,
    ) -> list[IssueCandidate]:
        """Search open beginner issues, then verify the most promising ones.

        `created_after` (YYYY-MM-DD) leaves older issues out of the search itself, so
        a caller that would skip them anyway gets its slots filled with ones it keeps.

        One search call excludes assigned, PR-linked, and archived-repo issues up
        front; timelines are fetched in parallel only for the top candidates.
        """
        owners = [
            validate_login(o, kind="organization") for o in [*(orgs or []), *([org] if org else [])]
        ]
        base = ["is:issue", "is:open", "no:assignee", "-linked:pr", "archived:false"]
        if language:
            base.append(language_group(language))
        if repo:
            owner_name, repo_name = parse_repo(repo)
            base.append(f"repo:{owner_name}/{repo_name}")
        since = (datetime.now(UTC) - timedelta(days=365)).date().isoformat()
        base.append(f"updated:>={since}")
        if created_after:
            base.append(f"created:>={created_after}")

        wanted = max(1, min(max_results, 30))
        labels = list(labels or ([label] if label else ["good first issue", "help wanted"]))
        # One request: the label group is OR-ed, repeated orgs are OR-ed, so GitHub's
        # advanced search cannot AND them away. Results keep the preferred label first.
        query = build_issue_query(base=base, labels=labels, orgs=list(dict.fromkeys(owners)))
        items: list[dict[str, Any]] = self.search_issues(query, per_page=min(100, wanted * 5))
        if labels[0] != "help wanted":
            # Beginner labels before "help wanted", which often marks larger work.
            preferred = {lab.lower() for lab in labels if lab.lower() != "help wanted"}
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

        # Across several owners, a big one (apache has hundreds of repos) must not fill
        # the whole list; a single owner or repo may.
        per_owner = 3 if len(set(owners)) > 1 or not (owners or repo) else wanted + 4
        per_owner_count: dict[str, int] = {}
        shortlist: list[IssueCandidate] = []
        for candidate in prelim:
            owner_key = candidate.repo.split("/")[0].lower()
            # One repository asked for by name may fill the list; otherwise spread it out.
            if not repo and per_repo_count.get(candidate.repo, 0) >= per_repo:
                continue
            if per_owner_count.get(owner_key, 0) >= per_owner:
                continue
            per_repo_count[candidate.repo] = per_repo_count.get(candidate.repo, 0) + 1
            per_owner_count[owner_key] = per_owner_count.get(owner_key, 0) + 1
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
                    self._timeline_with_imports,
                    key[0].split("/")[0],
                    key[0].split("/")[1],
                    key[1],
                    issues_by_key.get(key, {}),
                )
                for key in raw_by_key
            }
            for key, future in futures.items():
                candidate = raw_by_key[key]
                timeline = future.result()
                if timeline is None:
                    assessment = unverified_assessment()
                else:
                    owner_name, repo_name = key[0].split("/", 1)
                    assessment = assess_issue(
                        issues_by_key.get(key, {}),
                        timeline,
                        pull_lookup=self._pull_lookup(),
                    )
                candidate.assessment = assessment
                candidate.availability = assessment.availability
                candidate.availability_reason = assessment.reason
                score_issue(candidate)

        shortlist.sort(key=lambda c: (c.availability != Availability.AVAILABLE, -c.beginner_score))
        return shortlist[:wanted]

    def assess(self, full_name: str, number: int) -> tuple[dict[str, Any], IssueAssessment]:
        owner, repo = parse_repo(full_name)
        try:
            issue = self.get_issue(owner, repo, number)
        except NotFoundError:
            self._explain_missing_issues(owner, repo)
            raise
        if "pull_request" in issue:
            raise InputError(
                f"{owner}/{repo}#{number} is a pull request, not an issue",
                hint="Pass the issue number the PR addresses. To check a pull request, run "
                f"`git-into-gsoc pr-check {owner}/{repo}#{number}`.",
            )
        timeline = self._timeline_with_imports(owner, repo, number, issue)
        if timeline is None:
            return issue, unverified_assessment()
        return issue, assess_issue(issue, timeline, pull_lookup=self._pull_lookup())

    def _explain_missing_issues(self, owner: str, repo: str) -> None:
        """Raise a clearer error when the repository keeps no issues on GitHub at all.

        GNOME/gitg#494 is open on gitlab.gnome.org; on GitHub's read-only mirror it
        is a 404, which read as a misspelled name.
        """
        try:
            raw = self.get_repo(owner, repo)
        except HttpError:
            return
        source = mirror_source(raw)
        if source:
            raise NotFoundError(
                f"{owner}/{repo} on GitHub is a read-only mirror, so its issues are not here",
                hint=f"Open the issue where the project lives: {source}. This tool reads "
                "GitHub only, so check claims and linked merge requests there yourself.",
            )
        if raw.get("has_issues") is False:
            raise NotFoundError(
                f"{owner}/{repo} has GitHub issues turned off",
                hint="Its README or CONTRIBUTING file says where it tracks bugs.",
            )

    def unlinked_pulls(self, owner: str, repo: str, issue: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull requests opened since the issue that look like the same work but never link it.

        One search; an empty list when it fails, so the issue check still answers.
        """
        words = title_words(str(issue.get("title") or ""))
        if len(words) < MIN_SHARED:
            return []
        since = str(issue.get("created_at") or "")[:10]
        query = f"repo:{owner}/{repo} is:pr " + (f"created:>={since} " if since else "")
        try:
            found = self.search_issues(query + " ".join(words[:4]), per_page=10)
        except RateLimitError as err:
            self.rate_limited = err  # the caller says the check was skipped
            return []
        except HttpError:
            return []
        number = int(issue.get("number") or 0)
        return [p for p in found if "pull_request" in p and same_work(number, words, p)]

    def _timeline_with_imports(
        self, owner: str, repo: str, number: int, issue: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """The issue's timeline, plus pull requests that name its old Jira key.

        GitHub does not link those, so they read as cross-references here.
        """
        timeline = self.get_issue_timeline(owner, repo, number)
        key = imported_jira_key(issue.get("body"))
        if timeline is None or not key:
            return timeline
        try:
            found = self.search_issues(f'repo:{owner}/{repo} is:pr "{key}"', per_page=10)
        except HttpError:
            return timeline  # the timeline alone still says something
        named = re.compile(rf"\b{re.escape(key)}\b")
        pulls = [
            item
            for item in found
            if "pull_request" in item
            and named.search(f"{item.get('title') or ''} {item.get('body') or ''}")
        ]
        events = [
            {"event": "cross-referenced", "created_at": p.get("created_at"), "source": {"issue": p}}
            for p in pulls
        ]
        return [*timeline, *events]

    def _pull_lookup(self) -> Callable[[str, int], dict[str, Any] | None]:
        """Fetch a pull request by repository and number; None for an issue or an error."""

        def lookup(full_name: str, number: int) -> dict[str, Any] | None:
            owner, _, repo = full_name.partition("/")
            try:
                return self.get_pull(owner, repo, number)
            except InputError:  # a malformed name in someone's comment
                return None

        return lookup

    def contribution_guide(self, full_name: str) -> ContributionGuide:
        owner, repo = parse_repo(full_name)
        full_name = f"{owner}/{repo}"
        with ThreadPoolExecutor(max_workers=3) as pool:
            profile_f = pool.submit(self._community_profile, owner, repo)
            root_f = pool.submit(self.root_listing, owner, repo)
            labels_f = pool.submit(self.list_labels, owner, repo)
            profile_or_none, root, labels = profile_f.result(), root_f.result(), labels_f.result()
        # As in `repo_health`: a read GitHub did not answer is unread, not "no guide". A
        # rate limit used to make `draft claim` say "no contributing guide found".
        unread = [] if profile_or_none is not None else ["community profile"]
        profile = profile_or_none or {}
        files = profile.get("files") or {}
        path = contributing_path(profile)
        text = ""
        if path:
            try:
                text = self._raw_file(owner, repo, path) or ""
            except HttpError:
                unread.append("contributing guide")
        coc = files.get("code_of_conduct_file") or files.get("code_of_conduct") or {}
        try:
            language = self.get_repo(owner, repo).get("language")
        except HttpError:
            language = None
        toolchain, devcontainer = detect_toolchain(root, language=language)
        readme = None
        if not path:
            try:
                readme = self._readme_guide_path(owner, repo, profile)
            except HttpError:
                unread.append("README")
        hints = list(toolchain)
        if devcontainer:
            hints.insert(0, "Dev container available: open in Codespaces/VS Code for a ready env")
        if unread:
            hints.append(
                f"GitHub did not answer for its {', '.join(unread)}, so the contributing "
                "guide was not read; run it again later"
            )
        elif not hints:
            # Naming a file the repository does not have read as a contradiction next
            # to "No CONTRIBUTING guide detected" (a blind beginner run, 2026-10-22).
            hints.append(
                "Read README.md and CONTRIBUTING.md before coding"
                if path
                else f"Read the contributing section of {readme} before coding"
                if readme
                else "Read README.md before coding"
            )
        beginner = [str(lab.get("name")) for lab in labels if pick_beginner_label([lab])]
        # "Read first" points at the README when its section is the contributing guide.
        guide_file = files.get("contributing") or (files.get("readme") if readme else None) or {}
        return ContributionGuide(
            repo=full_name,
            contributing_url=guide_file.get("html_url"),
            contributing_excerpt=_excerpt(text, 1500),
            contributing_text=text,
            code_of_conduct_url=coc.get("html_url"),
            toolchain=toolchain,
            devcontainer=devcontainer,
            setup_hints=hints,
            communication_channels=channels_in(text),
            beginner_issue_labels=beginner or ["good first issue"],
            unread=unread,
        )

    def list_owner_repos(self, owner: str, *, pages: int = 1) -> list[dict[str, Any]]:
        """An owner's public repositories, most recently pushed first.

        A second page is read when the first is full: at openMF, a hundred bot-pushed
        connector repositories hid the main Android apps on page two.
        """
        owner = validate_login(owner, kind="GitHub org/user")
        params: dict[str, Any] = {"sort": "pushed", "per_page": 100, "type": "public"}
        path = f"orgs/{owner}/repos"
        try:
            data = self._api(path, params=params)
        except NotFoundError:
            path, params = f"users/{owner}/repos", {**params, "type": "owner"}
            data = self._api(path, params=params)
        found = list(data) if isinstance(data, list) else []
        for page in range(2, pages + 1):
            if len(found) < 100 * (page - 1):
                break
            more = self._api(path, params={**params, "page": page})
            if not isinstance(more, list) or not more:
                break
            found.extend(more)
        return found

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
            "name": clean_untrusted(user.get("name"), limit=100) or None,
            "bio": clean_untrusted(user.get("bio"), limit=200) or None,
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

    def pull_commits(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        """Commits on a pull request (first 100), short cache because they change."""
        try:
            data = self._api(
                f"repos/{owner}/{repo}/pulls/{int(number)}/commits",
                params={"per_page": 100},
                ttl=300,
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
            {
                "name": r.get("name"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                # For GitHub Actions the check run's id is the job's id, which has a log.
                "id": r.get("id"),
                "app": ((r.get("app") or {}).get("slug") or "")
                if isinstance(r.get("app"), dict)
                else "",
            }
            for r in runs or []
            if isinstance(r, dict)
        ]

    def job_log_tail(self, owner: str, repo: str, job_id: int) -> str:
        """The end of a GitHub Actions job's log, where the failure is.

        GitHub shows job logs only to signed-in requests, so this needs a token.
        """
        if not self.token:
            raise HttpError(
                "Reading a CI log needs a GitHub token.",
                hint="Run `gh auth login`, or set GITHUB_TOKEN.",
            )
        owner, repo = parse_repo(f"{owner}/{repo}")
        url = (
            f"{self.settings.github_api_url.rstrip('/')}/repos/{owner}/{repo}"
            f"/actions/jobs/{int(job_id)}/logs"
        )
        return self.http.get_tail(url, headers=self._headers())

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
