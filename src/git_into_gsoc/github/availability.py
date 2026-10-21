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
from collections.abc import Callable
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
# Labels saying the issue is not ready for anyone to work on yet.
NOT_OPEN_LABELS = {
    "idea for discussion",
    "needs discussion",
    "discussion",
    "needs decision",
    "needs design",
    "design needed",
    "not ready",
    "on hold",
    "blocked",
}
# A project bot or maintainer telling claimants the issue cannot be assigned.
_NOT_OPEN_RE = re.compile(
    r"not (?:currently |yet )?(?:available|open) for (?:assignment|claims?|contributions?)", re.I
)
RECENT_CLAIM_DAYS = 30
STALE_PR_DAYS = 90
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
    r"\b(?:happy|glad) to (?:work on|take on|pick up|take|fix) (?:this|it)\b",
    r"\bi(?:'d| would) (?:really )?(?:like|love) to (?:pick|take) (?:this|it) (?:up|on)\b",
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
    r"\b(?:this|that|your plan|the plan|your approach) (?:sounds|looks) (?:good|great|fine)\b",
]
# A comment pointing at a pull request: "covered by #1293", "PR #12", or a PR link.
_PR_MENTION_RE = re.compile(
    r"\b(?:PR|pull request)\s*#(\d+)"
    r"|\b(?:covered|fixed|addressed|resolved|handled|implemented|solved|done|tackled)"
    r"\s+(?:by|in|with|via)\s+#(\d+)"
    r"|https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)",
    re.IGNORECASE,
)
MAX_PR_LOOKUPS = 3

PullLookup = Callable[[int], dict[str, Any] | None]
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


def _mentioned_pulls(body: str, repo: str) -> list[int]:
    """Pull request numbers in this repository that a comment points at."""
    numbers: list[int] = []
    for match in _PR_MENTION_RE.finditer(body):
        short, covered, other_repo, linked_number = match.groups()
        if other_repo and other_repo.lower() != repo.lower():
            continue
        numbers.append(int(short or covered or linked_number))
    return numbers


def _issue_repo(issue: dict[str, Any]) -> str:
    url = str(issue.get("html_url") or "")
    parts = url.split("github.com/", 1)[-1].split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


def assess_issue(
    issue: dict[str, Any],
    timeline: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    pull_lookup: PullLookup | None = None,
) -> IssueAssessment:
    """Classify one issue from its payload and timeline.

    `pull_lookup(number)` returns a pull request of the same repository, or None.
    With it, a comment such as "this is covered by #1293" counts when that pull
    request is open, even though the pull request itself never links the issue.
    """
    now = now or datetime.now(UTC)
    caveats: list[str] = []
    claims: dict[str, IssueClaim] = {}
    linked: dict[str, LinkedPullRequest] = {}
    mentioned: list[int] = []
    repo = _issue_repo(issue)
    maintainer_engaged = False
    last_activity = _dt(issue.get("updated_at"))

    not_open: str | None = None
    for event in timeline:
        kind = event.get("event")
        at = _dt(event.get("created_at") or event.get("updated_at"))
        if kind == "commented":
            user = event.get("user") or event.get("actor")
            body = str(event.get("body") or "")
            said = _NOT_OPEN_RE.search(body)
            if said and (
                _is_bot(user) or str(event.get("author_association") or "") in MAINTAINER_ROLES
            ):
                not_open = f"The project said it is {said.group(0)}"
            if _is_bot(user):
                if is_release(body):
                    _release(claims, body, caveats, who=None)
                continue
            role = str(event.get("author_association") or "")
            login = _login(user)
            if is_release(body) and login:
                _release(claims, body, caveats, who=login)
            mentioned += _mentioned_pulls(body, repo)
            if role in MAINTAINER_ROLES:
                maintainer_engaged = True
                if is_grant(body):
                    _grant(claims, body)
                # "@x are you still working on this?" keeps x's claim alive.
                if at is not None:
                    for name in set(re.findall(r"@([A-Za-z0-9-]+)", body)) & set(claims):
                        _touch(claims[name], at, now)
            elif is_claim(body) and not is_release(body) and at is not None and login:
                if login in claims:
                    _touch(claims[login], at, now)
                else:
                    claims[login] = IssueClaim(login=login, at=at, days_ago=(now - at).days)
            elif login in claims and not is_release(body) and at is not None:
                _touch(claims[login], at, now)  # the claimant is still talking about it
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
                touched = _dt(source.get("updated_at"))
                linked[key] = LinkedPullRequest(
                    number=int(number) if number else None,
                    url=source.get("html_url"),
                    state="merged" if merged else str(source.get("state") or "unknown"),
                    author=_login(source.get("user")),
                    draft=bool(source.get("draft")),
                    idle_days=(now - touched).days if touched else None,
                )
        elif kind == "connected":
            caveats.append(
                "A PR may be linked through the Development sidebar; check before starting"
            )
        if at and (last_activity is None or at > last_activity):
            last_activity = at

    known = {p.number for p in linked.values()} | {issue.get("number")}
    for number in [n for n in dict.fromkeys(mentioned) if n not in known][:MAX_PR_LOOKUPS]:
        pull = pull_lookup(number) if pull_lookup else None
        if not pull:
            continue  # not a pull request, or it could not be read
        merged = bool(pull.get("merged_at"))
        state = "merged" if merged else str(pull.get("state") or "unknown")
        if state == "closed":
            continue
        touched = _dt(pull.get("updated_at"))
        linked[f"comment-{number}"] = LinkedPullRequest(
            number=number,
            url=pull.get("html_url"),
            state=state,
            author=_login(pull.get("user")),
            draft=bool(pull.get("draft")),
            idle_days=(now - touched).days if touched else None,
            via_comment=True,
        )

    assignees = [a for a in (_login(x) for x in issue.get("assignees") or []) if a]
    if not assignees and issue.get("assignee"):
        assignees = [a for a in [_login(issue.get("assignee"))] if a]
    prs = sorted(linked.values(), key=lambda p: p.number or 0)
    claim_list = sorted(claims.values(), key=lambda c: c.at, reverse=True)
    activity_days = (now - last_activity).days if last_activity else None

    if any(p.state == "merged" for p in prs):
        caveats.append("A merged PR references this issue; it may already be partly fixed")
    abandoned = [p for p in prs if p.state == "closed"]
    if abandoned and not any(p.state in {"open", "merged"} for p in prs):
        refs = ", ".join(f"#{p.number}" for p in abandoned[:3] if p.number) or "an earlier PR"
        caveats.append(
            f"{refs} tried this and was closed without merging; read its review comments "
            "first, they show what the maintainers expect"
        )

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
        reason = (
            f"A comment says open PR {ref}{who}{draft} covers it"
            if pr.via_comment
            else f"Open PR {ref}{who}{draft} references it"
        ).replace("  ", " ")
        if pr.idle_days is not None and pr.idle_days >= STALE_PR_DAYS:
            # Still someone else's work, but a quiet one: say how to ask, as
            # is-it-claimed does, instead of implying the issue is out of reach.
            reason += f"; it has been idle for {pr.idle_days} days"
            caveats.append(
                f"The open PR has had no activity for {pr.idle_days} days; ask in the issue "
                "whether its author is still working on it before you start"
            )
        return result(Availability.LIKELY_TAKEN, reason)

    names = [
        str(lab.get("name") if isinstance(lab, dict) else lab) for lab in issue.get("labels") or []
    ]
    held = [name for name in names if name.strip().lower() in NOT_OPEN_LABELS]
    if held or not_open:
        reason = (
            f"Labelled '{held[0]}': the project is not taking claims on it yet"
            if held
            else str(not_open)
        )
        return result(Availability.NOT_OPEN, reason + "; pick another issue")
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
        return result(
            Availability.CLAIMED,
            f"A maintainer approved @{c.login}; the claim was last active {c.days_ago}d ago",
        )
    window = [c for c in claim_list if c.days_ago <= CONTESTED_WINDOW_DAYS]
    if len(window) >= CONTESTED_MIN_CLAIMANTS:
        return result(
            Availability.CONTESTED,
            f"{len(window)} people asked to work on this in the last {CONTESTED_WINDOW_DAYS} days",
        )
    recent = [c for c in claim_list if c.days_ago <= RECENT_CLAIM_DAYS]
    if recent:
        c = recent[0]
        return result(
            Availability.CLAIMED,
            f"@{c.login} asked to work on it; the claim was last active {c.days_ago}d ago",
        )
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


def _touch(claim: IssueClaim, at: datetime, now: datetime) -> None:
    """Move a claim's last sign of life forward."""
    if at > claim.at:
        claim.at = at
        claim.days_ago = (now - at).days


def _grant(claims: dict[str, IssueClaim], body: str) -> None:
    mentioned = set(re.findall(r"@([A-Za-z0-9-]+)", body))
    targets = [c for login, c in claims.items() if login in mentioned]
    if not targets and claims:
        targets = [max(claims.values(), key=lambda c: c.at)]
    for claim in targets:
        claim.granted = True
