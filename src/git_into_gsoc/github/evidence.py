"""Contribution evidence: what a contributor has actually done in an org's repos.

Proposal reviewers look for prior interaction with the project. This module
turns four GitHub searches (PRs authored, issues opened, threads joined,
reviews given) into counts, paste-ready evidence lines, and honest gaps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.models import ContributionItem
from git_into_gsoc.text import clean_untrusted

STRENGTH_ORDER = ("none", "starting", "developing", "strong")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _repo_of(item: dict[str, Any]) -> str:
    parts = str(item.get("repository_url") or "").rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else ""


def _state(item: dict[str, Any]) -> str:
    if "pull_request" in item:
        pr = item.get("pull_request") or {}
        if pr.get("merged_at"):
            return "merged"
        return "open" if item.get("state") == "open" else "closed"
    return "open" if item.get("state") == "open" else "closed"


def to_item(item: dict[str, Any], kind: str) -> ContributionItem | None:
    repo = _repo_of(item)
    number = item.get("number")
    if "/" not in repo or not number:
        return None
    return ContributionItem(
        kind=kind,
        repo=repo,
        number=int(number),
        title=clean_untrusted(item.get("title"), limit=160),
        url=str(item.get("html_url") or ""),
        state=_state(item),
        author=(item.get("user") or {}).get("login"),
        created_at=_dt(item.get("created_at")),
        closed_at=_dt(item.get("closed_at")),
        comments=int(item.get("comments") or 0),
        labels=[str(lab.get("name")) for lab in item.get("labels") or [] if isinstance(lab, dict)],
    )


def _items(raw: list[dict[str, Any]], kind: str) -> list[ContributionItem]:
    seen: set[tuple[str, int]] = set()
    out: list[ContributionItem] = []
    for entry in raw:
        item = to_item(entry, kind)
        if item is None or (item.repo, item.number) in seen:
            continue
        seen.add((item.repo, item.number))
        out.append(item)
    out.sort(
        key=lambda i: (i.state != "merged", -(i.created_at.timestamp() if i.created_at else 0))
    )
    return out


def _evidence_line(item: ContributionItem) -> str:
    verb = {
        "pr": {"merged": "merged PR", "open": "open PR", "closed": "closed PR"},
        "issue": {"open": "opened issue", "closed": "opened issue (now closed)"},
        "discussion": {"open": "discussed", "closed": "discussed", "merged": "discussed"},
        "review": {"open": "reviewed PR", "closed": "reviewed PR", "merged": "reviewed PR"},
    }[item.kind].get(item.state, item.kind)
    when = f" ({item.created_at:%Y-%m-%d})" if item.created_at else ""
    return f"- {verb}: [{item.repo}#{item.number}]({item.url}) {item.title}{when}".rstrip()


def summarize_activity(
    username: str,
    *,
    prs: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    discussions: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Counts, ranked items, paste-ready evidence, and gaps for one contributor."""
    now = now or datetime.now(UTC)
    pr_items = _items(prs, "pr")
    issue_items = _items(issues, "issue")
    thread_items = _items(discussions, "discussion")
    review_items = _items(reviews, "review")

    counts = {
        "prs_merged": sum(1 for p in pr_items if p.state == "merged"),
        "prs_open": sum(1 for p in pr_items if p.state == "open"),
        "prs_closed_unmerged": sum(1 for p in pr_items if p.state == "closed"),
        "issues_opened": len(issue_items),
        "threads_joined": len(thread_items),
        "reviews_given": len(review_items),
    }
    everything = [*pr_items, *issue_items, *thread_items, *review_items]
    dates = sorted(i.created_at for i in everything if i.created_at)
    first_days = (now - dates[0]).days if dates else None
    last_days = (now - dates[-1]).days if dates else None
    repos = sorted({i.repo for i in everything})

    if counts["prs_merged"] >= 2 and (counts["threads_joined"] or counts["reviews_given"]):
        strength = "strong"
    elif counts["prs_merged"] >= 1:
        strength = "developing"
    elif everything:
        strength = "starting"
    else:
        strength = "none"

    gaps: list[str] = []
    if counts["prs_merged"] == 0:
        gaps.append(
            "No merged PR yet. One merged, non-trivial PR is the strongest signal mentors "
            "look for; a well-scoped docs or test fix counts."
        )
    if counts["prs_open"] and counts["prs_merged"] == 0:
        gaps.append("Follow up on open PRs: respond to reviews quickly and keep them small.")
    if not counts["threads_joined"] and not counts["reviews_given"]:
        gaps.append(
            "No visible participation in other people's threads. Answering a question or "
            "testing someone else's PR shows you are part of the community, not just a PR author."
        )
    if counts["issues_opened"] == 0 and everything:
        gaps.append(
            "No issues opened. A precise bug report with reproduction steps is a respected "
            "contribution and often leads to your own fix."
        )
    if last_days is not None and last_days > 45:
        gaps.append(f"Last activity was {last_days} days ago; recent, steady activity matters.")

    evidence = [_evidence_line(i) for i in [*pr_items, *issue_items, *review_items][:12]]
    return {
        "username": username,
        "counts": counts,
        "strength": strength,
        "first_activity_days_ago": first_days,
        "last_activity_days_ago": last_days,
        "repos": repos,
        "pull_requests": [p.model_dump(mode="json") for p in pr_items[:20]],
        "issues": [i.model_dump(mode="json") for i in issue_items[:20]],
        "threads_joined": [t.model_dump(mode="json") for t in thread_items[:20]],
        "reviews": [r.model_dump(mode="json") for r in review_items[:20]],
        "evidence_markdown": evidence,
        "gaps": gaps,
    }
