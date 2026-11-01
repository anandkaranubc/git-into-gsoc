"""Issues on GitLab hosts, read through the public API (gitlab.gnome.org, gitlab.com)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from git_into_gsoc.errors import HttpError, NotFoundError
from git_into_gsoc.gitlab import (
    GITLAB_BEGINNER_LABELS,
    gitlab_issue_status,
    gitlab_target,
    parse_gitlab_issue,
    search_gitlab_issues,
)
from git_into_gsoc.http_client import CachedHttpClient

API = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg/issues/494"


def _iso(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


class FakeHttp:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.asked: list[str] = []

    def get_json(self, url: str, **kwargs: Any) -> Any:
        self.asked.append(url)
        if url not in self.routes:
            raise HttpError("HTTP 404", status_code=404)
        return self.routes[url]


def _issue(**extra: Any) -> dict[str, Any]:
    return {
        "iid": 494,
        "title": "Change the application ID suffix",
        "state": "opened",
        "assignees": [],
        "labels": ["4. Newcomers"],
        "user_notes_count": 0,
        "updated_at": _iso(10),
        **extra,
    }


def _mr(iid: int, state: str, project: str = "GNOME/gitg") -> dict[str, Any]:
    return {
        "iid": iid,
        "state": state,
        "author": {"username": "someone"},
        "updated_at": _iso(210),
        "web_url": f"https://gitlab.gnome.org/{project}/-/merge_requests/{iid}",
    }


def test_the_short_reference_the_table_prints_is_an_issue() -> None:
    # `issues` prints GitLab results as host/path#N; `issue` must take that back.
    assert parse_gitlab_issue("gitlab.gnome.org/GNOME/gitg#494") == (
        "gitlab.gnome.org",
        "GNOME/gitg",
        494,
    )
    assert parse_gitlab_issue("gitlab.com/qemu-project/qemu#7") == (
        "gitlab.com",
        "qemu-project/qemu",
        7,
    )
    assert parse_gitlab_issue("sympy/sympy#23161") is None  # a GitHub reference, no host


def test_links_are_recognised() -> None:
    assert parse_gitlab_issue("https://gitlab.gnome.org/GNOME/gitg/-/issues/494") == (
        "gitlab.gnome.org",
        "GNOME/gitg",
        494,
    )
    assert parse_gitlab_issue("https://gitlab.com/nsnam/ns-3-dev/-/work_items/7")[2] == 7  # type: ignore[index]
    assert parse_gitlab_issue("https://github.com/a/b/-/issues/1") is None
    assert parse_gitlab_issue("https://github.com/a/b/issues/1") is None
    # Copied from the address bar without "https://".
    assert parse_gitlab_issue("gitlab.com/inkscape/inkscape/-/issues/6508") == (
        "gitlab.com",
        "inkscape/inkscape",
        6508,
    )
    assert parse_gitlab_issue("github.com/a/b/-/issues/1") is None


def test_an_open_merge_request_means_likely_taken() -> None:
    # gitg #494 (2026-10-21): the GNOME persona was sent to it; MR !330 was open.
    http = FakeHttp(
        {
            API: _issue(user_notes_count=3),
            f"{API}/related_merge_requests": [
                _mr(328, "closed"),
                _mr(330, "opened"),
                _mr(1326, "merged", project="GNOME/nautilus"),
            ],
        }
    )
    found = gitlab_issue_status(http, "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")  # type: ignore[arg-type]
    assert found["availability"] == "likely_taken"
    assert found["reason"].startswith("Open merge request !330 by @someone")
    assert [mr["number"] for mr in found["assessment"]["linked_prs"]] == [328, 330]
    assert any("cannot read the 3 comment(s)" in c for c in found["assessment"]["caveats"])


def test_comments_it_cannot_read_make_the_status_unknown() -> None:
    http = FakeHttp({API: _issue(user_notes_count=2), f"{API}/related_merge_requests": []})
    found = gitlab_issue_status(http, "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")  # type: ignore[arg-type]
    assert found["availability"] == "unknown" and "signed in" in found["reason"]
    quiet = FakeHttp({API: _issue(), f"{API}/related_merge_requests": []})
    assert (
        gitlab_issue_status(quiet, "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")[  # type: ignore[arg-type]
            "availability"
        ]
        == "available"
    )


@pytest.mark.parametrize(
    ("extra", "status"),
    [
        ({"state": "closed"}, "closed"),
        ({"assignees": [{"username": "sajal64"}]}, "assigned"),
        ({"labels": ["Needs Design"]}, "not_open"),
        # GitLab's scoped labels put a prefix before the status.
        ({"labels": ["Status::Needs Discussion"]}, "not_open"),
        ({"labels": ["workflow::blocked"]}, "not_open"),
        ({"labels": ["In Progress"]}, "claimed"),
        ({"updated_at": _iso(500)}, "stale"),
    ],
)
def test_other_statuses(extra: dict[str, Any], status: str) -> None:
    http = FakeHttp({API: _issue(**extra), f"{API}/related_merge_requests": []})
    found = gitlab_issue_status(http, "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")  # type: ignore[arg-type]
    assert found["availability"] == status


@pytest.mark.parametrize("routes", [{}, {API: []}])
def test_an_unreadable_issue_says_what_to_do(routes: dict[str, Any]) -> None:
    with pytest.raises(NotFoundError) as failed:
        gitlab_issue_status(FakeHttp(routes), "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")  # type: ignore[arg-type]
    assert failed.value.hint and "check for an assignee" in failed.value.hint


def test_the_issue_command_reads_gitlab_links(monkeypatch: Any) -> None:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    http = FakeHttp({API: _issue(), f"{API}/related_merge_requests": []})
    monkeypatch.setattr(toolkit, "http", http)
    data = toolkit.issue_status("https://gitlab.gnome.org/GNOME/gitg/-/issues/494")
    assert data["availability"] == "available" and data["before_you_comment"]
    assert data["repo"] == "gitlab.gnome.org/GNOME/gitg"


class RecordingHttp(FakeHttp):
    def __init__(self, routes: dict[str, Any]) -> None:
        super().__init__(routes)
        self.headers: list[dict[str, str] | None] = []

    def get_json(self, url: str, **kwargs: Any) -> Any:
        self.headers.append(kwargs.get("headers"))
        return super().get_json(url, **kwargs)


def _note(body: str, days_ago: int, *, system: bool = False) -> dict[str, Any]:
    return {
        "body": body,
        "author": {"username": "newcomer"},
        "created_at": _iso(days_ago),
        "system": system,
    }


def test_a_token_for_this_host_reads_claims_in_the_comments() -> None:
    http = RecordingHttp(
        {
            API: _issue(user_notes_count=2),
            f"{API}/related_merge_requests": [],
            f"{API}/notes": [
                _note("changed the description", 9, system=True),
                _note("I'd like to work on this issue, here is my plan", 5),
            ],
        }
    )
    found = gitlab_issue_status(  # type: ignore[arg-type]
        http,
        "https://gitlab.gnome.org/GNOME/gitg/-/issues/494",
        token="glpat-secret",
        token_host="gitlab.gnome.org",
    )
    assert found["availability"] == "claimed"
    assert found["assessment"]["claims"][0]["login"] == "newcomer"
    assert not any("cannot read" in c for c in found["assessment"]["caveats"])


def test_a_token_is_never_sent_to_another_host() -> None:
    http = RecordingHttp({API: _issue(user_notes_count=2), f"{API}/related_merge_requests": []})
    found = gitlab_issue_status(  # type: ignore[arg-type]
        http,
        "https://gitlab.gnome.org/GNOME/gitg/-/issues/494",
        token="glpat-for-gitlab-com",
        token_host="gitlab.com",
    )
    assert all(not h or "Authorization" not in h for h in http.headers)
    assert found["availability"] == "unknown"
    assert any("set GITLAB_TOKEN and GITLAB_HOST" in c for c in found["assessment"]["caveats"])


@respx.mock
def test_a_redirect_to_another_host_does_not_carry_the_token(tmp_path: Path) -> None:
    respx.get(API).mock(return_value=httpx.Response(200, json=_issue(user_notes_count=2)))
    respx.get(f"{API}/related_merge_requests").mock(return_value=httpx.Response(200, json=[]))
    notes = respx.get(f"{API}/notes").mock(
        return_value=httpx.Response(302, headers={"Location": "https://collect.example.net/n"})
    )
    other = respx.get("https://collect.example.net/n").mock(
        return_value=httpx.Response(200, json=[])
    )
    gitlab_issue_status(
        CachedHttpClient(cache_root=tmp_path / "http"),
        "https://gitlab.gnome.org/GNOME/gitg/-/issues/494",
        token="glpat-secret",
        token_host="gitlab.gnome.org",
    )
    assert any("glpat-secret" in v for v in notes.calls.last.request.headers.values())
    assert other.called
    assert not any("glpat-secret" in v for v in other.calls.last.request.headers.values())


# Searching a group or project, as `issues --org` does for GNOME, QEMU, or GNU Mailman.


GIMP = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgimp/issues"


class FakeGitLab:
    """Answers by (url, label) so a test can see which labels were asked for, in order."""

    def __init__(self, routes: dict[tuple[str, str | None], Any]) -> None:
        self.routes = routes
        self.asked: list[tuple[str, str | None]] = []

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        key = (url, (params or {}).get("labels"))
        self.asked.append(key)
        if key not in self.routes:
            raise NotFoundError("HTTP 404", status_code=404, url=url)
        return self.routes[key]


def _listed(iid: int, project: str = "GNOME/gimp", **extra: Any) -> dict[str, Any]:
    return {
        "id": 1000 + iid,
        "iid": iid,
        "title": f"Issue {iid}",
        "description": "Steps: open the dialog, click apply.",
        "state": "opened",
        "assignees": [],
        "author": {"username": "reporter"},
        "labels": ["4. Newcomers", "1. Bug"],
        "user_notes_count": 0,
        "created_at": _iso(40),
        "updated_at": _iso(5),
        "web_url": f"https://gitlab.gnome.org/{project}/-/work_items/{iid}",
        **extra,
    }


def test_the_code_link_says_where_to_search() -> None:
    assert gitlab_target("https://gitlab.gnome.org/") == ("gitlab.gnome.org", "GNOME")
    assert gitlab_target("https://gitlab.gnome.org/GNOME/gimp/") == (
        "gitlab.gnome.org",
        "GNOME/gimp",
    )
    assert gitlab_target("https://gitlab.com/qemu-project/qemu") == (
        "gitlab.com",
        "qemu-project/qemu",
    )
    assert gitlab_target("https://gitlab.com/mailman") == ("gitlab.com", "mailman")
    assert gitlab_target("https://invent.kde.org") is None  # bugs.kde.org holds KDE's bugs
    assert gitlab_target("https://github.com/sympy/sympy") is None
    assert gitlab_target(None) is None and gitlab_target("not a link") is None


def test_a_project_path_is_searched_when_it_is_not_a_group() -> None:
    mr_api = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgimp/issues"
    http = FakeGitLab(
        {
            (GIMP, "4. Newcomers"): [_listed(1), _listed(2, user_notes_count=3)],
            (GIMP, "easy"): [_listed(3, labels=["easy"])],
            (f"{mr_api}/1/related_merge_requests"): [_mr(7, "opened", project="GNOME/gimp")],
            (f"{mr_api}/3/related_merge_requests"): [],
        }
    )
    http.routes = {(k if isinstance(k, tuple) else (k, None)): v for k, v in http.routes.items()}
    found = search_gitlab_issues(
        http,  # type: ignore[arg-type]
        "gitlab.gnome.org",
        "GNOME/gimp",
        labels=GITLAB_BEGINNER_LABELS,
        max_results=5,
        org_name="GNU Image Manipulation Program",
    )
    # The group endpoint 404s for a project path, so the project one is used from then on.
    assert http.asked[0] == (
        "https://gitlab.gnome.org/api/v4/groups/GNOME%2Fgimp/issues",
        "4. Newcomers",
    )
    assert http.asked[1] == (GIMP, "4. Newcomers")
    assert all(url == GIMP for url, _ in http.asked[1:11])
    by_number = {c.number: c for c in found}
    assert set(by_number) == {1, 2, 3}
    assert by_number[1].availability.value == "likely_taken"  # the open merge request
    assert by_number[1].assessment and by_number[1].assessment.linked_prs[0].number == 7
    assert by_number[2].availability.value == "unknown"  # 3 comments nobody can read
    assert by_number[3].availability.value == "available"
    assert found[0].number == 3  # free first
    assert by_number[1].repo == "gitlab.gnome.org/GNOME/gimp"
    assert by_number[1].url == "https://gitlab.gnome.org/GNOME/gimp/-/issues/1"
    assert by_number[1].gsoc_org == "GNU Image Manipulation Program"
    assert by_number[1].beginner_score > 0 and by_number[1].signals


def test_a_host_that_is_not_gitlab_raises() -> None:
    http = FakeGitLab({})
    with pytest.raises(NotFoundError):
        search_gitlab_issues(
            http,  # type: ignore[arg-type]
            "cgit.freebsd.org",
            "src",
            labels=["good first issue"],
            max_results=5,
        )
    assert len(http.asked) == 2  # groups, then projects, then give up


def test_one_project_cannot_fill_the_list() -> None:
    group = "https://gitlab.gnome.org/api/v4/groups/GNOME/issues"
    page = [_listed(n) for n in range(1, 6)] + [_listed(9, project="GNOME/gitg")]
    routes: dict[tuple[str, str | None], Any] = {(group, "4. Newcomers"): page}
    for n in range(1, 10):
        for project in ("GNOME%2Fgimp", "GNOME%2Fgitg"):
            routes[
                (
                    f"https://gitlab.gnome.org/api/v4/projects/{project}/issues/{n}/related_merge_requests",
                    None,
                )
            ] = []
    found = search_gitlab_issues(
        FakeGitLab(routes),  # type: ignore[arg-type]
        "gitlab.gnome.org",
        "GNOME",
        labels=["4. Newcomers"],
        max_results=10,
    )
    assert sum(c.repo.endswith("/gimp") for c in found) == 3
    assert any(c.repo.endswith("/gitg") for c in found)
