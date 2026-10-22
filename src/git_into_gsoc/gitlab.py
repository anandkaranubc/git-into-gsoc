"""Check an issue on a GitLab host (gitlab.com, gitlab.gnome.org, invent.kde.org).

About one in six GSoC organizations keep their code on GitLab. Its public API
answers without a token for the issue itself (state, assignees, labels) and for
the merge requests that reference it, but not for comments, so a claim written
in a comment cannot be seen. The status says so instead of guessing.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from git_into_gsoc.errors import GigError, NotFoundError
from git_into_gsoc.github.availability import (
    RESERVED_LABELS,
    STALE_DAYS,
    assess_issue,
    is_not_open_label,
)
from git_into_gsoc.http_client import CachedHttpClient
from git_into_gsoc.models import Availability
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
    try:
        issue = http.get_json(api, ttl=300)
    except GigError as exc:
        raise NotFoundError(
            f"Could not read {host}/{project} issue {number} through GitLab's public API",
            hint="It may be private, deleted, or on a host that is not GitLab. Open the link "
            "and check for an assignee, a merge request, and recent claims yourself.",
        ) from exc
    try:
        merge_requests = http.get_json(f"{api}/related_merge_requests", ttl=300)
    except GigError:
        merge_requests = []
    now = datetime.now(UTC)
    status, reason, linked, caveats = _status(
        issue if isinstance(issue, dict) else {},
        merge_requests if isinstance(merge_requests, list) else [],
        project=project,
        now=now,
    )
    notes = int(issue.get("user_notes_count") or 0)
    claims: list[dict[str, Any]] = []
    read_comments = False
    if notes and token and _same_host(host, token_host):
        try:
            found = http.get_json(
                f"{api}/notes",
                headers={"PRIVATE-TOKEN": token},
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
