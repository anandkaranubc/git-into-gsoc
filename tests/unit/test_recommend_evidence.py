"""recommend and orgs: evidence, program status, ideas that fit, and a path, on fixtures."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc import service
from git_into_gsoc.cli import app
from git_into_gsoc.errors import InputError
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.service import GSoCToolkit

OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"
SIGNALS = {
    "generated": "2026-10-21",
    "year": 2026,
    "organizations": {
        "openastronomy": {
            "ideas": {
                "url": "https://openastronomy.org/gsoc/",
                "count": 2,
                "difficulty": {"easy": 1, "medium": 1},
                "ideas": [
                    {
                        "t": "Faster FITS reader",
                        "d": "medium",
                        "s": "medium",
                        "k": ["python", "numpy", "astronomy"],
                    },
                    {"t": "Rust bindings", "d": "hard", "k": ["rust"]},
                ],
            }
        }
    },
}


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> respx.MockRouter:
    monkeypatch.setattr(service, "load_signals", lambda: SIGNALS)
    monkeypatch.setattr(
        service, "signals_for", lambda slug: dict(SIGNALS["organizations"].get(slug or "", {}))
    )
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": [], "total_count": 0})
        )
        router.get(url__regex=r"https://api\.github\.com/(orgs|users)/[^/]+/repos").mock(
            return_value=httpx.Response(200, json=[])
        )
        router.get(url__regex=r"https://api\.github\.com/repos/[^/]+/[^/]+$").mock(
            return_value=httpx.Response(200, json={"description": "", "archived": False})
        )
        yield router


def test_recommend_says_the_list_is_last_years_and_shows_evidence(api: respx.MockRouter) -> None:
    data = GSoCToolkit().recommend_path(
        technologies=["pyhton"], interests=["astronomy"], experience="new", hours_per_week=10
    )
    assert data["program"] == {
        "target_year": 2027,
        "list_year": 2026,
        "confirmed": False,
        "note": data["program"]["note"],
    }
    assert "has not announced the GSoC 2027 organizations" in data["program"]["note"]
    assert data["read_as"] == ["Read 'pyhton' as 'python'."]
    assert data["experience"] == {"level": "new", "from": "you said so"}
    top = data["recommended_orgs"][0]
    assert top["name"] == "OpenAstronomy" and top["fit"] == "strong"
    assert any("official GSoC listing" in line for line in top["evidence"])
    assert "match_score" in top  # kept for ordering, never shown as a chance
    group = data["ideas_that_fit"][0]
    assert group["org"] == "OpenAstronomy" and group["year"] == 2026
    assert "2027 ideas usually appear" in group["note"]
    assert group["ideas"][0]["title"] == "Faster FITS reader"
    assert group["ideas"][0]["you_have"] == ["Python"]
    assert group["ideas"][0]["you_would_learn"] == ["NumPy/SciPy"]
    steps = [s["step"] for s in data["learning_path"]]
    assert steps[0].startswith("Practise the pull request routine")
    assert "OpenAstronomy" in steps[1]


def test_recommend_moves_an_org_that_says_it_sits_out_and_skips_its_issues(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolkit = GSoCToolkit()

    def posts(owners: list[str], year: int) -> list[dict[str, Any]]:
        if "sympy" in owners:
            return [
                {
                    "status": "not_taking_part",
                    "url": "https://github.com/sympy/sympy/issues/1",
                    "title": "No GSoC 2027",
                    "by_maintainer": True,
                }
            ]
        return []

    from git_into_gsoc.models import Availability, IssueCandidate

    searched: list[list[str]] = []

    def search(**kwargs: Any) -> list[IssueCandidate]:
        searched.append(kwargs["orgs"])
        return [
            IssueCandidate(
                repo=f"{owner}/x",
                number=n,
                title="Fix docs",
                url=f"https://github.com/{owner}/x/issues/{n}",
                availability=Availability.AVAILABLE,
            )
            for n, owner in enumerate(kwargs["orgs"] or [], start=1)
        ]

    monkeypatch.setattr(toolkit.github, "gsoc_year_posts", posts)
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", search)
    data = toolkit.recommend_path(technologies=["python"], interests=["mathematics"])
    ranked = toolkit.match_orgs(technologies=["python"], topics=["mathematics"])
    assert ranked["organizations"][0]["name"] == "SymPy"  # first before the check
    names = [o["name"] for o in data["recommended_orgs"]]
    assert names[-1] == "SymPy"
    assert data["recommended_orgs"][-1]["caveats"][0].startswith(
        "Says it will not take part in GSoC 2027"
    )
    assert data["recommended_orgs"][-1]["participation"]["status"] == "not_taking_part"
    assert "sympy" not in searched[0]  # the scoped search skips it
    # The wider language search may reach it, but its issues are never shown.
    assert data["starter_issues"]
    assert all(not i["repo"].startswith("sympy/") for i in data["starter_issues"])


def test_recommend_rejects_an_unknown_experience_level(api: respx.MockRouter) -> None:
    with pytest.raises(InputError, match="Unknown experience level"):
        GSoCToolkit().recommend_path(technologies=["python"], experience="guru")


def test_orgs_explains_an_empty_search_for_an_earlier_years_org(api: respx.MockRouter) -> None:
    data = GSoCToolkit().match_orgs(query="3DTK")
    assert data["organizations"] == []
    assert "3DTK took part in GSoC in 2018, but it is not on the official 2026 list" in data["hint"]
    result = CliRunner().invoke(app, ["orgs", "-q", "3DTK"])
    assert "took part in GSoC in 2018" in " ".join(result.output.split())


def test_saved_experience_and_hours_shape_orgs(api: respx.MockRouter) -> None:
    ProgressStore().set_profile(
        technologies=["python"], interests=["astronomy"], experience="new", hours_per_week=6
    )
    data = GSoCToolkit().match_orgs()
    assert data["matched_on"]["experience"] == "new"
    assert data["matched_on"]["hours_per_week"] == 6
    assert data["matched_on"]["from_profile"] is True


def test_profile_reads_experience_from_merged_pull_requests(api: respx.MockRouter) -> None:
    api.get("https://api.github.com/users/octo").mock(
        return_value=httpx.Response(200, json={"login": "octo", "public_repos": 1})
    )
    api.get(url__regex=r"https://api\.github\.com/users/octo/repos").mock(
        return_value=httpx.Response(200, json=[{"language": "Python"}])
    )
    api.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [], "total_count": 3})
    )
    profile = GSoCToolkit().save_profile(github="octo")
    assert profile["merged_prs_elsewhere"] == 3
    assert profile["experience_inferred"] == {
        "level": "some",
        "from": "3 merged pull requests in other people's repositories on GitHub",
    }
    query = api.calls.last.request.url.params["q"]
    assert query == "is:pr is:merged author:octo -user:octo"
    stated = GSoCToolkit().save_profile(experience="experienced")
    assert stated["experience"] == "experienced" and "experience_inferred" not in stated


def test_cli_profile_takes_an_experience_level(api: respx.MockRouter) -> None:
    result = CliRunner().invoke(app, ["profile", "--experience", "new", "--tech", "python"])
    assert result.exit_code == 0, result.output
    assert "Open source experience: new" in result.output
    bad = CliRunner().invoke(app, ["profile", "--experience", "guru"])
    assert bad.exit_code != 0 and "Unknown experience level" in bad.output


def test_recommend_states_eligibility_from_the_faq(api: respx.MockRouter) -> None:
    data = GSoCToolkit().recommend_path(technologies=["python"], experience="experienced")
    notes = " ".join(data["notes"])
    assert "18 or older" in notes and "GSoC is not for experienced open source developers" in notes
    docs = GSoCToolkit().recommend_path(
        technologies=["markdown", "git"], interests=["documentation"]
    )
    assert any("GSoC projects are coding projects" in n for n in docs["notes"])


def test_orgs_checks_its_top_organizations_posts(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolkit = GSoCToolkit()
    seen: list[list[str]] = []

    def posts(owners: list[str], year: int) -> list[dict[str, Any]]:
        seen.append(owners)
        return []

    monkeypatch.setattr(toolkit.github, "gsoc_year_posts", posts)
    plain = toolkit.match_orgs(technologies=["python"])
    assert not seen and all(o.get("participation") is None for o in plain["organizations"])
    checked = toolkit.match_orgs(technologies=["python"], check_posts=True)
    assert 1 <= len(seen) <= 3
    assert any(o.get("participation") for o in checked["organizations"])


def test_an_empty_starter_list_names_where_to_look(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **k: [])
    data = toolkit.recommend_path(technologies=["python"], interests=["mathematics"])
    assert data["starter_issues"] == []
    top = data["recommended_orgs"][0]["name"]
    assert f'git-into-gsoc ideas "{top}"' in data["starter_issue_note"]
    # The path agrees: no step sends the person back to the search that came back empty.
    commands = " ".join(step["command"] for step in data["learning_path"])
    assert "issues --org" not in commands
    assert any("passed the checks" in step["why"] for step in data["learning_path"])


def test_starter_issues_search_every_language_more_owners_and_beginner_labels(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolkit = GSoCToolkit()
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(toolkit.github, "find_beginner_issues", lambda **k: seen.append(k) or [])
    toolkit.recommend_path(technologies=["django", "react"], interests=["mathematics"])
    first = seen[0]
    assert first["language"] == ["python", "javascript"]
    # Common beginner labels, but not "help wanted", which mostly marks bigger work.
    assert "starter" in first["labels"] and "help wanted" not in first["labels"]
    # Issues too old for the starter list are left out of the search itself.
    assert str(first["created_after"]).endswith("-01-01")


def test_starter_issues_in_a_repository_written_in_another_language_are_left_out(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = {
        "listenbrainz-android": {"language": "Kotlin", "description": "Android app"},
        "listenbrainz-server": {"language": "Python", "description": ""},
    }
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: repos[name])
    issues = [
        {"repo": "metabrainz/listenbrainz-android", "number": 1},
        {"repo": "metabrainz/listenbrainz-server", "number": 2},
    ]
    kept = toolkit._without_retired_repos(issues, ["python", "sql"])
    assert [i["number"] for i in kept] == [2]
    # With no languages known, the language is not a reason to leave an issue out.
    assert len(toolkit._without_retired_repos(issues)) == 2
