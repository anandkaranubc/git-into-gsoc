"""Decide whether an issue is genuinely free to pick up.

Works on the issue payload plus its timeline (comments, cross-references,
assignments), so a single extra API call gives: linked PRs and their state,
who asked to work on it and when, whether a maintainer granted it, and whether
maintainers are engaged at all. During GSoC season the common failure mode is
an issue with five "can I work on this?" comments; that is surfaced as
`contested` instead of `available`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.models import Availability, IssueAssessment, IssueClaim, LinkedPullRequest

MAINTAINER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}
# Labels projects use to mark an issue as taken, with or without an assignee.
RESERVED_LABELS = {
    "assigned",
    "claimed",
    "taken",
    "in progress",
    "in-progress",
    "wip",
    "work in progress",
    "has-pr",
    "has pr",
    "pr-open",
    "pr open",
    "pr opened",
}
# The same words inside a longer label, such as "good first issue (taken)".
_RESERVED_WORD_RE = re.compile(
    r"\b(taken|claimed|in[ -]progress|wip|has[ -]pr|pr[ -]open(?:ed)?)\b", re.I
)
RECENT_CLAIM_DAYS = 30
CONTESTED_WINDOW_DAYS = 60
CONTESTED_MIN_CLAIMANTS = 3
STALE_DAYS = 365

_CLAIM_PATTERNS = [
    r"\bi(?:'m| am) (?:currently |now )?working on (?:this|it|the issue)\b",
    r"\bi(?:'ll| will) (?:take|work on|pick up|handle|fix) (?:this|it)\b",
    r"\b(?:can|could|may) i (?:please )?(?:work on|take|pick up|tackle|fix|be assigned|get assigned)\b",
    r"\b(?:please |kindly )?assign (?:this |it )?(?:issue )?(?:to )?me\b",
    r"\bi(?:'d| would) (?:really )?(?:like|love) to (?:work on|take|tackle|pick up|fix|contribute to) (?:this|it)\b",
    r"\b(?:i want|wanting) to work on (?:this|it)\b",
    r"\bclaiming (?:this|it)\b",
    r"\bi(?:'ve| have) (?:started|begun) working\b",
    r"\bis (?:this|it) (?:still )?(?:available|open) (?:to|for) (?:work|take)\b",
    # bot commands used by Kubernetes, pandas, Zulip, Rust, Beam and others
    r"^\s*/(?:assign(?:-me)?|take|claim)\s*$",
    r"^\s*\.take(?:-issue)?\s*$",
    r"^\s*@\w+bot\s+claim\b",
]
_RELEASE_PATTERNS = [
    r"^\s*/(?:unassign(?:-me)?|release|unclaim)\s*$",
    r"^\s*\.(?:release|unassign)\s*$",
    r"^\s*@\w+bot\s+(?:abandon|unclaim|release)\b",
    r"\b(?:i(?:'m| am) )?no longer (?:working on|able to work on|interested in) (?:this|it)\b",
    r"\b(?:please )?unassign me\b",
    r"\bfeel free to (?:take|pick) (?:this|it) (?:over|up)\b",
    r"\bhas been (?:automatically )?unassigned\b",
    r"\bunassigned (?:due to|because of|for) inactivity\b",
]
_GRANT_PATTERNS = [
    r"\bassigned\b",
    r"\bgo ahead\b",
    r"\bgo for it\b",
    r"\bfeel free\b",
    r"\ball yours\b",
    r"\bsure,? (?:go|you can|please)\b",
]
_CLAIM_RE = re.compile("|".join(_CLAIM_PATTERNS), re.IGNORECASE | re.MULTILINE)
_GRANT_RE = re.compile("|".join(_GRANT_PATTERNS), re.IGNORECASE)
_RELEASE_RE = re.compile("|".join(_RELEASE_PATTERNS), re.IGNORECASE | re.MULTILINE)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _login(obj: dict[str, Any] | None) -> str | None:
    return (obj or {}).get("login")


def _is_bot(user: dict[str, Any] | None) -> bool:
    login = _login(user) or ""
    return (user or {}).get("type") == "Bot" or login.endswith("[bot]")


def is_claim(text: str) -> bool:
    return bool(_CLAIM_RE.search(text or ""))


def is_grant(text: str) -> bool:
    return bool(_GRANT_RE.search(text or ""))


def is_release(text: str) -> bool:
    """A comment that gives an issue back: a bot command, a withdrawal, or an auto-unassign."""
    return bool(_RELEASE_RE.search(text or ""))


def assess_issue(
    issue: dict[str, Any],
    timeline: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> IssueAssessment:
    now = now or datetime.now(UTC)
    caveats: list[str] = []
    claims: dict[str, IssueClaim] = {}
    linked: dict[str, LinkedPullRequest] = {}
    maintainer_engaged = False
    last_activity = _dt(issue.get("updated_at"))

    for event in timeline:
        kind = event.get("event")
        at = _dt(event.get("created_at") or event.get("updated_at"))
        if kind == "commented":
            user = event.get("user") or event.get("actor")
            body = str(event.get("body") or "")
            if _is_bot(user):
                if is_release(body):
                    _release(claims, body, caveats, who=None)
                continue
            role = str(event.get("author_association") or "")
            login = _login(user)
            if is_release(body) and login:
                _release(claims, body, caveats, who=login)
            if role in MAINTAINER_ROLES:
                maintainer_engaged = True
                if is_grant(body):
                    _grant(claims, body)
            elif is_claim(body) and not is_release(body) and at is not None and login:
                claims[login] = IssueClaim(login=login, at=at, days_ago=(now - at).days)
        elif kind == "unassigned":
            login = _login(event.get("assignee"))
            if login and login in claims:
                del claims[login]
                caveats.append(f"@{login} was unassigned later; the issue is open again")
        elif kind == "cross-referenced":
            source = (event.get("source") or {}).get("issue") or {}
            if "pull_request" in source:
                merged = bool((source.get("pull_request") or {}).get("merged_at"))
                number = source.get("number")
                key = str(number or source.get("html_url") or len(linked))
                linked[key] = LinkedPullRequest(
                    number=int(number) if number else None,
                    url=source.get("html_url"),
                    state="merged" if merged else str(source.get("state") or "unknown"),
                    author=_login(source.get("user")),
                    draft=bool(source.get("draft")),
                )
        elif kind == "connected":
            caveats.append(
                "A PR may be linked through the Development sidebar; check before starting"
            )
        if at and (last_activity is None or at > last_activity):
            last_activity = at

    assignees = [a for a in (_login(x) for x in issue.get("assignees") or []) if a]
    if not assignees and issue.get("assignee"):
        assignees = [a for a in [_login(issue.get("assignee"))] if a]
    prs = sorted(linked.values(), key=lambda p: p.number or 0)
    claim_list = sorted(claims.values(), key=lambda c: c.at, reverse=True)
    activity_days = (now - last_activity).days if last_activity else None

    if any(p.state == "merged" for p in prs):
        caveats.append("A merged PR references this issue; it may already be partly fixed")

    def result(status: Availability, reason: str) -> IssueAssessment:
        return IssueAssessment(
            availability=status,
            reason=reason,
            claims=claim_list,
            linked_prs=prs,
            assignees=assignees,
            maintainer_engaged=maintainer_engaged,
            last_activity_days=activity_days,
            caveats=list(dict.fromkeys(caveats)),
        )

    if issue.get("state") and issue.get("state") != "open":
        return result(Availability.CLOSED, "Issue is closed")
    if assignees:
        return result(Availability.ASSIGNED, "Assigned to " + ", ".join(f"@{a}" for a in assignees))

    open_prs = [p for p in prs if p.state == "open"]
    if open_prs:
        pr = open_prs[0]
        ref = f"#{pr.number}" if pr.number else ""
        who = f" by @{pr.author}" if pr.author else ""
        draft = " (draft)" if pr.draft else ""
        return result(
            Availability.LIKELY_TAKEN, f"Open PR {ref}{who}{draft} references it".replace("  ", " ")
        )

    names = [
        str(lab.get("name") if isinstance(lab, dict) else lab) for lab in issue.get("labels") or []
    ]
    reserved = [
        name
        for name in names
        if name.strip().lower() in RESERVED_LABELS or _RESERVED_WORD_RE.search(name)
    ]
    if reserved:
        return result(Availability.CLAIMED, f"Label '{reserved[0]}' marks it as taken")

    granted = [c for c in claim_list if c.granted and c.days_ago <= CONTESTED_WINDOW_DAYS]
    if granted:
        c = granted[0]
        return result(Availability.CLAIMED, f"Maintainer approved @{c.login} {c.days_ago}d ago")
    window = [c for c in claim_list if c.days_ago <= CONTESTED_WINDOW_DAYS]
    if len(window) >= CONTESTED_MIN_CLAIMANTS:
        return result(
            Availability.CONTESTED,
            f"{len(window)} people asked to work on this in the last {CONTESTED_WINDOW_DAYS} days",
        )
    recent = [c for c in claim_list if c.days_ago <= RECENT_CLAIM_DAYS]
    if recent:
        c = recent[0]
        return result(Availability.CLAIMED, f"@{c.login} asked to work on it {c.days_ago}d ago")
    if claim_list:
        c = claim_list[0]
        caveats.append(
            f"@{c.login} asked {c.days_ago}d ago with no PR; ask politely in the thread first"
        )
    if activity_days is not None and activity_days > STALE_DAYS and not maintainer_engaged:
        return result(Availability.STALE, f"No activity for {activity_days} days")
    return result(Availability.AVAILABLE, "Open, unassigned, no open PR or recent claim")


def unverified_assessment() -> IssueAssessment:
    """Assessment to use when the issue timeline could not be fetched."""
    return IssueAssessment(
        availability=Availability.UNKNOWN,
        reason=(
            "Could not read the issue timeline; open the issue and check for claims "
            "and linked PRs yourself"
        ),
        caveats=["The timeline request failed, so claims and linked PRs were not checked"],
    )


def _release(
    claims: dict[str, IssueClaim], body: str, caveats: list[str], *, who: str | None
) -> None:
    """Drop claims a comment gives back: the author's own, or those it mentions."""
    mentioned = set(re.findall(r"@([A-Za-z0-9-]+)", body))
    targets = [login for login in claims if login in mentioned or (who and login == who)]
    if not targets and who is None and len(claims) == 1:
        targets = list(claims)
    for login in targets:
        del claims[login]
        caveats.append(f"@{login} released this issue later; it is open again")


def _grant(claims: dict[str, IssueClaim], body: str) -> None:
    mentioned = set(re.findall(r"@([A-Za-z0-9-]+)", body))
    targets = [c for login, c in claims.items() if login in mentioned]
    if not targets and claims:
        targets = [max(claims.values(), key=lambda c: c.at)]
    for claim in targets:
        claim.granted = True
