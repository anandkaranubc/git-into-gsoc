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
    gitlab_ci_as_workflow,
    gitlab_ci_environment,
    gitlab_issue_pointers,
    gitlab_issue_status,
    gitlab_orientation,
    gitlab_repo_health,
    gitlab_repo_leads,
    gitlab_target,
    parse_gitlab_issue,
    parse_gitlab_project,
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


# Ranking a group's projects, as `repos` does for GNOME or GNU Mailman.

GNOME_PROJECTS = "https://gitlab.gnome.org/api/v4/groups/GNOME/projects"


def _project(path: str, *, stars: int = 10, days: int = 3, **extra: Any) -> dict[str, Any]:
    return {
        "name": path.rsplit("/", 1)[1],
        "path_with_namespace": path,
        "web_url": f"https://gitlab.gnome.org/{path}",
        "description": f"{path} does things",
        "star_count": stars,
        "last_activity_at": _iso(days),
        "archived": False,
        **extra,
    }


def test_group_projects_are_ranked_and_the_top_get_a_language() -> None:
    projects = [
        _project("GNOME/gtk", stars=300),
        _project("GNOME/gimp", stars=305, days=200),
        _project("GNOME/old-thing", archived=True),
        _project("GNOME/gtk-fork", forked_from_project={"id": 1}),
        _project("GNOME/gnome-shell", stars=50, description="The desktop shell, in JavaScript"),
    ]
    api = "https://gitlab.gnome.org/api/v4/projects"
    http = FakeGitLab(
        {
            (GNOME_PROJECTS, None): projects,
            (f"{api}/GNOME%2Fgtk/languages", None): {"C": 95.0, "Python": 5.0},
            (f"{api}/GNOME%2Fgnome-shell/languages", None): {"JavaScript": 80.0, "C": 20.0},
        }
    )
    leads = gitlab_repo_leads(
        http,  # type: ignore[arg-type]
        "gitlab.gnome.org",
        "GNOME",
        ideas="Ideas: https://gitlab.gnome.org/GNOME/gnome-shell notifications, https://gitlab.gnome.org/GNOME/gtk-vnc",
        language="javascript",
        person=None,
        limit=2,
    )
    names = [lead.full_name for lead in leads]
    assert names == ["gitlab.gnome.org/GNOME/gnome-shell", "gitlab.gnome.org/GNOME/gtk"]
    shell = leads[0]
    assert shell.ideas_mention and shell.language == "JavaScript"
    assert "Named on the GSoC ideas page" in shell.reasons
    assert not leads[1].ideas_mention  # gtk is not gtk-vnc
    assert any(r.startswith("Active in the last") for r in shell.reasons)
    assert not any("Pushed" in r for r in shell.reasons)
    assert not any(n.endswith(("/old-thing", "/gtk-fork")) for n in names)


def test_a_project_path_gives_that_one_project() -> None:
    api = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgimp"
    http = FakeGitLab(
        {
            (api, None): _project("GNOME/gimp", stars=305),
            (f"{api}/languages", None): {"C": 94.0},
        }
    )
    leads = gitlab_repo_leads(
        http,  # type: ignore[arg-type]
        "gitlab.gnome.org",
        "GNOME/gimp",
        ideas="",
        language=None,
        person=None,
        limit=10,
    )
    assert [lead.full_name for lead in leads] == ["gitlab.gnome.org/GNOME/gimp"]
    assert leads[0].language == "C" and leads[0].stars == 305
    assert http.asked[0][0] == "https://gitlab.gnome.org/api/v4/groups/GNOME%2Fgimp/projects"


# Grading a project, as `repo` does for a GitLab link.

GITG_API = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg"


class FakeProject:
    """Answers by URL and the parameters that tell two reads of one URL apart."""

    KEYS = ("labels", "state", "assignee_id", "path", "page")

    def __init__(self, routes: dict[str, Any], texts: dict[str, str] | None = None) -> None:
        self.routes, self.texts = routes, texts or {}

    @classmethod
    def key(cls, url: str, **params: Any) -> str:
        tail = "&".join(f"{k}={params[k]}" for k in cls.KEYS if k in params)
        return f"{url}?{tail}" if tail else url

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        key = self.key(url, **(params or {}))
        if key not in self.routes:
            raise NotFoundError("HTTP 404", status_code=404, url=url)
        return self.routes[key]

    def get_text(self, url: str, **kwargs: Any) -> str:
        if url not in self.texts:
            raise NotFoundError("HTTP 404", status_code=404, url=url)
        return self.texts[url]


def _merge_request(iid: int, author: str, *, merged: bool, days: int) -> dict[str, Any]:
    return {
        "iid": iid,
        "author": {"username": author},
        "merge_user": {"username": "maintainer"} if merged else None,
        "created_at": _iso(days + 2),
        "merged_at": _iso(days) if merged else None,
        "closed_at": None if merged else _iso(days),
    }


def test_project_links_are_recognised() -> None:
    assert parse_gitlab_project("https://gitlab.gnome.org/GNOME/gitg") == (
        "gitlab.gnome.org",
        "GNOME/gitg",
    )
    assert parse_gitlab_project("gitlab.gnome.org/GNOME/gitg/-/issues/494") == (
        "gitlab.gnome.org",
        "GNOME/gitg",
    )
    assert parse_gitlab_project("https://gitlab.com/qemu-project/qemu.git") == (
        "gitlab.com",
        "qemu-project/qemu",
    )
    assert parse_gitlab_project("sympy/sympy") is None
    assert parse_gitlab_project("https://github.com/sympy/sympy") is None
    assert parse_gitlab_project("https://gitlab.com/mailman") is None  # a group, not a project


def test_a_gitlab_project_is_graded_from_its_merge_requests_and_tree() -> None:
    k = FakeProject.key
    tree = [
        {"name": n, "type": "blob"}
        for n in ("CONTRIBUTING.md", "README.md", ".gitlab-ci.yml", "meson.build", "COPYING")
    ]
    tree.append({"name": ".gitlab", "type": "tree"})
    merged = [_merge_request(i, f"outsider{i}", merged=True, days=i) for i in range(1, 4)]
    merged.append(_merge_request(9, "maintainer", merged=True, days=1))
    closed = [_merge_request(5, "outsider5", merged=False, days=5)]
    http = FakeProject(
        {
            k(GITG_API): {
                "path_with_namespace": "GNOME/gitg",
                "web_url": "https://gitlab.gnome.org/GNOME/gitg",
                "default_branch": "master",
                "description": "A git client",
                "star_count": 61,
                "forks_count": 97,
                "last_activity_at": _iso(1),
                "license": {"key": "gpl-2.0+", "name": "GNU General Public License v2.0 or later"},
                "topics": ["git"],
            },
            k(f"{GITG_API}/repository/tree"): tree,
            k(f"{GITG_API}/repository/tree", path=".gitlab"): [
                {"name": "issue_templates", "type": "tree"}
            ],
            k(f"{GITG_API}/users"): [{"username": "maintainer"}, {"username": "root"}],
            k(f"{GITG_API}/merge_requests", state="merged"): merged,
            k(f"{GITG_API}/merge_requests", state="closed"): closed,
            k(f"{GITG_API}/languages"): {"Vala": 80.0, "C": 20.0},
            k(f"{GITG_API}/issues_statistics", labels="4. Newcomers"): {
                "statistics": {"counts": {"all": 20, "opened": 5, "closed": 15}}
            },
            k(f"{GITG_API}/issues_statistics", labels="4. Newcomers", assignee_id="Any"): {
                "statistics": {"counts": {"all": 6, "opened": 2, "closed": 4}}
            },
        },
        texts={
            f"{GITG_API}/repository/files/CONTRIBUTING.md/raw": "# Contributing\n\nAsk on Matrix in #gitg first.\n"
        },
    )
    health, guide = gitlab_repo_health(http, "gitlab.gnome.org", "GNOME/gitg")  # type: ignore[arg-type]
    assert health.full_name == "gitlab.gnome.org/GNOME/gitg" and health.pr_source == "gitlab"
    assert health.has_contributing and health.contributing_source == "file"
    assert health.has_ci and health.has_issue_template and not health.has_pr_template
    assert not health.has_code_of_conduct
    assert health.license == "GNU General Public License v2.0 or later"
    assert health.language == "Vala" and health.topics == ["git"]
    assert health.insiders_known and health.prs_sampled == 5
    assert health.outsider_prs_sampled == 4 and health.outsider_merge_rate == 0.75
    assert health.outside_authors_merged == 3
    assert health.beginner_label == "4. Newcomers"
    assert (health.open_beginner_issues, health.assigned_beginner_issues) == (5, 2)
    assert health.unread == [] and health.grade in "ABCDEF" and health.health_score > 0
    assert any("3 different outside author" in s for s in health.signals)
    assert (
        guide.contributing_url
        == "https://gitlab.gnome.org/GNOME/gitg/-/blob/master/CONTRIBUTING.md"
    )
    assert "Matrix" in guide.communication_channels
    assert guide.beginner_issue_labels == ["4. Newcomers"]
    assert any("meson" in hint.lower() or "Build" in hint for hint in guide.setup_hints)


def test_a_project_without_a_known_label_or_members_still_grades() -> None:
    k = FakeProject.key
    merged = [_merge_request(1, "someone", merged=True, days=3)]
    http = FakeProject(
        {
            k(GITG_API): {"path_with_namespace": "a/b", "web_url": "https://gitlab.com/a/b"},
            k(f"{GITG_API}/repository/tree"): [{"name": "README.md", "type": "blob"}],
            k(f"{GITG_API}/merge_requests", state="merged"): merged,
        },
        texts={f"{GITG_API}/repository/files/README.md/raw": "# b\n\nSmall tool.\n"},
    )
    health, guide = gitlab_repo_health(http, "gitlab.gnome.org", "GNOME/gitg")  # type: ignore[arg-type]
    # The person who merged is the one known insider, so the author counts as outside.
    assert health.outsider_prs_sampled == 1 and health.outside_authors_merged == 1
    assert health.beginner_label is None and health.open_beginner_issues is None
    assert any(p.signal == "Open beginner issues" and p.why for p in health.points)
    assert not health.has_contributing and guide.contributing_url is None
    assert guide.setup_hints == ["Read README.md before coding"]


def test_a_missing_project_raises_with_a_hint() -> None:
    with pytest.raises(NotFoundError) as caught:
        gitlab_repo_health(FakeProject({}), "codeberg.org", "a/b")  # type: ignore[arg-type]
    assert "another server" in (caught.value.hint or "")


# Orientation, as `orient` does for a GitLab link.

GITLAB_CI = """\
image: python:3.12-slim

services:
  - postgres:15
  - name: redis:7

test:
  before_script:
    - pip install -e .[dev]
  script:
    - ruff check src
    - pytest -q tests

lint:
  script: ruff format --check src
"""


def test_gitlab_ci_scripts_read_as_run_blocks() -> None:
    converted = gitlab_ci_as_workflow(GITLAB_CI)
    assert "  run: |\n    pip install -e .[dev]\n" in converted
    assert "  run: |\n    ruff check src\n    pytest -q tests\n" in converted
    assert "  run: ruff format --check src" in converted
    from git_into_gsoc.github.orientation import ci_test_commands

    commands = [c["command"] for c in ci_test_commands({".gitlab-ci.yml": converted})]
    assert "pytest -q tests" in commands


def test_gitlab_ci_lists_at_the_keys_indent_and_block_items_keep_their_commands() -> None:
    # The two inputs from the review of this change (2026-11-01).
    same_indent = gitlab_ci_as_workflow(
        "test:\n  script:\n  - pytest\n  - ruff check\n  tags:\n  - docker\n"
    )
    assert same_indent == "test:\n  run: |\n    pytest\n    ruff check\n  tags:\n  - docker"
    block = gitlab_ci_as_workflow("test:\n  script:\n    - |\n      pip install .\n      pytest\n")
    assert block == "test:\n  run: |\n      pip install .\n      pytest"
    from git_into_gsoc.github.orientation import ci_test_commands

    commands = [c["command"] for c in ci_test_commands({".gitlab-ci.yml": same_indent + block})]
    assert "pytest" in commands and "docker" not in commands


def test_gitlab_ci_images_and_services_make_the_environment() -> None:
    env = gitlab_ci_environment(GITLAB_CI)
    assert env["runtimes"] == [
        {"name": "Python", "versions": ["3.12"], "most_used": "3.12", "source": ".gitlab-ci.yml"}
    ]
    assert [s["image"] for s in env["services"]] == ["postgres:15", "redis:7"]
    assert env["runners"] == []


def test_orientation_is_built_from_the_project_api() -> None:
    k = FakeProject.key
    tree = [
        {
            "path": p,
            "type": "tree" if "." not in p.rsplit("/", 1)[-1] else "blob",
            "name": p.rsplit("/", 1)[-1],
        }
        for p in (
            "README.md",
            "CONTRIBUTING.md",
            ".gitlab-ci.yml",
            "meson.build",
            "pyproject.toml",
            ".gitlab",
            ".gitlab/merge_request_templates",
            ".gitlab/merge_request_templates/Default.md",
            "gitg",
            "gitg/gitg.vala",
            "gitg/main.vala",
            "tests",
            "tests/test_core.py",
        )
    ]
    merged = [
        {"iid": i, "merged_at": _iso(i), "target_branch": "gtk4", "author": {"username": f"p{i}"}}
        for i in range(1, 5)
    ] + [{"iid": 9, "merged_at": _iso(9), "target_branch": "master", "author": {"username": "p9"}}]
    http = FakeProject(
        {
            k(GITG_API): {
                "path_with_namespace": "GNOME/gitg",
                "web_url": "https://gitlab.gnome.org/GNOME/gitg",
                "default_branch": "master",
                "description": "A git client",
                "star_count": 61,
                "last_activity_at": _iso(1),
                "license": {"name": "GPL-2.0+"},
            },
            k(f"{GITG_API}/repository/tree"): [e for e in tree if "/" not in e["path"]],
            k(f"{GITG_API}/repository/tree", path=".gitlab"): [
                e for e in tree if e["path"].startswith(".gitlab/")
            ],
            k(f"{GITG_API}/repository/tree", path="gitg"): [
                e for e in tree if e["path"].startswith("gitg/")
            ],
            k(f"{GITG_API}/repository/tree", path="tests"): [
                e for e in tree if e["path"].startswith("tests/")
            ],
            k(f"{GITG_API}/languages"): {"Vala": 90.5, "Python": 9.5},
            k(f"{GITG_API}/repository/commits"): [
                {
                    "message": "Fix dialog\n\nSigned-off-by: Ada <ada@example.org>",
                    "author_name": "Ada",
                },
                {"message": "Update translation", "author_name": "Translator"},
            ],
            k(f"{GITG_API}/merge_requests", state="merged"): merged,
            k(f"{GITG_API}/repository/branches/master"): {"commit": {"id": "abc123"}},
            k(f"{GITG_API}/protected_branches"): [
                {
                    "name": "master",
                    "push_access_levels": [{"access_level_description": "Maintainers"}],
                }
            ],
        },
        texts={
            f"{GITG_API}/repository/files/CONTRIBUTING.md/raw": "# Contributing\n\nAsk on Matrix first.\n",
            f"{GITG_API}/repository/files/.gitlab-ci.yml/raw": GITLAB_CI,
            f"{GITG_API}/repository/files/pyproject.toml/raw": "[project]\nname = 'gitg'\n",
            f"{GITG_API}/repository/files/.gitlab%2Fmerge_request_templates%2FDefault.md/raw": "- [ ] Tests added\n",
        },
    )
    data = gitlab_orientation(http, "gitlab.gnome.org", "GNOME/gitg", codetour=True)  # type: ignore[arg-type]
    assert data["repo"] == "gitlab.gnome.org/GNOME/gitg" and data["as_of_commit"] == "abc123"
    assert data["languages"][0] == {"name": "Vala", "share": 90}
    assert {d["path"] for d in data["code_map"]} >= {"gitg", "tests"}
    assert data["docs"]["contributing"] == "CONTRIBUTING.md" and data["docs"]["test_dirs"] == [
        "tests"
    ]
    assert [c["command"] for c in data["test_commands"]] == ["pytest -q tests"]
    assert data["ci_environment"]["runtimes"][0]["name"] == "Python"
    assert data["work_branch"]["branch"] == "gtk4" and data["work_branch"]["merged"] == 4
    assert data["conventions"]["gates"][0]["source"] == "protected branches"
    assert "Maintainers" in data["conventions"]["gates"][0]["gate"]
    assert data["maintainers"]["active_committers_90d"][0]["login"] in {"Ada", "Translator"}
    assert data["maintainers"]["commits_90d"] == 2
    assert "Matrix" in data["channels"] and data["example_pr"] is None
    assert data["reading_plan"][0]["path"] == "README.md"
    assert not data["tree_truncated"] and "codetour" in data
    assert "GitLab" in data["note"]


# Pointers for an issue, as `pointers` does for a GitLab link.


def test_pointers_resolve_paths_and_find_the_closing_merge_request() -> None:
    k = FakeProject.key
    tree_top = [
        {"path": "README.md", "type": "blob", "name": "README.md"},
        {"path": "gitg", "type": "tree", "name": "gitg"},
    ]
    tree_gitg = [
        {"path": "gitg/window.py", "type": "blob", "name": "window.py"},
        {"path": "gitg/dialog.py", "type": "blob", "name": "dialog.py"},
    ]
    closed = [
        {
            "iid": 300,
            "title": "Dialog loses its size",
            "closed_at": _iso(30),
            "web_url": "https://gitlab.gnome.org/GNOME/gitg/-/issues/300",
            "labels": ["4. Newcomers"],
        },
        {
            "iid": 301,
            "title": "Typo in README",
            "closed_at": _iso(60),
            "web_url": "https://gitlab.gnome.org/GNOME/gitg/-/issues/301",
            "labels": ["4. Newcomers"],
        },
    ]
    http = FakeProject(
        {
            k(GITG_API): {
                "id": 1550,
                "path_with_namespace": "GNOME/gitg",
                "default_branch": "master",
                "web_url": "https://gitlab.gnome.org/GNOME/gitg",
            },
            k(f"{GITG_API}/issues/494"): {
                "iid": 494,
                "title": "Dialog opens off screen",
                "description": "See `gitg/dialog.py` and the `GitgWindow` class.",
                "labels": ["4. Newcomers", "1. Bug"],
                "web_url": "https://gitlab.gnome.org/GNOME/gitg/-/issues/494",
            },
            k(f"{GITG_API}/repository/tree"): tree_top,
            k(f"{GITG_API}/repository/tree", path="gitg"): tree_gitg,
            k(f"{GITG_API}/issues", labels="4. Newcomers", state="closed"): closed,
            k(f"{GITG_API}/issues/300/closed_by"): [
                {
                    "iid": 77,
                    "merged_at": _iso(30),
                    "created_at": _iso(33),
                    "title": "Remember the dialog size",
                    "web_url": "https://gitlab.gnome.org/GNOME/gitg/-/merge_requests/77",
                    "author": {"username": "newcomer"},
                }
            ],
            k(f"{GITG_API}/issues/301/closed_by"): [],
            k(f"{GITG_API}/repository/branches/master"): {"commit": {"id": "abc123"}},
        }
    )
    data = gitlab_issue_pointers(http, "gitlab.gnome.org", "GNOME/gitg", 494)  # type: ignore[arg-type]
    assert (
        data["issue"]["repo"] == "gitlab.gnome.org/GNOME/gitg" and data["as_of_commit"] == "abc123"
    )
    assert data["files_likely_involved"][0]["path"] == "gitg/dialog.py"
    assert data["search_links"][0]["identifier"] == "GitgWindow"
    assert data["search_links"][0]["url"].startswith(
        "https://gitlab.gnome.org/search?project_id=1550"
    )
    assert "sign-in" in data["code_search_note"]
    assert data["similar_label"] == "4. Newcomers" and data["similar_shares_title_words"]
    fix = data["similar_fixes"][0]
    assert fix["issue"]["number"] == 300 and fix["pull_request"]["number"] == 77
    assert fix["pull_request"]["confidence"] == "closing MR" and fix["days_to_merge"] == 3
    assert fix["files"] == [] and data["fix_norm"] == {"sample": 0}
    assert "merge requests" in data["next_step"] and "GITLAB_TOKEN" in data["next_step"]


def test_pointers_for_a_missing_issue_raise_with_a_hint() -> None:
    k = FakeProject.key
    http = FakeProject({k(GITG_API): {"id": 1, "web_url": "https://gitlab.gnome.org/GNOME/gitg"}})
    with pytest.raises(NotFoundError) as caught:
        gitlab_issue_pointers(http, "gitlab.gnome.org", "GNOME/gitg", 1)  # type: ignore[arg-type]
    assert "merge request" in (caught.value.hint or "")
    with pytest.raises(NotFoundError) as other:
        gitlab_issue_pointers(FakeProject({}), "codeberg.org", "a/b", 1)  # type: ignore[arg-type]
    assert "another server" in (other.value.hint or "")
