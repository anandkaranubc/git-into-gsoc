"""Which of a contributor's open pull requests need them, and which are waiting on others.

Pure functions over three GitHub responses per pull request: the pull request
itself (draft flag, merge state), its issue timeline (commits, comments, and
reviews in order), and the check runs on its head commit. The idea comes from
oss-autopilot (MIT), which sorts open pull requests the same way; the rules
here are written for a newcomer who has one or two pull requests open.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

# A commit or reply counts as answering a comment only if it came this long
# after it; clocks and in-flight pushes make tighter comparisons unreliable.
RESPONSE_GAP = timedelta(minutes=2)
# The GSoC contributor guide suggests one follow-up after about five days of silence.
FOLLOW_UP_DAYS = 5
FAILED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _login(user: dict[str, Any] | None) -> str:
    return str((user or {}).get("login") or "")


# Machine accounts that GitHub reports as ordinary users (for example "stdlib-bot").
_BOT_NAME_RE = re.compile(r"(?:\[bot\]|[-_.]bot|^bot)$", re.I)
_SERVICE_ACCOUNTS = {
    "codecov",
    "coveralls",
    "netlify",
    "vercel",
    "sonarcloud",
    "mergify",
    "github-actions",
    "dependabot",
    "renovate",
    "pre-commit-ci",
    "allcontributors",
    "gitguardian",
    "changeset-bot",
    "welcome",
}


def _is_bot(user: dict[str, Any] | None) -> bool:
    login = _login(user)
    return (
        (user or {}).get("type") == "Bot"
        or bool(_BOT_NAME_RE.search(login))
        or login.lower() in _SERVICE_ACCOUNTS
    )


def _days(since: datetime | None, now: datetime) -> int | None:
    return None if since is None else max(0, (now - since).days)


def _ago(days: int | None) -> str:
    if days is None:
        return ""
    if days == 0:
        return "today"
    return "1 day ago" if days == 1 else f"{days} days ago"


def pull_request_status(
    pull: dict[str, Any],
    timeline: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Status of one open pull request from its author's point of view.

    `status` is "needs_you" when the author has something to do (a conflict, a
    failing check, requested changes, an unanswered comment, a draft) and
    "waiting" otherwise. `reasons` lists every problem found, most urgent first.
    """
    now = now or datetime.now(UTC)
    author = _login(pull.get("user")).lower()
    base = str((pull.get("base") or {}).get("ref") or "the default branch")

    last_author: datetime | None = _dt(pull.get("created_at"))
    last_commit: datetime | None = None
    last_other: tuple[datetime, str] | None = None
    latest_review: dict[str, tuple[str, datetime]] = {}

    def author_did(at: datetime | None) -> None:
        nonlocal last_author
        if at and (last_author is None or at > last_author):
            last_author = at

    for event in timeline:
        kind = event.get("event")
        if kind == "committed":
            at = _dt(
                ((event.get("author") or {}).get("date"))
                or (event.get("committer") or {}).get("date")
            )
            if at and (last_commit is None or at > last_commit):
                last_commit = at
            author_did(at)
            continue
        user = event.get("user") or event.get("actor")
        if _is_bot(user):
            continue
        login = _login(user).lower()
        at = _dt(event.get("submitted_at") or event.get("created_at"))
        if kind == "head_ref_force_pushed" and login == author:
            author_did(at)
        elif kind in {"commented", "reviewed", "line-commented"} and at:
            if login == author:
                author_did(at)
                continue
            if last_other is None or at > last_other[0]:
                last_other = (at, login)
            state = str(event.get("state") or "").lower()
            if kind == "reviewed" and state in {"approved", "changes_requested", "dismissed"}:
                latest_review[login] = (state, at)

    pending = [
        (who, at) for who, (state, at) in latest_review.items() if state == "changes_requested"
    ]
    approvers = [who for who, (state, _) in latest_review.items() if state == "approved"]
    failing = sorted(
        {
            str(c.get("name"))
            for c in checks
            if str(c.get("conclusion") or "").lower() in FAILED_CONCLUSIONS and c.get("name")
        }
    )
    running = any(str(c.get("status") or "").lower() in {"queued", "in_progress"} for c in checks)

    reasons: list[str] = []
    if str(pull.get("mergeable_state") or "").lower() == "dirty":
        reasons.append(f"Merge conflict with {base}: rebase your branch on {base} and push")
    if failing:
        shown = ", ".join(failing[:3]) + (
            f" and {len(failing) - 3} more" if len(failing) > 3 else ""
        )
        reasons.append(
            f"Failing check: {shown}. Read its log, and see whether it also fails on {base} "
            "before changing code"
        )
    for who, at in sorted(pending, key=lambda p: p[1]):
        if last_commit is None or last_commit < at + RESPONSE_GAP:
            reasons.append(
                f"@{who} requested changes {_ago(_days(at, now))} and no commit has followed; "
                "push the fixes as new commits and answer each comment"
            )
            break
    if last_other and (last_author is None or last_other[0] > last_author + RESPONSE_GAP):
        approved_and_green = bool(approvers) and not failing and not pending
        if not approved_and_green and not any("requested changes" in r for r in reasons):
            reasons.append(
                f"@{last_other[1]} commented {_ago(_days(last_other[0], now))} with no reply from you; "
                "answer in the thread, even if only to say when you will get to it"
            )
    if pull.get("draft"):
        reasons.append("Still a draft: mark it ready for review when it is")

    full_name = str(((pull.get("base") or {}).get("repo") or {}).get("full_name") or "")
    result: dict[str, Any] = {
        "ref": f"{full_name}#{pull.get('number')}" if full_name else f"#{pull.get('number')}",
        "repo": full_name,
        "url": pull.get("html_url"),
        "title": pull.get("title"),
        "status": "needs_you" if reasons else "waiting",
        "reasons": reasons,
        "checks_running": running,
    }
    if reasons:
        result["summary"] = reasons[0]
        return result

    quiet_days = _days(last_author, now)
    if approvers:
        result["summary"] = f"Approved by @{approvers[0]}; waiting for a maintainer to merge"
    elif last_other is None:
        result["summary"] = (
            f"No reply from a reviewer yet; you last opened or updated it {_ago(quiet_days)}"
        )
    else:
        result["summary"] = f"Waiting for review; your last update was {_ago(quiet_days)}"
    result["follow_up"] = bool(
        not approvers and quiet_days is not None and quiet_days >= FOLLOW_UP_DAYS
    )
    if result["follow_up"]:
        result["summary"] += "; one short, polite follow-up in the thread is fine"
    result["quiet_days"] = quiet_days
    return result
