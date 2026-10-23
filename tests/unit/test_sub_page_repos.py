"""An ideas index of project pages: the code is linked one level down, from each page.

UC OSPO's ideas page links only to its 22 project pages on its own site. `repos` and
`issues --org` searched just uccross and ucsc-ospo and found nothing, while the project
repositories (Scenic, drishti, the edulinq tools) were linked from those pages (a launch
audit, 2026-10-23).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc.cli import app
from git_into_gsoc.models import ProjectIdea
from git_into_gsoc.service import GSoCToolkit, _idea_repo, _sub_page_github_repos

runner = CliRunner()
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
# SymPy's ideas page in the fixture data stands in for an index of project pages.
SYMPY_RAW = "https://raw.githubusercontent.com/wiki/sympy/sympy/GSoC-Ideas.md"
SITE = "https://projects.example.org/gsoc"

INDEX = f"""# GSoC 2026 projects

Each project keeps its own page:

- [Alpha]({SITE}/alpha/)
- [Beta]({SITE}/beta/)
- [Gamma]({SITE}/gamma/)
"""


def _idea(title: str, *links: str) -> str:
    lines = [
        f"### {title}",
        "",
        f"- Description: {title} for the project, with tests and docs.",
        "- Mentor(s): Dana Example",
        "- Expected project size: 175h",
    ]
    lines += [f"- Link: {link}" for link in links]
    return "\n".join(lines) + "\n\n"


PAGES = {
    # A person's helper repository first, then the project's issue: the work is there.
    "alpha": "# Alpha\n\n"
    + _idea(
        "Faster parser",
        "https://github.com/someone/helper",
        "https://github.com/alpha-lab/alpha/issues/9",
    )
    + _idea("Better errors", "https://github.com/alpha-lab/alpha/issues/12"),
    # A pull request is an example to follow, not a project. (A page with one idea block
    # reads as no ideas, so each page has two.)
    "beta": "# Beta\n\n"
    + _idea(
        "Plugin loader",
        "https://github.com/beta-org/beta",
        "https://github.com/other-org/example/pull/3",
    )
    + _idea("Config files", "https://github.com/beta-org/beta/issues/4"),
    # The organization's own repository is searched in full already.
    "gamma": "# Gamma\n\n"
    + _idea("Docs site", "https://github.com/sympy/sympy/issues/1")
    + _idea("Search box", "https://github.com/sympy/sympy/issues/2"),
}


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


def _repo(request: httpx.Request) -> httpx.Response:
    owner, name = request.url.path.split("/")[2:4]
    return httpx.Response(
        200,
        json={
            "full_name": f"{owner}/{name}",
            "html_url": f"https://github.com/{owner}/{name}",
            "owner": {"type": "User" if owner == "someone" else "Organization"},
            "description": "a project",
            "language": "Python",
            "stargazers_count": 10,
            "pushed_at": datetime.now(UTC).isoformat(),
            "archived": False,
            "fork": False,
            "has_issues": True,
        },
    )


def _mock(api: respx.MockRouter) -> None:
    api.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
    api.get(f"{OFFICIAL}/2026/organizations/").mock(
        return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
    )
    api.get(f"{ARCHIVE}/organizations.json").mock(
        return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
    )
    api.get(f"{ARCHIVE}/2026.json").mock(return_value=httpx.Response(200, json=_archive_year(2026)))
    api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=INDEX))
    for name, page in PAGES.items():
        api.get(f"{SITE}/{name}/").mock(return_value=httpx.Response(200, text=page))
    api.get(url__regex=r"https://api\.github\.com/orgs/[\w.-]+/repos.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    api.get(url__regex=r"https://api\.github\.com/repos/[\w.-]+/[\w.-]+/pulls.*").mock(
        return_value=httpx.Response(200, json=[])
    )
    api.get(url__regex=r"https://api\.github\.com/repos/.*/git/trees/HEAD.*").mock(
        return_value=httpx.Response(404)
    )
    api.get(url__regex=r"https://api\.github\.com/repos/[\w.-]+/[\w.-]+$").mock(side_effect=_repo)
    api.get(url__regex=r"https://api\.github\.com/search/issues.*").mock(
        return_value=httpx.Response(200, json={"total_count": 0, "items": []})
    )


def test_each_project_page_gets_a_place_before_any_gets_a_second() -> None:
    ideas = [
        ProjectIdea(
            title="One",
            section="Lynx Grader",
            links=[
                "https://github.com/edulinq/autograder-web",
                "https://github.com/edulinq/autograder-server/issues/142",
                "https://github.com/edulinq/autograder-server/blob/main/api.json",
            ],
        ),
        ProjectIdea(
            title="Two",
            section="Scenic",
            links=[
                "https://github.com/BerkeleyLearnVerify/Scenic/issues/274",
                "https://github.com/BerkeleyLearnVerify/Scenic/issues/295",
            ],
        ),
        ProjectIdea(title="Three", section="Scenic", links=["https://github.com/tier4/AWSIM"]),
        ProjectIdea(
            title="Four",
            section="Peersky",
            links=["https://github.com/uccross/site", "https://github.com/x/y/pull/1"],
        ),
    ]
    assert _sub_page_github_repos(ideas, ["uccross"]) == [
        ("edulinq/autograder-server", "Lynx Grader"),
        ("BerkeleyLearnVerify/Scenic", "Scenic"),
        ("edulinq/autograder-web", "Lynx Grader"),
        ("tier4/AWSIM", "Scenic"),
    ]


def test_an_ideas_repository_is_the_one_whose_issue_it_links() -> None:
    assert (
        _idea_repo(
            [
                "https://github.com/akhileshthite/chrome-extension-fetch",
                "https://github.com/p2plabsxyz/peersky-browser/issues/42",
            ]
        )
        == "p2plabsxyz/peersky-browser"
    )
    assert _idea_repo(["https://github.com/x/y/pull/1", "https://example.org"]) is None
    assert _idea_repo([]) is None


def test_repos_lists_the_projects_linked_from_project_pages() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        data = GSoCToolkit().discover_repos("SymPy", limit=10)
    names = [r["full_name"] for r in data["repos"]]
    assert set(names) == {"alpha-lab/alpha", "beta-org/beta"}
    alpha = next(r for r in data["repos"] if r["full_name"] == "alpha-lab/alpha")
    assert "Linked from its Alpha project page" in alpha["reasons"]
    assert alpha["ideas_mention"]


def test_issues_org_searches_the_projects_linked_from_project_pages() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        owners, linked, note = GSoCToolkit()._gsoc_owners("SymPy", language=None)
    assert owners == ["sympy"]
    assert linked == ["alpha-lab", "beta-org"]
    assert (
        note == "Searching SymPy: sympy, and alpha-lab, beta-org (linked from its project pages)."
    )


def test_issues_labels_project_page_owners_as_the_note_does(monkeypatch: Any) -> None:
    # The note said "linked from its project pages" and every issue said "named on the
    # SymPy ideas page" (a post-merge audit, 2026-10-23).
    seen: dict[str, Any] = {}

    def search(**kwargs: Any) -> list[Any]:
        seen.update(kwargs)
        return []

    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        toolkit = GSoCToolkit()
        monkeypatch.setattr(toolkit.github, "find_beginner_issues", search)
        toolkit.find_issues(org="SymPy")
    assert seen["org_names"]["alpha-lab"] == "linked from the SymPy project pages"
    assert seen["org_names"]["sympy"] == "SymPy"


def test_ideas_says_which_repository_each_idea_links_to() -> None:
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        data = GSoCToolkit().org_ideas("SymPy")
        shown = runner.invoke(app, ["ideas", "SymPy"], env={"COLUMNS": "160"})
    repos = {i["title"]: i["repo"] for i in data["ideas"]}
    assert repos == {
        "Faster parser": "alpha-lab/alpha",
        "Better errors": "alpha-lab/alpha",
        "Plugin loader": "beta-org/beta",
        "Config files": "beta-org/beta",
        "Docs site": "sympy/sympy",
        "Search box": "sympy/sympy",
    }
    assert data["repos_linked"]
    assert "git-into-gsoc repo owner/name --track" in data["next_step"]
    assert shown.exit_code == 0, shown.output
    assert "links to alpha-lab/alpha" in shown.stdout


def test_ideas_that_all_link_one_repository_show_no_hint() -> None:
    page = "# Ideas\n\n" + _idea("Faster parser", "https://github.com/sympy/sympy/issues/9")
    page += _idea("Better errors", "https://github.com/sympy/sympy/issues/12")
    with respx.mock(assert_all_called=False) as api:
        _mock(api)
        api.get(SYMPY_RAW).mock(return_value=httpx.Response(200, text=page))
        data = GSoCToolkit().org_ideas("SymPy")
        shown = runner.invoke(app, ["ideas", "SymPy"], env={"COLUMNS": "160"})
    assert not data["repos_linked"]
    assert "--track" not in data["next_step"]
    assert "links to" not in shown.stdout


def test_pages_that_mostly_link_the_organizations_own_code_add_nothing() -> None:
    # MetaBrainz: its pages link metabrainz repositories; tesseract is a tool an idea uses.
    own = [f"https://github.com/metabrainz/{name}" for name in ("mb-solr", "artwork-indexer")]
    ideas = [
        ProjectIdea(title="Search", section="MusicBrainz", links=own),
        ProjectIdea(
            title="Cover art", section="MusicBrainz", links=["https://github.com/tesseract-ocr/x"]
        ),
    ]
    assert _sub_page_github_repos(ideas, ["metabrainz"]) == []


def test_without_a_token_it_reads_fewer_repositories(monkeypatch: Any) -> None:
    # One read per repository; without a token GitHub allows 60 an hour.
    from git_into_gsoc.models import IdeasDocument

    ideas = [
        ProjectIdea(title=f"Idea {n}", section=f"Project {n}", links=[f"https://github.com/o{n}/r"])
        for n in range(7)
    ]
    doc = IdeasDocument(source_url=SYMPY_RAW, fetched_url=SYMPY_RAW, layout="index", ideas=ideas)

    def found(toolkit: GSoCToolkit) -> int:
        toolkit.read_ideas_page = lambda url, **_: (doc, [{"title": "x", "url": SITE}])  # type: ignore[method-assign]
        with respx.mock(assert_all_called=False) as api:
            api.get(url__regex=r"https://api\.github\.com/repos/[\w.-]+/[\w.-]+$").mock(
                side_effect=_repo
            )
            return len(toolkit._sub_page_repos(SYMPY_RAW, ["sympy"], language=None))

    assert found(GSoCToolkit()) == 5
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    assert found(GSoCToolkit()) == 7


def test_githubs_own_pages_are_not_a_projects_repository() -> None:
    # A post-merge audit (2026-10-23): one pasted image made a one-project page look like
    # several, and the next step could name "user-attachments/assets".
    links = [
        "https://github.com/user-attachments/assets/1a2b",
        "https://github.com/sponsors/someone",
        "https://github.com/sympy/sympy",
    ]
    assert _idea_repo(links) == "sympy/sympy"
    assert _idea_repo(links[:2]) is None
