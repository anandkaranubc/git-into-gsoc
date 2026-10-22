"""Issues on GitLab hosts, read through the public API (gitlab.gnome.org, gitlab.com)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from git_into_gsoc.errors import HttpError, NotFoundError
from git_into_gsoc.gitlab import gitlab_issue_status, parse_gitlab_issue

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


def test_an_unreadable_issue_says_what_to_do() -> None:
    with pytest.raises(NotFoundError) as failed:
        gitlab_issue_status(FakeHttp({}), "https://gitlab.gnome.org/GNOME/gitg/-/issues/494")  # type: ignore[arg-type]
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
    assert all(not h or "PRIVATE-TOKEN" not in h for h in http.headers)
    assert found["availability"] == "unknown"
    assert any("set GITLAB_TOKEN and GITLAB_HOST" in c for c in found["assessment"]["caveats"])
