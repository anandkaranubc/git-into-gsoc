"""Authenticated fast path for repository health: one GraphQL query instead of
a PR listing, returning the data REST cannot give cheaply.

* ``assignableUsers``: the people who can be assigned issues, which is the
  closest public approximation of "has write access". Together with the
  OWNER/MEMBER/COLLABORATOR associations it defines the insider set, so
  "outside contributor" means someone who is really outside.
* The first six timeline items of each of the last 50 closed PRs, which give
  the time to the first human (non-author, non-bot) reply: the signal that
  explains most of a PR's lifetime and predicts whether newcomers stay.

GraphQL requires a token, so this is only used when one is available; the
REST path remains the default and the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from git_into_gsoc.github.repos import is_bot
from git_into_gsoc.http_client import CachedHttpClient, HttpError

QUERY = """
query($owner: String!, $name: String!) {
  rateLimit { cost }
  repository(owner: $owner, name: $name) {
    assignableUsers(first: 100) { totalCount nodes { login } }
    pullRequests(last: 50, states: [MERGED, CLOSED]) {
      nodes {
        number title createdAt mergedAt closedAt authorAssociation
        author { login __typename }
        additions deletions changedFiles
        timelineItems(first: 6, itemTypes: [ISSUE_COMMENT, PULL_REQUEST_REVIEW, PULL_REQUEST_REVIEW_THREAD]) {
          nodes {
            __typename
            ... on IssueComment { createdAt author { login __typename } }
            ... on PullRequestReview { createdAt author { login __typename } }
            ... on PullRequestReviewThread { comments(first: 1) { nodes { createdAt author { login __typename } } } }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class PullAnalysis:
    """One query's answer: the insider set, REST-shaped pull request dicts, and its
    rate-limit cost in points."""

    insiders: frozenset[str]
    pulls: list[dict[str, Any]]
    cost: int = 0


def _author(node: dict[str, Any] | None) -> dict[str, Any]:
    node = node or {}
    return {"login": node.get("login"), "type": node.get("__typename") or "User"}


def _first_human_reply(pr: dict[str, Any], author_login: str | None) -> str | None:
    """Earliest comment/review by someone other than the author and not a bot."""
    candidates: list[str] = []
    for item in (pr.get("timelineItems") or {}).get("nodes") or []:
        entries = [item]
        if item.get("__typename") == "PullRequestReviewThread":
            entries = (item.get("comments") or {}).get("nodes") or []
        for entry in entries:
            who = _author(entry.get("author"))
            if not entry.get("createdAt") or not who["login"]:
                continue
            if who["login"] == author_login or is_bot(who):
                continue
            candidates.append(str(entry["createdAt"]))
    return min(candidates) if candidates else None


def normalize(data: dict[str, Any]) -> PullAnalysis | None:
    """Turn the GraphQL payload into REST-shaped PR dicts plus the insider set."""
    repo = (data.get("data") or {}).get("repository") or {}
    if not repo:
        return None
    insiders = frozenset(
        str(n.get("login")) for n in (repo.get("assignableUsers") or {}).get("nodes") or []
    )
    pulls: list[dict[str, Any]] = []
    for pr in (repo.get("pullRequests") or {}).get("nodes") or []:
        who = _author(pr.get("author"))
        pulls.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title") or "",
                "user": who,
                "author_association": pr.get("authorAssociation"),
                "created_at": pr.get("createdAt"),
                "merged_at": pr.get("mergedAt"),
                "closed_at": pr.get("closedAt"),
                "additions": pr.get("additions") or 0,
                "deletions": pr.get("deletions") or 0,
                "changed_files": pr.get("changedFiles") or 0,
                "first_response_at": _first_human_reply(pr, who["login"]),
            }
        )
    cost = int(((data.get("data") or {}).get("rateLimit") or {}).get("cost") or 0)
    return PullAnalysis(insiders=insiders, pulls=pulls, cost=cost)


def fetch_pull_analysis(
    http: CachedHttpClient,
    *,
    api_url: str,
    token: str,
    owner: str,
    repo: str,
    user_agent: str | None = None,
    ttl: int = 3600,
) -> PullAnalysis | None:
    """Run the query; returns None on any failure so callers fall back to REST."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        data = http.post_json(
            f"{api_url.rstrip('/')}/graphql",
            {"query": QUERY, "variables": {"owner": owner, "name": repo}},
            headers=headers,
            ttl=ttl,
        )
    except HttpError:
        return None
    if not isinstance(data, dict) or (
        data.get("errors") and not (data.get("data") or {}).get("repository")
    ):
        return None
    return normalize(data)
