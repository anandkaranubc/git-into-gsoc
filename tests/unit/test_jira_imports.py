"""Issues imported from Jira: pull requests that name only the old key still count."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from git_into_gsoc.github.availability import imported_jira_key
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.models import Availability

JENKINS_BODY = (
    "<!-- ### Imported Jira references for easier searching -->\n"
    "<!-- [jira_issue_key=JENKINS-43785] -->\n<p>Using the pipeline plugin ...</p>"
)
APACHE_BODY = (
    '<details><summary><i>Originally reported by <a title="A" href="https://issues.apache.org/'
    'jira/secure/ViewProfile.jspa?name=a">a</a>, imported from: <a href="https://issues.apache'
    '.org/jira/browse/STORM-4020" target="_blank">Metrics endpoint</a></i></summary>'
)


def test_the_key_comes_from_an_importer_marker_only() -> None:
    assert imported_jira_key(JENKINS_BODY) == "JENKINS-43785"
    assert imported_jira_key(APACHE_BODY) == "STORM-4020"
    # Naming a key for context does not make an issue the imported copy of it.
    assert imported_jira_key("Related to JENKINS-123, see the old ticket.") is None
    assert imported_jira_key(None) is None


def _pr(number: int, title: str, state: str = "open", merged: bool = False) -> dict[str, Any]:
    return {
        "number": number,
        "html_url": f"https://github.com/acme/tap/pull/{number}",
        "title": title,
        "body": "",
        "state": "closed" if merged else state,
        "user": {"login": "dev"},
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
        "pull_request": {"merged_at": "2026-02-26T00:00:00Z" if merged else None},
    }


def _mock_issue(search: httpx.Response) -> respx.Route:
    issue = {
        "number": 164,
        "html_url": "https://github.com/acme/tap/issues/164",
        "state": "open",
        "assignees": [],
        "labels": [{"name": "good first issue"}],
        "body": JENKINS_BODY,
        "updated_at": "2026-10-20T00:00:00Z",
    }
    respx.get("https://api.github.com/repos/acme/tap/issues/164").mock(
        return_value=httpx.Response(200, json=issue)
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/tap/issues/164/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    return respx.get("https://api.github.com/search/issues").mock(return_value=search)


@respx.mock
def test_an_open_pr_naming_the_jira_key_marks_the_issue_taken() -> None:
    # A Jenkins plugin issue (2026-10-22) read "available" although open PR 1646 named
    # its Jira key; the PR never linked the GitHub issue.
    items = [_pr(1646, "JENKINS-43785 Add the pipeline symbol"), _pr(9, "JENKINS-437850 other")]
    search = _mock_issue(httpx.Response(200, json={"items": items}))
    _, found = GitHubClient().assess("acme/tap", 164)
    assert '"JENKINS-43785"' in search.calls[0].request.url.params["q"]
    assert found.availability == Availability.LIKELY_TAKEN
    assert [p.number for p in found.linked_prs] == [1646]  # not the near-miss key


@respx.mock
def test_a_merged_pr_naming_the_key_is_a_caveat() -> None:
    _mock_issue(httpx.Response(200, json={"items": [_pr(44, "Fixes JENKINS-43785", merged=True)]}))
    _, found = GitHubClient().assess("acme/tap", 164)
    assert found.availability == Availability.AVAILABLE
    assert "A merged PR references this issue; it may already be partly fixed" in found.caveats


@respx.mock
def test_a_failed_search_leaves_the_timeline_answer() -> None:
    _mock_issue(httpx.Response(422, json={"message": "Validation Failed"}))
    _, found = GitHubClient().assess("acme/tap", 164)
    assert found.availability == Availability.AVAILABLE
    assert found.linked_prs == []


@respx.mock
def test_the_issues_list_checks_the_key_too() -> None:
    issue = {
        "id": 1,
        "number": 164,
        "title": "Pipeline support",
        "html_url": "https://github.com/acme/tap/issues/164",
        "repository_url": "https://api.github.com/repos/acme/tap",
        "labels": [{"name": "good first issue"}],
        "state": "open",
        "assignees": [],
        "comments": 0,
        "updated_at": "2026-10-20T00:00:00Z",
        "body": JENKINS_BODY,
    }

    def search(request: httpx.Request) -> httpx.Response:
        if "is:pr" in request.url.params["q"]:
            return httpx.Response(200, json={"items": [_pr(1646, "JENKINS-43785 symbol")]})
        return httpx.Response(200, json={"items": [issue]})

    respx.get("https://api.github.com/search/issues").mock(side_effect=search)
    respx.get(url__regex=r"https://api\.github\.com/repos/acme/tap/issues/164/timeline.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    [found] = GitHubClient().find_beginner_issues(repo="acme/tap", max_results=1)
    assert found.availability == Availability.LIKELY_TAKEN
