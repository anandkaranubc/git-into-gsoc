"""Token-free committer statistics from commits.ecosyste.ms.

ecosyste.ms clones repositories and publishes ``git shortlog`` style counts
with a generous anonymous limit (15,000 requests per hour) and day-long cache
headers. One call gives what GitHub cannot without a token and many requests:
how many different people committed in the last year, how many of them landed
exactly one commit (newcomers who got through), and how concentrated the work
is (bus factor). Everything here is best effort; failures return None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from git_into_gsoc.github.repos import is_bot
from git_into_gsoc.http_client import CachedHttpClient, HttpError

DEFAULT_API = "https://commits.ecosyste.ms/api/v1"


@dataclass(frozen=True)
class CommitStats:
    committers_last_year: int
    commits_last_year: int
    newcomer_committers_last_year: int  # exactly one commit in the year
    bus_factor: int | None  # smallest group of people behind more than half the commits
    synced_at: str | None


def _committer_is_bot(entry: dict[str, Any]) -> bool:
    login = entry.get("login") or ""
    name = str(entry.get("name") or "")
    return is_bot({"login": login, "type": "User"}) or name.endswith("[bot]")


def summarize(payload: dict[str, Any]) -> CommitStats | None:
    committers = [
        c
        for c in (payload.get("past_year_committers") or [])
        if isinstance(c, dict) and not _committer_is_bot(c)
    ]
    if not committers and not payload.get("past_year_total_commits"):
        return None
    counts = sorted((int(c.get("count") or 0) for c in committers), reverse=True)
    total = sum(counts)
    bus_factor: int | None = None
    if total:
        running = 0
        for index, count in enumerate(counts, start=1):
            running += count
            if running * 2 > total:
                bus_factor = index
                break
    return CommitStats(
        committers_last_year=len(counts),
        commits_last_year=total,
        newcomer_committers_last_year=sum(1 for c in counts if c == 1),
        bus_factor=bus_factor,
        synced_at=payload.get("last_synced_at"),
    )


def fetch_commit_stats(
    http: CachedHttpClient, *, api_url: str, owner: str, repo: str, ttl: int
) -> CommitStats | None:
    url = f"{api_url.rstrip('/')}/hosts/GitHub/repositories/{owner}/{repo}"
    try:
        data = http.get_json(url, ttl=ttl)
    except HttpError:
        return None
    return summarize(data) if isinstance(data, dict) else None
