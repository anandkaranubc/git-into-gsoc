"""Check an issue on a GitLab host (gitlab.com, gitlab.gnome.org, invent.kde.org).

About one in six GSoC organizations keep their code on GitLab. Its public API
answers without a token for the issue itself (state, assignees, labels) and for
the merge requests that reference it, but not for comments, so a claim written
in a comment cannot be seen. The status says so instead of guessing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse

from git_into_gsoc.dates import parse_iso
from git_into_gsoc.errors import GigError, NotFoundError
from git_into_gsoc.github.availability import (
    RESERVED_LABELS,
    STALE_DAYS,
    assess_issue,
    is_not_open_label,
)
from git_into_gsoc.github.orientation import (
    active_committers,
    ci_test_commands,
    code_map,
    codetour_from_orientation,
    conventions,
    days_since,
    entry_points,
    find_paths,
    policy_quotes,
    reading_plan,
    since_iso,
    work_branch,
)
from git_into_gsoc.github.pointers import (
    closing_pull_request,
    code_first,
    days_between,
    extract_mentions,
    fix_norm,
    rank_similar,
    resolve_paths,
    title_file_matches,
)
from git_into_gsoc.github.repos import (
    channels_in,
    detect_toolchain,
    is_bot,
    mentioned_repos,
    pull_stats,
    readme_contributing_section,
    repo_lead_score,
)
from git_into_gsoc.http_client import CachedHttpClient
from git_into_gsoc.labels import is_beginner_label
from git_into_gsoc.matching.profile import ContributorProfile
from git_into_gsoc.models import (
    Availability,
    ContributionGuide,
    IssueAssessment,
    IssueCandidate,
    LinkedPullRequest,
    RepoHealth,
    RepoLead,
)
from git_into_gsoc.scoring.health import score_repo_health
from git_into_gsoc.scoring.issues import score_issue
from git_into_gsoc.text import clean_untrusted

_SHORT_REF = re.compile(r"^([A-Za-z0-9.-]+\.[A-Za-z]{2,})/((?:[\w.-]+/)+[\w.-]+)#(\d+)$")
_ISSUE_URL = re.compile(
    r"^https://([A-Za-z0-9.-]+\.[A-Za-z]{2,})/((?:[\w.-]+/)+?[\w.-]+)/-/(?:issues|work_items)/(\d+)"
)


def parse_gitlab_issue(url: str) -> tuple[str, str, int] | None:
    """(host, project path, issue number) for a GitLab issue link, else None."""
    raw = (url or "").strip()
    if "://" not in raw and "/-/" in raw:
        raw = "https://" + raw  # copied from the address bar without "https://"
    short = _SHORT_REF.match(raw)
    if short:
        # "gitlab.gnome.org/GNOME/gitg#494", as the issues table and footer print it.
        raw = f"https://{short.group(1)}/{short.group(2)}/-/issues/{short.group(3)}"
    match = _ISSUE_URL.match(raw)
    if not match or match.group(1).lower().removeprefix("www.") == "github.com":
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _days(value: str | None, now: datetime) -> int | None:
    when = parse_iso(value)
    return None if when is None else (now - when).days


def _status(
    issue: dict[str, Any], merge_requests: list[dict[str, Any]], *, project: str, now: datetime
) -> tuple[Availability, str, list[dict[str, Any]], list[str]]:
    """Availability, reason, the merge requests in this project, and caveats."""
    caveats: list[str] = []
    own = [mr for mr in merge_requests if f"/{project}/-/merge_requests/" in str(mr.get("web_url"))]
    linked: list[dict[str, Any]] = [
        {
            "number": mr.get("iid"),
            "url": mr.get("web_url"),
            "state": "open" if mr.get("state") == "opened" else str(mr.get("state") or "unknown"),
            "author": (mr.get("author") or {}).get("username"),
            "draft": bool(mr.get("draft")),
            "idle_days": _days(mr.get("updated_at"), now),
            "via_comment": False,
        }
        for mr in own
    ]
    if any(mr["state"] == "merged" for mr in linked):
        caveats.append("A merged merge request references this issue; it may already be fixed")
    closed = [mr for mr in linked if mr["state"] == "closed"]
    if closed and not any(mr["state"] in {"open", "merged"} for mr in linked):
        refs = ", ".join(f"!{mr['number']}" for mr in closed[:3])
        caveats.append(
            f"{refs} tried this and was closed without merging; read its review comments first"
        )
    labels = [str(label) for label in issue.get("labels") or []]
    lowered = {label.lower() for label in labels}
    assignees = [str(a.get("username")) for a in issue.get("assignees") or [] if a.get("username")]
    notes = int(issue.get("user_notes_count") or 0)
    idle = _days(issue.get("updated_at"), now)

    if issue.get("state") != "opened":
        return Availability.CLOSED, "Issue is closed", linked, caveats
    if assignees:
        names = ", ".join(f"@{a}" for a in assignees)
        return Availability.ASSIGNED, f"Assigned to {names}", linked, caveats
    open_mrs = [mr for mr in linked if mr["state"] == "open"]
    if open_mrs:
        mr = open_mrs[0]
        reason = f"Open merge request !{mr['number']} by @{mr['author']} references it"
        if mr["idle_days"] is not None and mr["idle_days"] >= 90:
            reason += f"; it has been idle for {mr['idle_days']} days"
        return Availability.LIKELY_TAKEN, reason, linked, caveats
    held = sorted(label for label in labels if is_not_open_label(label))
    if held:
        return Availability.NOT_OPEN, f"Labelled '{held[0]}'; pick another issue", linked, caveats
    reserved = sorted(lowered & RESERVED_LABELS)
    if reserved:
        return Availability.CLAIMED, f"Label '{reserved[0]}' marks it as taken", linked, caveats
    if idle is not None and idle > STALE_DAYS:
        return Availability.STALE, f"No activity for {idle} days", linked, caveats
    if notes:
        return (
            Availability.UNKNOWN,
            f"Open, unassigned, and no open merge request, but its {notes} comment(s) can only "
            "be read when signed in: check them for claims before you start",
            linked,
            caveats,
        )
    return Availability.AVAILABLE, "Open, unassigned, no merge request or comments", linked, caveats


def _same_host(host: str, token_host: str | None) -> bool:
    wanted = (token_host or "").lower().removeprefix("https://").removeprefix("http://")
    return bool(wanted) and host.lower() == wanted.strip("/").removeprefix("www.")


def _comment_claims(
    notes: list[dict[str, Any]], issue: dict[str, Any]
) -> tuple[Availability, str, list[dict[str, Any]], list[str]]:
    """Claims in GitLab comments, judged by the same rules as GitHub comments."""
    timeline = [
        {
            "event": "commented",
            "user": {"login": (n.get("author") or {}).get("username"), "type": "User"},
            "body": str(n.get("body") or ""),
            "created_at": n.get("created_at"),
            "author_association": "NONE",
        }
        for n in notes
        if isinstance(n, dict) and not n.get("system")
    ]
    found = assess_issue(
        {"state": "open", "assignees": [], "updated_at": issue.get("updated_at")}, timeline
    )
    claims = [claim.model_dump(mode="json") for claim in found.claims]
    return found.availability, found.reason, claims, list(found.caveats)


def gitlab_issue_status(
    http: CachedHttpClient, url: str, *, token: str | None = None, token_host: str | None = None
) -> dict[str, Any]:
    """The same shape as the GitHub issue status, read from a GitLab host's public API.

    With a token for this host (GITLAB_TOKEN and GITLAB_HOST), the comments are read
    too, and a claim in them counts as it does on GitHub.
    """
    parsed = parse_gitlab_issue(url)
    if parsed is None:
        raise NotFoundError(f"Not a GitLab issue link: {url}")
    host, project, number = parsed
    api = f"https://{host}/api/v4/projects/{quote(project, safe='')}/issues/{number}"
    unreadable = NotFoundError(
        f"Could not read {host}/{project} issue {number} through GitLab's public API",
        hint="It may be private, deleted, or on a host that is not GitLab. Open the link "
        "and check for an assignee, a merge request, and recent claims yourself.",
    )
    try:
        issue = http.get_json(api, ttl=300)
    except GigError as exc:
        raise unreadable from exc
    if not isinstance(issue, dict):  # a host that is not GitLab can answer with a list
        raise unreadable
    try:
        merge_requests = http.get_json(f"{api}/related_merge_requests", ttl=300)
    except GigError:
        merge_requests = []
    now = datetime.now(UTC)
    status, reason, linked, caveats = _status(
        issue,
        merge_requests if isinstance(merge_requests, list) else [],
        project=project,
        now=now,
    )
    notes = int(issue.get("user_notes_count") or 0)
    claims: list[dict[str, Any]] = []
    read_comments = False
    if notes and token and _same_host(host, token_host):
        try:
            # Not GitLab's PRIVATE-TOKEN header: httpx drops only Authorization when a
            # redirect leaves the host, so a redirect sent PRIVATE-TOKEN to another site
            # (an audit, 2026-10-29).
            found = http.get_json(
                f"{api}/notes",
                headers={"Authorization": f"Bearer {token}"},
                params={"per_page": 100, "sort": "asc"},
                ttl=300,
            )
        except GigError:
            found = None
        if isinstance(found, list):
            read_comments = True
            comment_status, comment_reason, claims, comment_caveats = _comment_claims(found, issue)
            caveats += comment_caveats
            if status in {Availability.AVAILABLE, Availability.UNKNOWN}:
                status, reason = comment_status, comment_reason
    if notes and not read_comments:
        caveats.append(
            f"This tool cannot read the {notes} comment(s) without a {host} sign-in; read the "
            "thread before you claim it, or set GITLAB_TOKEN and GITLAB_HOST so it can"
        )
    return {
        "repo": f"{host}/{project}",
        "number": number,
        "title": clean_untrusted(issue.get("title"), limit=256),
        "url": f"https://{host}/{project}/-/issues/{number}",
        "labels": [str(label) for label in issue.get("labels") or []],
        "comments": notes,
        "availability": status.value,
        "reason": reason,
        "host": host,
        "assessment": {
            "availability": status.value,
            "reason": reason,
            "claims": claims,
            "linked_prs": linked,
            "assignees": [a.get("username") for a in issue.get("assignees") or []],
            "maintainer_engaged": False,
            "last_activity_days": _days(issue.get("updated_at"), now),
            "caveats": caveats,
        },
    }


# The official listing gives GNOME only its host; everything GNOME is under this group.
_DEFAULT_GROUPS = {"gitlab.gnome.org": "GNOME"}

# One request per label, in this order, until the list is full. GitLab's label filter
# is case-sensitive ("4. newcomers" found nothing on gitlab.gnome.org, 2026-11-01), so
# a label projects spell differently is listed both ways.
GITLAB_BEGINNER_LABELS: tuple[str, ...] = (
    "4. Newcomers",
    "Newcomers",
    "good first issue",
    "Good first issue",
    "beginner",
    "Beginner",
    "easy",
    "Easy",
    "help wanted",
    "Help wanted",
)

# GNOME has hundreds of projects; gimp's newcomer issues must not fill the whole list.
_PER_PROJECT = 3


def gitlab_target(source_code: str | None) -> tuple[str, str] | None:
    """(host, group or project path) to search when an organization's code link may be
    a GitLab group or project. None for GitHub and for a bare host with no known group
    (KDE's invent.kde.org: its bugs live on bugs.kde.org)."""
    parsed = urlparse((source_code or "").strip())
    host = parsed.netloc.lower().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or not host or host == "github.com":
        return None
    path = parsed.path.strip("/").removesuffix(".git") or _DEFAULT_GROUPS.get(host, "")
    return (host, path) if path else None


# The shared parser, under the short name the field maps below use.
_dt = parse_iso


def _issues_page(
    http: CachedHttpClient,
    url: str,
    label: str,
    *,
    since: str,
    per_page: int,
    created_after: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "state": "opened",
        "labels": label,
        "assignee_id": "None",
        "scope": "all",
        "updated_after": f"{since}T00:00:00Z",
        "order_by": "created_at" if created_after else "updated_at",
        "per_page": per_page,
    }
    if created_after:
        params["created_after"] = created_after
    found = http.get_json(url, params=params, ttl=300)
    if not isinstance(found, list):  # a host that is not GitLab can answer with anything
        raise NotFoundError(f"{url} did not answer as GitLab does", status_code=404, url=url)
    return [item for item in found if isinstance(item, dict)]


def search_gitlab_issues(
    http: CachedHttpClient,
    host: str,
    path: str,
    *,
    labels: Sequence[str],
    max_results: int,
    org_name: str | None = None,
    created_after: str | None = None,
) -> list[IssueCandidate]:
    """Open, unassigned issues under a GitLab group or project that carry one of
    `labels`, each checked for merge requests, free ones first. With `created_after`
    (an ISO time), only issues opened since then, newest first: `next` wants what is
    new, not what was touched lately.

    Raises NotFoundError when `path` is neither a group nor a project the host's
    public API answers for, and HttpError when the host does not answer as GitLab.
    """
    wanted = max(1, min(max_results, 30))
    base = f"https://{host}/api/v4"
    since = (datetime.now(UTC) - timedelta(days=365)).date().isoformat()
    per_page = min(50, wanted * 3)
    items: dict[tuple[str, int], dict[str, Any]] = {}

    def keep(page: list[dict[str, Any]]) -> None:
        for item in page:
            parsed = parse_gitlab_issue(str(item.get("web_url") or ""))
            if parsed and item.get("state") == "opened":
                items.setdefault((parsed[1], parsed[2]), item)

    listing: str | None = None
    # A one-segment path is a group; GNOME/gimp or qemu-project/qemu is a project.
    for kind in ("groups", "projects"):
        url = f"{base}/{kind}/{quote(path, safe='')}/issues"
        try:
            keep(
                _issues_page(
                    http,
                    url,
                    labels[0],
                    since=since,
                    per_page=per_page,
                    created_after=created_after,
                )
            )
        except NotFoundError:
            continue
        listing = url
        break
    if listing is None:
        raise NotFoundError(
            f"{host}/{path} is not a GitLab group or project this tool can read",
            status_code=404,
            url=f"https://{host}/{path}",
        )
    for label in labels[1:]:
        if len(items) >= wanted + 4:
            break
        try:
            keep(
                _issues_page(
                    http,
                    listing,
                    label,
                    since=since,
                    per_page=per_page,
                    created_after=created_after,
                )
            )
        except GigError:
            continue

    prelim = [
        score_issue(
            IssueCandidate(
                repo=f"{host}/{project}",
                number=number,
                title=clean_untrusted(item.get("title"), limit=256),
                url=f"https://{host}/{project}/-/issues/{number}",
                labels=[str(label) for label in item.get("labels") or []],
                created_at=_dt(item.get("created_at")),
                updated_at=_dt(item.get("updated_at")),
                comments=int(item.get("user_notes_count") or 0),
                author=(item.get("author") or {}).get("username"),
                body_excerpt=clean_untrusted(item.get("description"), limit=280),
                gsoc_org=org_name,
            )
        )
        for (project, number), item in items.items()
    ]
    prelim.sort(key=lambda c: -c.beginner_score)
    per_project: dict[str, int] = {}
    shortlist: list[IssueCandidate] = []
    for candidate in prelim:
        if per_project.get(candidate.repo, 0) >= _PER_PROJECT:
            continue
        per_project[candidate.repo] = per_project.get(candidate.repo, 0) + 1
        shortlist.append(candidate)
        if len(shortlist) >= wanted + 4:
            break

    now = datetime.now(UTC)
    for candidate in shortlist:
        project = candidate.repo.split("/", 1)[1]
        api = f"{base}/projects/{quote(project, safe='')}/issues/{candidate.number}"
        try:
            merge_requests = http.get_json(f"{api}/related_merge_requests", ttl=300)
        except GigError:
            merge_requests = []
        item = items[(project, candidate.number)]
        status, reason, linked, caveats = _status(
            item,
            merge_requests if isinstance(merge_requests, list) else [],
            project=project,
            now=now,
        )
        candidate.assessment = IssueAssessment(
            availability=status,
            reason=reason,
            linked_prs=[LinkedPullRequest(**mr) for mr in linked],
            last_activity_days=_days(item.get("updated_at"), now),
            caveats=caveats,
        )
        candidate.availability, candidate.availability_reason = status, reason
        score_issue(candidate)
    shortlist.sort(key=lambda c: (c.availability != Availability.AVAILABLE, -c.beginner_score))
    return shortlist[:wanted]


def gitlab_repo_leads(
    http: CachedHttpClient,
    host: str,
    path: str,
    *,
    ideas: str,
    language: str | None,
    person: ContributorProfile | None,
    limit: int,
) -> list[RepoLead]:
    """The most recently active projects under a GitLab group, or the one project
    `path` names, scored as GitHub repositories are: ideas-page mentions, activity,
    stars, and language. Beginner-issue counts are not read: they cost one request
    per project and label on GitLab.

    Raises NotFoundError when `path` is neither a group nor a project the host's
    public API answers for.
    """
    base = f"https://{host}/api/v4"
    encoded = quote(path, safe="")
    try:
        listed = http.get_json(
            f"{base}/groups/{encoded}/projects",
            params={
                "include_subgroups": "true",
                "order_by": "last_activity_at",
                "sort": "desc",
                "per_page": 100,
                "archived": "false",
            },
            ttl=3600,
        )
    except NotFoundError:
        listed = [http.get_json(f"{base}/projects/{encoded}", ttl=3600)]
    if not isinstance(listed, list) or not all(isinstance(p, dict) for p in listed):
        raise NotFoundError(
            f"{host}/{path} did not answer as GitLab does",
            status_code=404,
            url=f"https://{host}/{path}",
        )
    raws: list[dict[str, Any]] = [
        {
            "name": project.get("name"),
            "full_name": project.get("path_with_namespace"),
            "html_url": project.get("web_url"),
            "description": project.get("description"),
            "stargazers_count": project.get("star_count"),
            "pushed_at": project.get("last_activity_at"),
            "topics": project.get("topics") or project.get("tag_list") or [],
        }
        for project in listed
        if project.get("web_url")
        and project.get("path_with_namespace")
        and not project.get("archived")
        and not project.get("forked_from_project")
    ]
    mentioned = mentioned_repos(ideas, [], raws) if ideas else set()
    ideas_lower = ideas.lower()

    def lead(raw: dict[str, Any], main_language: str | None) -> RepoLead:
        full = str(raw["full_name"])
        in_ideas = full.lower() in mentioned or str(raw["html_url"]).lower() in ideas_lower
        score, reasons = repo_lead_score(
            {**raw, "language": main_language},
            beginner_issues=0,
            ideas_mention=in_ideas,
            language=language,
            person=person,
        )
        # last_activity_at moves on issues and merge requests too, not only on pushes.
        reasons = [reason.replace("Pushed", "Active") for reason in reasons]
        return RepoLead(
            full_name=full,
            url=str(raw["html_url"]),
            description=clean_untrusted(raw.get("description"), limit=300) or None,
            language=main_language,
            stars=int(raw.get("stargazers_count") or 0),
            pushed_at=_dt(raw.get("pushed_at")),
            ideas_mention=in_ideas,
            score=score,
            reasons=reasons,
        )

    first = sorted((lead(raw, None) for raw in raws), key=lambda x: (-x.score, -x.stars))
    by_name = {str(raw["full_name"]): raw for raw in raws}
    # The main language costs one request per project, so only the likely top get it.
    rescored: list[RepoLead] = []
    for candidate in first[: limit + 5]:
        try:
            languages = http.get_json(
                f"{base}/projects/{quote(candidate.full_name, safe='')}/languages", ttl=3600
            )
        except GigError:
            languages = {}
        main = (
            max(languages, key=lambda name: float(languages[name]))
            if isinstance(languages, dict) and languages
            else None
        )
        rescored.append(lead(by_name[candidate.full_name], main))
    rescored.sort(key=lambda x: (-x.score, -x.stars))
    return rescored[:limit]


_PROJECT_URL = re.compile(
    r"^(?:https?://)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})/((?:[\w.-]+/)+[\w.-]+?)/?(?:/-/.*)?$"
)


def parse_gitlab_project(ref: str) -> tuple[str, str] | None:
    """(host, project path) for a project link on a host other than GitHub, else None.

    "sympy/sympy" has no host and stays a GitHub name; "gitlab.gnome.org/GNOME/gitg"
    works with or without "https://" and with a "/-/issues" tail from the address bar.
    """
    # "-" fits the path class, so the "/-/issues/494" tail is cut before matching.
    match = _PROJECT_URL.match((ref or "").strip().split("/-/", 1)[0])
    if not match:
        return None
    host = match.group(1).lower().removeprefix("www.")
    path = match.group(2).strip("/").removesuffix(".git")
    if host == "github.com" or "/" not in path:
        return None
    return host, path


def gitlab_repo_health(
    http: CachedHttpClient, host: str, path: str
) -> tuple[RepoHealth, ContributionGuide]:
    """The same grade `repo` gives a GitHub repository, from a GitLab project's public
    API: its merge requests (members count as insiders), the files in its tree, its
    license and languages, and open issues under a common beginner label. The time to
    a first reply is not read (one request per merge request), so merge times stand
    in for it, as they do on GitHub without comments.

    Raises NotFoundError when `path` is not a project the host answers for.
    """
    base = f"https://{host}/api/v4"
    pid = quote(path, safe="")
    project = http.get_json(f"{base}/projects/{pid}", params={"license": "true"}, ttl=3600)
    if not isinstance(project, dict) or not project.get("web_url"):
        raise NotFoundError(
            f"{host}/{path} did not answer as a GitLab project",
            status_code=404,
            url=f"https://{host}/{path}",
        )
    web_url = str(project["web_url"])
    branch = str(project.get("default_branch") or "main")
    full = str(project.get("path_with_namespace") or path)
    unread: list[str] = []

    def read(url: str, *, what: str, params: dict[str, Any] | None = None) -> Any:
        """None for a 404 (an answer) and for a failed read, which is also noted."""
        try:
            return http.get_json(url, params=params, ttl=3600)
        except NotFoundError:
            return None
        except GigError:
            unread.append(what)
            return None

    def read_text(url: str, *, what: str) -> str:
        try:
            return http.get_text(url, params={"ref": branch}, ttl=3600)
        except NotFoundError:
            return ""
        except GigError:
            unread.append(what)
            return ""

    tree = read(
        f"{base}/projects/{pid}/repository/tree",
        what="file listing",
        params={"per_page": 100, "ref": branch},
    )
    entries = [e for e in (tree if isinstance(tree, list) else []) if isinstance(e, dict)]
    names = [str(e.get("name") or "") for e in entries]
    contributing = next((n for n in names if n.upper().startswith("CONTRIBUTING")), None)
    readme = next((n for n in names if n.upper().startswith("README")), None)
    templates = False
    if ".gitlab" in names:
        sub = read(
            f"{base}/projects/{pid}/repository/tree",
            what="template listing",
            params={"path": ".gitlab", "per_page": 100, "ref": branch},
        )
        templates = any(
            "template" in str(e.get("name") or "").lower()
            for e in (sub if isinstance(sub, list) else [])
            if isinstance(e, dict)
        )
    raw_url = f"{base}/projects/{pid}/repository/files/{{}}/raw"
    text = (
        read_text(raw_url.format(quote(contributing, safe="")), what="contributing guide")
        if contributing
        else ""
    )
    readme_text = (
        read_text(raw_url.format(quote(readme, safe="")), what="README")
        if readme and not contributing
        else ""
    )
    readme_guide = bool(readme_text) and readme_contributing_section(readme_text)
    contributing_source = "file" if contributing else "readme" if readme_guide else None

    users = read(f"{base}/projects/{pid}/users", what="members", params={"per_page": 100})
    insiders = frozenset(
        str(u.get("username"))
        for u in (users if isinstance(users, list) else [])
        if isinstance(u, dict) and u.get("username")
    )
    pulls: list[dict[str, Any]] = []
    for state in ("merged", "closed"):
        found = read(
            f"{base}/projects/{pid}/merge_requests",
            what="merge requests",
            params={"state": state, "order_by": "created_at", "sort": "desc", "per_page": 50},
        )
        for mr in found if isinstance(found, list) else []:
            if not isinstance(mr, dict):
                continue
            login = str((mr.get("author") or {}).get("username") or "")
            # Whoever merges has maintainer rights, and the member list misses people
            # whose access comes from the group (GNOME grants it there, 2026-11-01).
            merger = str((mr.get("merge_user") or mr.get("merged_by") or {}).get("username") or "")
            if merger:
                insiders = insiders | {merger}
            pulls.append(
                {
                    "number": mr.get("iid"),
                    "user": {"login": login, "type": "User"},
                    "created_at": mr.get("created_at"),
                    "merged_at": mr.get("merged_at"),
                    "closed_at": mr.get("closed_at") or mr.get("merged_at"),
                    "state": "closed",
                }
            )
    for pull in pulls:
        pull["author_association"] = "MEMBER" if pull["user"]["login"] in insiders else "NONE"
    pulls.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
    stats = pull_stats(pulls[:60], insiders=insiders or None)

    languages = read(f"{base}/projects/{pid}/languages", what="languages")
    language = (
        max(languages, key=lambda name: float(languages[name]))
        if isinstance(languages, dict) and languages
        else None
    )

    label: str | None = None
    open_beginner: int | None = None
    assigned_beginner: int | None = None
    for candidate in GITLAB_BEGINNER_LABELS[:4]:
        counts = read(
            f"{base}/projects/{pid}/issues_statistics",
            what="beginner issues",
            params={"labels": candidate},
        )
        total = ((counts or {}).get("statistics") or {}).get("counts") or {}
        if int(total.get("all") or 0):
            label, open_beginner = candidate, int(total.get("opened") or 0)
            assigned = read(
                f"{base}/projects/{pid}/issues_statistics",
                what="beginner issues",
                params={"labels": candidate, "assignee_id": "Any"},
            )
            assigned_counts = ((assigned or {}).get("statistics") or {}).get("counts") or {}
            assigned_beginner = int(assigned_counts.get("opened") or 0)
            break

    license_raw = project.get("license")
    license_obj: dict[str, Any] = license_raw if isinstance(license_raw, dict) else {}
    health = RepoHealth(
        full_name=f"{host}/{full}",
        url=web_url,
        description=clean_untrusted(project.get("description"), limit=350) or None,
        language=language,
        stars=int(project.get("star_count") or 0),
        forks=int(project.get("forks_count") or 0),
        open_issues=int(project.get("open_issues_count") or 0),
        archived=bool(project.get("archived")),
        pushed_at=_dt(project.get("last_activity_at")),
        license=str(license_obj.get("name") or license_obj.get("key") or "") or None,
        topics=[str(t) for t in project.get("topics") or project.get("tag_list") or []],
        has_contributing=contributing_source is not None,
        contributing_source=contributing_source,
        has_code_of_conduct=any(n.upper().startswith("CODE_OF_CONDUCT") for n in names),
        has_issue_template=templates,
        has_pr_template=templates,
        has_ci=".gitlab-ci.yml" in names or bool(project.get("ci_config_path")),
        unread=sorted(set(unread)),
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
        pr_source="gitlab",
        beginner_label=label,
        open_beginner_issues=open_beginner,
        assigned_beginner_issues=assigned_beginner,
    )
    toolchain, devcontainer = detect_toolchain([{"name": n} for n in names], language=language)
    hints = list(toolchain)
    if devcontainer:
        hints.insert(0, "Dev container available: open in VS Code for a ready environment")
    if not hints:
        hints.append(
            f"Read {readme or 'the README'} and {contributing} before coding"
            if contributing
            else f"Read the contributing section of {readme} before coding"
            if readme_guide
            else f"Read {readme or 'the README'} before coding"
        )
    guide_file = contributing or (readme if readme_guide else None)
    guide = ContributionGuide(
        repo=f"{host}/{full}",
        contributing_url=f"{web_url}/-/blob/{branch}/{guide_file}" if guide_file else None,
        contributing_excerpt=re.sub(
            r"\s+", " ", clean_untrusted(text or readme_text, limit=1500)
        ).strip(),
        contributing_text=text or readme_text,
        toolchain=toolchain,
        devcontainer=devcontainer,
        setup_hints=hints,
        communication_channels=channels_in(text or readme_text),
        beginner_issue_labels=[label] if label else ["good first issue"],
        unread=sorted(set(unread)),
    )
    return score_repo_health(health), guide


# Top-level directories read one page deep: GIMP has over a thousand files, and a
# recursive listing paged alphabetically left only its first five directories.
_TREE_DIRS = 20

_IMAGE_RUNTIMES = {
    "python": "Python",
    "node": "Node.js",
    "ruby": "Ruby",
    "golang": "Go",
    "rust": "Rust",
    "openjdk": "Java",
    "eclipse-temurin": "Java",
    "php": "PHP",
}
_IMAGE_RE = re.compile(r"^\s*image:\s*['\"]?([A-Za-z0-9._/-]+?):([\w.]+)")
_SERVICE_ITEM_RE = re.compile(
    r"^\s*-\s*(?:name:\s*)?['\"]?([A-Za-z0-9._/-]+)(?::([\w.-]+))?['\"]?\s*$"
)


def gitlab_ci_as_workflow(text: str) -> str:
    """A .gitlab-ci.yml rewritten so the GitHub Actions readers see its commands:
    each `script:` list becomes a `run: |` block. Everything else stays as it is."""
    out: list[str] = []
    script_indent: int | None = None
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip())
        if script_indent is not None:
            item = re.match(r"^\s*-\s+(.*)$", line)
            if line.strip() and indent <= script_indent:
                script_indent = None
            elif item:
                out.append(" " * (script_indent + 2) + item.group(1))
                continue
            elif line.strip():
                out.append(line)
                continue
        match = re.match(r"^(\s*)(?:before_|after_)?script:\s*(.*)$", line)
        if match:
            rest = match.group(2).strip()
            out.append(f"{match.group(1)}run: {rest}" if rest else f"{match.group(1)}run: |")
            script_indent = None if rest else indent
            continue
        out.append(line)
    return "\n".join(out)


def gitlab_ci_environment(text: str, *, source: str = ".gitlab-ci.yml") -> dict[str, Any]:
    """Runtimes from `image:` lines (python:3.12) and service containers, in the shape
    `ci_environment` gives for GitHub Actions."""
    versions: dict[str, list[str]] = {}
    services: list[dict[str, str]] = []
    lines = text.splitlines()
    in_services: int | None = None
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if in_services is not None:
            if line.strip() and indent <= in_services:
                in_services = None
            else:
                item = _SERVICE_ITEM_RE.match(line)
                if item:
                    name = item.group(1).rsplit("/", 1)[-1]
                    image = item.group(1) + (f":{item.group(2)}" if item.group(2) else "")
                    if name not in (s["name"] for s in services):
                        services.append({"name": name, "image": image, "source": source})
                continue
        if re.match(r"^\s*services:\s*$", line):
            in_services = indent
            continue
        image = _IMAGE_RE.match(line)
        if image:
            runtime = _IMAGE_RUNTIMES.get(image.group(1).rsplit("/", 1)[-1])
            version = image.group(2).split("-", 1)[0]
            if (
                runtime
                and version[:1].isdigit()
                and version not in versions.setdefault(runtime, [])
            ):
                versions[runtime].append(version)
    return {
        "runtimes": [
            {
                "name": name,
                "versions": found,
                "most_used": found[0] if len(found) == 1 else None,
                "source": source,
            }
            for name, found in versions.items()
        ],
        "services": services,
        "runners": [],
    }


def _gitlab_tree(
    http: CachedHttpClient, base: str, pid: str, branch: str
) -> tuple[list[dict[str, Any]], bool]:
    """The top level of a project's tree plus one page of each top-level directory, and
    whether anything was cut (a directory over 100 entries, or more directories than
    _TREE_DIRS). A failed read gives an empty page, never an error."""

    def page(params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            found = http.get_json(
                f"{base}/projects/{pid}/repository/tree",
                params={**params, "per_page": 100, "ref": branch},
                ttl=3600,
            )
        except GigError:
            return []
        return [e for e in (found if isinstance(found, list) else []) if isinstance(e, dict)]

    top = page({})
    directories = [str(e.get("path")) for e in top if e.get("type") == "tree" and e.get("path")]
    truncated = len(top) >= 100 or len(directories) > _TREE_DIRS
    entries: list[dict[str, Any]] = list(top)
    for directory in directories[:_TREE_DIRS]:
        inside = page({"path": directory, "recursive": "true"})
        entries.extend(inside)
        truncated = truncated or len(inside) >= 100
    return entries, truncated


def gitlab_orientation(
    http: CachedHttpClient, host: str, path: str, *, codetour: bool = False
) -> dict[str, Any]:
    """The orientation sheet `orient` gives for a GitHub repository, read from a GitLab
    project's public API: tree, languages, 90 days of commits, merged merge requests
    (for the work branch), the protected default branch, CONTRIBUTING and the merge
    request template, and .gitlab-ci.yml. A worked-example merge request is left out:
    its changed files need a sign-in.

    Raises NotFoundError when `path` is not a project the host answers for.
    """
    base = f"https://{host}/api/v4"
    pid = quote(path, safe="")
    project = http.get_json(f"{base}/projects/{pid}", params={"license": "true"}, ttl=3600)
    if not isinstance(project, dict) or not project.get("web_url"):
        raise NotFoundError(
            f"{host}/{path} did not answer as a GitLab project",
            status_code=404,
            url=f"https://{host}/{path}",
        )
    web_url = str(project["web_url"])
    branch = str(project.get("default_branch") or "main")
    full = str(project.get("path_with_namespace") or path)

    def read(url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return http.get_json(url, params=params, ttl=3600)
        except GigError:
            return None

    def read_text(file_path: str) -> str:
        try:
            return http.get_text(
                f"{base}/projects/{pid}/repository/files/{quote(file_path, safe='')}/raw",
                params={"ref": branch},
                ttl=3600,
            )
        except GigError:
            return ""

    entries, truncated = _gitlab_tree(http, base, pid, branch)
    found_paths = find_paths(entries)
    blobs = {
        str(e.get("path")).lower(): str(e.get("path")) for e in entries if e.get("type") == "blob"
    }
    if not found_paths.get("codeowners") and ".gitlab/codeowners" in blobs:
        found_paths["codeowners"] = blobs[".gitlab/codeowners"]
    if not found_paths.get("pr_template"):
        templates = sorted(
            p for low, p in blobs.items() if low.startswith(".gitlab/merge_request_templates/")
        )
        if templates:
            found_paths["pr_template"] = templates[0]
    ci_path = blobs.get(".gitlab-ci.yml")

    texts = {
        key: read_text(found_paths[key])
        for key in ("contributing", "pr_template", "pyproject", "package_json", "codeowners")
        if found_paths.get(key)
    }
    ci_text = read_text(ci_path) if ci_path else ""
    workflow_texts = {ci_path: gitlab_ci_as_workflow(ci_text)} if ci_path and ci_text else {}

    langs = read(f"{base}/projects/{pid}/languages")
    languages = (
        [
            {"name": name, "share": round(float(share))}
            for name, share in sorted(langs.items(), key=lambda kv: -float(kv[1]))[:4]
        ]
        if isinstance(langs, dict)
        else []
    )
    raw_commits = read(
        f"{base}/projects/{pid}/repository/commits", {"since": since_iso(90), "per_page": 100}
    )
    commits = [
        {
            "commit": {
                "message": str(c.get("message") or c.get("title") or ""),
                "author": {"name": c.get("author_name")},
            },
            "author": {"login": "", "type": "User"},
        }
        for c in (raw_commits if isinstance(raw_commits, list) else [])
        if isinstance(c, dict)
    ]
    raw_merged = read(
        f"{base}/projects/{pid}/merge_requests",
        {"state": "merged", "order_by": "created_at", "sort": "desc", "per_page": 30},
    )
    merged = [
        {
            "number": mr.get("iid"),
            "merged_at": mr.get("merged_at"),
            "base": {"ref": mr.get("target_branch")},
            "user": {"login": (mr.get("author") or {}).get("username"), "type": "User"},
        }
        for mr in (raw_merged if isinstance(raw_merged, list) else [])
        if isinstance(mr, dict) and mr.get("merged_at")
    ]
    merged = [mr for mr in merged if not is_bot(mr.get("user"))]
    head = read(f"{base}/projects/{pid}/repository/branches/{quote(branch, safe='')}")
    as_of = ((head or {}).get("commit") or {}).get("id") if isinstance(head, dict) else None

    gates: list[dict[str, str]] = []
    protected = read(f"{base}/projects/{pid}/protected_branches")
    for rule in protected if isinstance(protected, list) else []:
        if not isinstance(rule, dict) or rule.get("name") != branch:
            continue
        who = ", ".join(
            str(level.get("access_level_description") or "")
            for level in rule.get("push_access_levels") or []
            if isinstance(level, dict)
        )
        gates.append(
            {
                "gate": f"Direct pushes to `{branch}` are limited to {who or 'maintainers'}: "
                "changes go through a merge request",
                "source": "protected branches",
            }
        )

    points = entry_points(
        entries, pyproject=texts.get("pyproject"), package_json=texts.get("package_json")
    )
    rules = conventions(
        commits,
        contributing=texts.get("contributing", ""),
        pr_template=texts.get("pr_template", ""),
        check_names=[],
        found=found_paths,
    )
    rules["gates"] = gates
    license_raw = project.get("license")
    license_obj: dict[str, Any] = license_raw if isinstance(license_raw, dict) else {}
    result: dict[str, Any] = {
        "repo": f"{host}/{full}",
        "url": web_url,
        "description": clean_untrusted(project.get("description"), limit=300),
        "default_branch": branch,
        "work_branch": work_branch(merged, default=branch),
        "as_of_commit": as_of,
        "tree_truncated": truncated,
        "stars": int(project.get("star_count") or 0),
        "license": str(license_obj.get("name") or license_obj.get("key") or "") or None,
        "pushed_days_ago": days_since(project.get("last_activity_at")),
        "languages": languages,
        "code_map": code_map(entries, repo_name=full.rsplit("/", 1)[-1]),
        "entry_points": points,
        "test_commands": ci_test_commands(workflow_texts),
        "ci_environment": gitlab_ci_environment(ci_text)
        if ci_text
        else {"runtimes": [], "services": [], "runners": []},
        "setup_hints": [f"{found_paths['makefile']} lists local targets"]
        if found_paths.get("makefile")
        else [],
        "docs": {
            "readme": found_paths.get("readme"),
            "contributing": found_paths.get("contributing"),
            "architecture": found_paths.get("architecture_docs") or [],
            "governance": found_paths.get("governance"),
            "test_dirs": found_paths.get("test_dirs") or [],
        },
        "maintainers": {
            "active_committers_90d": active_committers(commits),
            "commits_90d": len(commits),
            "codeowners": [],
            "codeowners_path": found_paths.get("codeowners"),
        },
        "conventions": rules,
        "policies": policy_quotes(
            {
                str(found_paths.get("contributing") or "CONTRIBUTING"): texts.get(
                    "contributing", ""
                ),
                str(found_paths.get("pr_template") or "MR template"): texts.get("pr_template", ""),
            }
        ),
        "channels": channels_in(texts.get("contributing", "")),
        "example_pr": None,
        "reading_plan": reading_plan(found=found_paths, points=points, example_pr=None),
        "note": (
            "Read through GitLab's public API. Purpose labels on the code map are guesses "
            "from directory names; everything else names a real file, commit, or check. "
            "A worked-example merge request is not shown: its changed files need a sign-in. "
            "File counts stop at 100 per directory. Read the files; do not rely on a summary."
        ),
    }
    if codetour:
        result["codetour"] = codetour_from_orientation(result)
    return result


def gitlab_issue_pointers(
    http: CachedHttpClient,
    host: str,
    path: str,
    number: int,
    *,
    similar: int = 5,
    code_search: bool = True,
    token: str | None = None,
    token_host: str | None = None,
) -> dict[str, Any]:
    """Where to start reading for an issue on a GitLab host, in the shape `pointers`
    gives for GitHub: paths the issue names resolved against the tree, closed issues
    with the same beginner label and the merge requests that closed them, and a fix
    norm when the changed files could be read. Code search and the files a merge
    request changed need a sign-in to the host (GITLAB_TOKEN with GITLAB_HOST); without
    one, search links are given and the fix norm stays empty.

    Raises NotFoundError when the project or the issue is not there.
    """
    base = f"https://{host}/api/v4"
    pid = quote(path, safe="")
    repo = f"{host}/{path}"
    project = http.get_json(f"{base}/projects/{pid}", ttl=3600)
    issue = http.get_json(f"{base}/projects/{pid}/issues/{number}", ttl=300)
    if not isinstance(project, dict) or not isinstance(issue, dict):
        raise NotFoundError(
            f"Could not read {repo} issue {number} through GitLab's public API",
            status_code=404,
            url=f"https://{host}/{path}/-/issues/{number}",
        )
    branch = str(project.get("default_branch") or "main")
    signed_in = bool(token) and _same_host(host, token_host)
    headers = {"Authorization": f"Bearer {token}"} if signed_in else None

    def read(url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return http.get_json(url, params=params, headers=headers, ttl=300)
        except GigError:
            return None

    entries, _ = _gitlab_tree(http, base, pid, branch)
    tree_paths = [str(e.get("path")) for e in entries if e.get("type") == "blob" and e.get("path")]
    title = str(issue.get("title") or "")
    mentions = extract_mentions(f"{title}\n{issue.get('description') or ''}", repo=repo)
    resolved = resolve_paths(mentions, tree_paths)
    resolved_paths = {r["path"] for r in resolved}
    unresolved = [
        m["text"]
        for m in mentions
        if m["kind"] in {"identifier", "backtick"} and m["text"] not in resolved_paths
    ][:4]
    searched: list[dict[str, Any]] = []
    code_search_note = ""
    if code_search and unresolved and signed_in:
        for ident in unresolved[:2]:
            hits = read(
                f"{base}/projects/{pid}/search", {"scope": "blobs", "search": ident, "per_page": 8}
            )
            if hits is None:
                code_search_note = f"Code search on {host} did not answer."
                break
            paths = code_first(
                [
                    str(h.get("path") or h.get("filename"))
                    for h in hits
                    if isinstance(h, dict) and (h.get("path") or h.get("filename"))
                ]
            )
            searched.append({"identifier": ident, "paths": paths[:6]})
            for found_path in paths[:3]:
                if found_path not in resolved_paths:
                    resolved_paths.add(found_path)
                    resolved.append(
                        {
                            "path": found_path,
                            "score": 1.0,
                            "lines": [],
                            "reasons": [f"code search: {ident}"],
                            "confidence": "code search",
                        }
                    )
    elif code_search and unresolved:
        code_search_note = (
            f"Code search on {host} needs a sign-in (set GITLAB_TOKEN and GITLAB_HOST); "
            "search links are given instead."
        )
    if not resolved:
        resolved = title_file_matches(title, tree_paths)

    own_labels = [str(label) for label in issue.get("labels") or []]
    label = next((lab for lab in own_labels if is_beginner_label(lab)), None) or (
        own_labels[0] if own_labels else None
    )
    fixes: list[dict[str, Any]] = []
    shared = False
    if label is None:
        similar_note = "No label on this issue to look up similar closed issues with."
    else:
        closed = read(
            f"{base}/projects/{pid}/issues",
            {"state": "closed", "labels": label, "per_page": 30, "order_by": "updated_at"},
        )
        items = [
            i
            for i in (closed if isinstance(closed, list) else [])
            if isinstance(i, dict) and i.get("iid") and i.get("iid") != number
        ]
        for item in items:
            item["number"] = item.get("iid")
        if closed is None:
            similar_note = f"Could not list closed '{label}' issues on {host}."
        elif not items:
            similar_note = f"No closed issues carry the '{label}' label yet."
        else:
            items, shared = rank_similar(title, items, limit=similar)
            similar_note = (
                ""
                if shared
                else f"None of the closed '{label}' issues share words with this title; these are the most recent ones."
            )
            for item in items:
                closers = read(f"{base}/projects/{pid}/issues/{item['iid']}/closed_by") or []
                # closed_by lists the merge requests whose text closes the issue; shaped as
                # GitHub timeline events so closing_pull_request picks the same way.
                events = [
                    {
                        "event": "cross-referenced",
                        "source": {
                            "issue": {
                                "pull_request": {"merged_at": mr.get("merged_at")},
                                "number": mr.get("iid"),
                                "html_url": mr.get("web_url"),
                                "title": mr.get("title"),
                                "user": {"login": (mr.get("author") or {}).get("username")},
                                "created_at": mr.get("created_at"),
                                "repository": {"full_name": repo},
                            }
                        },
                    }
                    for mr in closers
                    if isinstance(mr, dict) and mr.get("merged_at")
                ]
                closer = closing_pull_request(item, events, repo=repo)
                if not closer:
                    continue
                closer["confidence"] = str(closer["confidence"]).replace("PR", "MR")
                files: list[str] = []
                if signed_in:
                    diffs = read(
                        f"{base}/projects/{pid}/merge_requests/{closer['number']}/diffs",
                        {"per_page": 50},
                    )
                    files = [
                        str(d.get("new_path"))
                        for d in (diffs if isinstance(diffs, list) else [])
                        if isinstance(d, dict) and d.get("new_path")
                    ]
                fixes.append(
                    {
                        "issue": {
                            "number": int(item["iid"]),
                            "title": clean_untrusted(item.get("title"), limit=120),
                            "url": item.get("web_url"),
                        },
                        "pull_request": closer,
                        "files": files[:12],
                        "additions": 0,
                        "deletions": 0,
                        "days_to_merge": days_between(
                            closer.get("opened_at"), closer.get("merged_at")
                        ),
                    }
                )
            if items and not fixes and not similar_note:
                similar_note = f"The closed '{label}' issues were not closed by a merge request that names them."
    project_id = project.get("id")
    search_links = [
        {
            "identifier": ident,
            "url": f"https://{host}/search?project_id={project_id}&scope=blobs&search={quote(ident, safe='')}",
        }
        for ident in unresolved
        if project_id and not any(s["identifier"] == ident for s in searched)
    ]
    head = read(f"{base}/projects/{pid}/repository/branches/{quote(branch, safe='')}")
    files_note = (
        ""
        if signed_in
        else " The files each merge request changed need a sign-in to read (GITLAB_TOKEN and "
        "GITLAB_HOST), so open the merge requests to see them."
    )
    return {
        "issue": {
            "repo": repo,
            "number": number,
            "title": clean_untrusted(title, limit=200),
            "url": issue.get("web_url") or f"https://{host}/{path}/-/issues/{number}",
            "labels": own_labels,
        },
        "as_of_commit": ((head or {}).get("commit") or {}).get("id")
        if isinstance(head, dict)
        else None,
        "files_likely_involved": resolved[:8],
        "code_search": searched,
        "search_links": search_links[:4],
        "code_search_note": code_search_note,
        "similar_fixes": fixes,
        "similar_label": label,
        "similar_note": similar_note,
        "similar_shares_title_words": shared,
        "fix_norm": fix_norm(fixes),
        "next_step": (
            "Open the files above and the merge requests for similar issues before touching "
            "code. If no file resolved, the issue needs clarification: ask in the thread what "
            "part of the code it concerns." + files_note
        ),
        "note": "Pointers are places to read, not a diagnosis. The fix is yours to work out.",
    }
