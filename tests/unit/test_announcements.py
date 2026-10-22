"""Organization posts about a coming GSoC year, read from real titles and bodies."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.github.announcements import gsoc_posts


def _item(repo: str, number: int, title: str, body: str, role: str = "MEMBER") -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "state": "open",
        "created_at": "2026-10-07T16:25:51Z",
        "user": {"login": "maintainer"},
        "author_association": role,
    }


# Shortened from the real posts (2026-10-21).
WAGTAIL = _item(
    "wagtail/wagtail",
    14705,
    "No GSoC on Wagtail core in 2027",
    "we've decided we won\u2019t take part in GSoC 2027 with Wagtail core. If you're contributing "
    "with the view to take part in Google Summer of Code with us, please consider other projects.",
)
NOMINATIM = _item(
    "osm-search/Nominatim",
    4225,
    "Interested in GSOC 2027? Read this first.",
    "We have **not yet decided** if Nominatim will take part at Google Summer of Code 2027.",
)
OPPIA = _item(
    "oppia/oppia",
    27409,
    "GSoC 2027 Preparation 🚀",
    "GSoC 2027 is approaching! This tracker lists meaningful, well-scoped issues. "
    "Contributing to these issues does not guarantee GSoC selection.",
)
APPLICANT = _item(
    "oppia/oppia",
    27500,
    "Can I do GSoC 2027 here? I will not take part in anything else",
    "Please assign me.",
    role="NONE",
)
NUMBER_ONLY = _item("sympy/sympy", 2027, "Implement log method", "No GSoC here", role="CONTRIBUTOR")


def test_posts_are_classified_from_the_maintainers_own_words() -> None:
    posts = {p["repo"]: p for p in gsoc_posts([OPPIA, NOMINATIM, WAGTAIL], year=2027)}
    assert posts["wagtail/wagtail"]["status"] == "not_taking_part"
    assert posts["osm-search/Nominatim"]["status"] == "undecided"
    assert posts["oppia/oppia"]["status"] == "mentions"
    assert all(p["by_maintainer"] for p in posts.values())


def test_not_taking_part_comes_first() -> None:
    posts = gsoc_posts([OPPIA, NOMINATIM, WAGTAIL], year=2027)
    assert posts[0]["number"] == 14705


def test_applicants_cannot_announce_for_an_org_and_numbers_are_not_years() -> None:
    posts = gsoc_posts([APPLICANT, NUMBER_ONLY], year=2027)
    assert [p["number"] for p in posts] == [27500]
    assert posts[0]["status"] == "mentions"  # "will not take part" from a non-maintainer
    assert posts[0]["by_maintainer"] is False


def test_pull_requests_and_other_years_are_ignored() -> None:
    pr = {**OPPIA, "pull_request": {"url": "x"}}
    old = _item("oppia/oppia", 1, "GSoC 2026 Preparation", "")
    assert gsoc_posts([pr, old], year=2027) == []


def test_next_puts_an_org_that_is_sitting_out_first(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.models import OrgSummary
    from git_into_gsoc.progress.store import ProgressStore
    from git_into_gsoc.service import GSoCToolkit

    ProgressStore().set_profile(technologies=["python"])
    ProgressStore().shortlist_org("Wagtail")
    ProgressStore().shortlist_org("SymPy")
    toolkit = GSoCToolkit()
    orgs = {
        "Wagtail": OrgSummary(name="Wagtail", github_orgs=["wagtail"]),
        "SymPy": OrgSummary(name="SymPy", github_orgs=["sympy"]),
    }
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: orgs[name])
    monkeypatch.setattr(toolkit.github, "search_issues", lambda *a, **k: [WAGTAIL])
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner: [])
    monkeypatch.setattr(toolkit.official, "program", lambda *a, **k: None)
    monkeypatch.setattr(toolkit, "_new_beginner_issues", lambda *a, **k: [])
    data = toolkit.next_steps(year=2027)
    assert data["org_posts"][0]["org"] == "Wagtail"
    assert data["actions"][0]["title"].startswith("Wagtail says it will not take part in GSoC 2027")
    assert data["actions"][0]["why"].endswith("/14705")
    repo_step = next(a for a in data["actions"] if a["title"].startswith("Pick the repository"))
    assert repo_step["title"].endswith("SymPy")  # planning moves on to an org taking part


def test_org_details_survive_a_failed_post_search(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.errors import HttpError
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()

    def down(*a: object, **k: object) -> list[dict[str, Any]]:
        raise HttpError("HTTP 503 from api.github.com", status_code=503)

    monkeypatch.setattr(toolkit.github, "search_issues", down)
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner: [])
    found = toolkit.gsoc_posts_for(["wagtail"], year=2027)
    assert found["posts"] == [] and "503" in found["error"]["error"]


def test_a_hand_typed_shortlist_name_is_still_moved_aside(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.models import OrgSummary
    from git_into_gsoc.progress.store import ProgressStore
    from git_into_gsoc.service import GSoCToolkit

    ProgressStore().set_profile(technologies=["python"])
    ProgressStore().shortlist_org("wagtail")  # typed by hand, not the official name
    ProgressStore().shortlist_org("SymPy")
    toolkit = GSoCToolkit()
    orgs = {
        "wagtail": OrgSummary(name="Wagtail", github_orgs=["wagtail"]),
        "SymPy": OrgSummary(name="SymPy", github_orgs=["sympy"]),
    }
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: orgs[name])
    monkeypatch.setattr(toolkit.github, "search_issues", lambda *a, **k: [WAGTAIL])
    monkeypatch.setattr(toolkit.github, "list_owner_repos", lambda owner: [])
    monkeypatch.setattr(toolkit.official, "program", lambda *a, **k: None)
    monkeypatch.setattr(toolkit, "_new_beginner_issues", lambda *a, **k: [])
    data = toolkit.next_steps(year=2027)
    repo_step = next(a for a in data["actions"] if a["title"].startswith("Pick the repository"))
    assert repo_step["title"].endswith("SymPy")


LU_WIKI = """# Welcome

We have made the decision to not be involved with Google Summer of Code for the 2027 session. If anything changes, we will announce it here.

## I want to get involved!
We took part in GSoC 2026 and loved it.
"""


def test_a_wiki_statement_about_the_year_counts() -> None:
    # Learning Unlimited said this on its wiki home page (2026-10-21), never in an issue,
    # and the tool still ranked it second for a GSoC 2027 beginner.
    from git_into_gsoc.github.announcements import wiki_post

    post = wiki_post(LU_WIKI, year=2027, repo="learning-unlimited/ESP-Website")
    assert post is not None and post["status"] == "not_taking_part"
    assert post["source"] == "wiki" and post["by_maintainer"] is False
    assert post["url"] == "https://github.com/learning-unlimited/ESP-Website/wiki"
    assert wiki_post(LU_WIKI, year=2026, repo="x/y") is None  # "took part" is not news
    assert wiki_post("GSoC 2027 ideas are below.", year=2027, repo="x/y") is None


def test_wiki_pages_are_read_for_the_biggest_repositories(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.errors import HttpError
    from git_into_gsoc.github.client import GitHubClient

    client = GitHubClient()
    repos = [
        {"full_name": "learning-unlimited/ESP-Website", "has_wiki": True, "stargazers_count": 400},
        {"full_name": "learning-unlimited/old", "has_wiki": True, "archived": True},
        {"full_name": "learning-unlimited/tiny", "has_wiki": True, "stargazers_count": 1},
    ]
    monkeypatch.setattr(client, "list_owner_repos", lambda owner: repos)
    fetched: list[str] = []

    def text(url: str, **kw: object) -> str:
        fetched.append(url)
        if "ESP-Website" in url:
            return LU_WIKI
        raise HttpError("HTTP 404", status_code=404)

    monkeypatch.setattr(client.http, "get_text", text)
    monkeypatch.setattr(client, "search_issues", lambda *a, **k: [])
    posts = client.gsoc_year_posts(["learning-unlimited"], 2027)
    assert [p["status"] for p in posts] == ["not_taking_part"]
    assert len(fetched) == 2 and not any("/old/" in url for url in fetched)


def _lu_toolkit(monkeypatch):  # type: ignore[no-untyped-def]
    from git_into_gsoc.errors import HttpError
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()

    def limited(*a: object, **k: object) -> list[dict[str, Any]]:
        raise HttpError("GitHub API secondary rate limit exceeded", status_code=403)

    monkeypatch.setattr(toolkit.github, "search_issues", limited)
    monkeypatch.setattr(
        toolkit.github,
        "list_owner_repos",
        lambda owner: [{"full_name": "learning-unlimited/ESP-Website", "has_wiki": True}],
    )
    monkeypatch.setattr(toolkit.github.http, "get_text", lambda url, **kw: LU_WIKI)
    return toolkit


def test_a_search_limit_still_reads_the_wiki_statement(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A post-release check hit GitHub's search limit, and `org "Learning Unlimited"`
    # lost the wiki's "not be involved ... for the 2027 session" with the search,
    # though reading a wiki takes no search.
    from git_into_gsoc.service import participation_from

    found = _lu_toolkit(monkeypatch).gsoc_posts_for(["learning-unlimited"], year=2027)
    assert "rate limit" in found["error"]["error"]
    assert [(p["source"], p["status"]) for p in found["posts"]] == [("wiki", "not_taking_part")]
    assert participation_from(found)["status"] == "not_taking_part"
    # With the search down and nothing on the wiki, the answer stays unknown.
    assert participation_from({"posts": [], "error": found["error"]}) == {"status": "unknown"}
    mention = {**found["posts"][0], "status": "mentions"}
    assert participation_from({"posts": [mention], "error": found["error"]}) == {
        "status": "unknown"
    }


def test_org_says_when_it_could_not_search_for_posts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from git_into_gsoc import cli

    found = _lu_toolkit(monkeypatch).gsoc_posts_for(["learning-unlimited"], year=2027)
    details = {
        "found": True,
        "catalog": {"year": 2026},
        "organization": {
            "name": "Learning Unlimited",
            "description": "Building excitement for teaching and learning",
            "official": True,
            "years_active": [2026],
            "projects_by_year": {2026: 3},
        },
        "gsoc_posts": found,
    }

    class Fake:
        def org_details(self, *a, **k):  # type: ignore[no-untyped-def]
            return details

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = CliRunner().invoke(cli.app, ["org", "LU"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    output = result.output
    assert "Could not search its issues for posts about GSoC 2027" in output
    assert "says it will not take part" in output
    details["gsoc_posts"] = {"year": 2027, "posts": [], "error": found["error"]}
    output = CliRunner().invoke(cli.app, ["org", "LU"], env={"COLUMNS": "200"}).output
    assert "Could not search its issues" in output and "secondary rate limit" in output


def test_org_shows_the_statement_the_monthly_check_found(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # SymPy's "we will not participate" is in an issue body, which only the monthly
    # check reads; `org` searched titles live and never showed it.
    from typer.testing import CliRunner

    from git_into_gsoc import cli, service
    from git_into_gsoc.models import OrgSummary
    from git_into_gsoc.service import GSoCToolkit

    said = {
        "status": "reported",
        "url": "https://github.com/sympy/sympy/issues/30671",
        "year": 2027,
        "checked": "2026-10-22",
        "date": "2026-10-04",
        "quote": "It's likely that as a result of this we will not participate in GSoC this year.",
        "by_maintainer": False,
    }
    monkeypatch.setattr(service, "signals_for", lambda slug: {"participation": said})
    toolkit = GSoCToolkit()
    toolkit.settings.target_year = 2027
    org = OrgSummary(name="SymPy", slug="sympy", github_orgs=["sympy"], official=True)
    monkeypatch.setattr(toolkit.gsoc, "get_organization", lambda name, **k: org)

    class Catalog:
        def model_dump(self) -> dict[str, Any]:
            return {"year": 2026}

    monkeypatch.setattr(toolkit.gsoc, "catalog", lambda year: (Catalog(), None))
    monkeypatch.setattr(
        toolkit,
        "gsoc_posts_for",
        lambda owners, **k: {"year": 2027, "posts": [], "error": {"error": "limit"}},
    )
    details = toolkit.org_details("SymPy")
    assert details["statement_on_file"] == said
    monkeypatch.setattr(cli, "_toolkit", lambda: toolkit)
    output = CliRunner().invoke(cli.app, ["org", "SymPy"], env={"COLUMNS": "250"}).output
    assert "Could not search its issues for posts about GSoC 2027" in output
    assert "The monthly check on 2026-10-22 found that someone wrote in its tracker on" in output
    assert "we will not participate" in output and "not the organization's own statement" in output

    # A live post with the same link is not repeated, and another year's statement is left out.
    live = {
        "year": 2027,
        "posts": [
            {
                "url": said["url"],
                "title": "x",
                "status": "mentions",
                "created_at": "2026-10-04",
                "state": "open",
                "by_maintainer": True,
            }
        ],
    }
    monkeypatch.setattr(toolkit, "gsoc_posts_for", lambda owners, **k: live)
    output = CliRunner().invoke(cli.app, ["org", "SymPy"], env={"COLUMNS": "250"}).output
    assert "monthly check" not in output
    monkeypatch.setattr(
        service, "signals_for", lambda slug: {"participation": {**said, "year": 2026}}
    )
    assert "statement_on_file" not in toolkit.org_details("SymPy")
