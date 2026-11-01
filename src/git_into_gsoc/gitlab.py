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

from git_into_gsoc.errors import GigError, NotFoundError
from git_into_gsoc.github.availability import (
    RESERVED_LABELS,
    STALE_DAYS,
    assess_issue,
    is_not_open_label,
)
from git_into_gsoc.github.repos import (
    channels_in,
    detect_toolchain,
    mentioned_repos,
    pull_stats,
    readme_contributing_section,
    repo_lead_score,
)
from git_into_gsoc.http_client import CachedHttpClient
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

_ISSUE_URL = re.compile(
    r"^https://([A-Za-z0-9.-]+\.[A-Za-z]{2,})/((?:[\w.-]+/)+?[\w.-]+)/-/(?:issues|work_items)/(\d+)"
)


def parse_gitlab_issue(url: str) -> tuple[str, str, int] | None:
    """(host, project path, issue number) for a GitLab issue link, else None."""
    raw = (url or "").strip()
    if "://" not in raw and "/-/" in raw:
        raw = "https://" + raw  # copied from the address bar without "https://"
    match = _ISSUE_URL.match(raw)
    if not match or match.group(1).lower().removeprefix("www.") == "github.com":
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _days(value: str | None, now: datetime) -> int | None:
    if not value:
        return None
    try:
        return (now - datetime.fromisoformat(value.replace("Z", "+00:00"))).days
    except ValueError:
        return None


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


def _dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _issues_page(
    http: CachedHttpClient, url: str, label: str, *, since: str, per_page: int
) -> list[dict[str, Any]]:
    found = http.get_json(
        url,
        params={
            "state": "opened",
            "labels": label,
            "assignee_id": "None",
            "scope": "all",
            "updated_after": f"{since}T00:00:00Z",
            "order_by": "updated_at",
            "per_page": per_page,
        },
        ttl=300,
    )
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
) -> list[IssueCandidate]:
    """Open, unassigned issues under a GitLab group or project that carry one of
    `labels`, each checked for merge requests, free ones first.

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
            keep(_issues_page(http, url, labels[0], since=since, per_page=per_page))
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
            keep(_issues_page(http, listing, label, since=since, per_page=per_page))
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
