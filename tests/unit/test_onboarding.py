"""The home screen and the guided `start` setup: topic parsing, milestones, the four
questions, and what each answer saves."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc import cli, onboarding
from git_into_gsoc.cli import app
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


@pytest.fixture
def api() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=rf"{OFFICIAL}/\d+/$").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=_archive_year(2026))
        )
        # start asks GitHub whether its top picks posted about the coming year.
        router.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        router.get(url__regex=r"https://api\.github\.com/(orgs|users)/[^/]+/repos").mock(
            return_value=httpx.Response(200, json=[])
        )
        yield router


def test_parse_topics_reads_numbers_and_words() -> None:
    assert onboarding.parse_topics("1, 3, open hardware") == ["science", "web", "open hardware"]
    assert onboarding.parse_topics("2 and 2, 99") == ["ai"]
    assert onboarding.parse_topics("") == []


def test_milestones_count_what_is_saved() -> None:
    steps = onboarding.milestones(
        {
            "profile": {"technologies": ["python"]},
            "shortlisted_orgs": ["SymPy", "NumFOCUS"],
            "tracked_repos": [],
            "tracked_issues": [],
            "log_entries": 0,
            "contributions": 1,
        }
    )
    assert [s["done"] for s in steps] == [True, True, False, False, False, True]
    assert steps[1]["count"] == 2
    assert all(s["command"].startswith("git-into-gsoc ") for s in steps)


def test_home_for_a_new_user_points_to_start(api: respx.MockRouter) -> None:
    data = onboarding.home(GSoCToolkit())
    assert data["new_user"] is True
    assert data["next_command"] == "git-into-gsoc start"
    assert data["done"] == 0
    assert data["program"]["phase"]


def test_bare_command_shows_home_not_a_wall_of_commands(api: respx.MockRouter) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "New here?" in result.stdout
    assert "git-into-gsoc start" in result.stdout
    assert "git-into-gsoc --help" in result.stdout
    assert "Usage:" not in result.stdout
    # No token here (conftest removes them), so the one-line reminder is shown.
    assert "Tip: run gh auth login once" in " ".join(result.stdout.split())


def test_home_has_no_token_tip_when_a_token_is_set(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from git_into_gsoc import config

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    config.get_settings.cache_clear()

    fresh = runner.invoke(app, [])
    assert fresh.exit_code == 0, fresh.output
    assert "Tip: run gh auth login" not in fresh.stdout

    # The returning view is a different branch of _render_home; the tip stays gone there too.
    GSoCToolkit().progress.set_profile(technologies=["python"], github="octocat")
    returning = runner.invoke(app, [])
    assert returning.exit_code == 0, returning.output
    assert "Welcome back, @octocat." in returning.stdout
    assert "Tip: run gh auth login" not in returning.stdout


def test_help_still_lists_every_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "start" in result.stdout and "pointers" in result.stdout


def test_bare_command_welcomes_back_with_progress(api: respx.MockRouter) -> None:
    toolkit = GSoCToolkit()
    toolkit.progress.set_profile(technologies=["python"], github="octocat")
    toolkit.progress.shortlist_org("SymPy")
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "Welcome back, @octocat." in result.stdout
    assert "2 of 6" in result.stdout
    assert "git-into-gsoc next" in result.stdout


def test_start_without_a_terminal_explains_the_options() -> None:
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, result.output
    assert "--tech python" in result.stdout
    asked = runner.invoke(app, ["start", "--output", "json"])
    data = json.loads(asked.stdout)
    assert data["needs_input"] is True
    assert [q["option"] for q in data["questions"]] == [
        "--github",
        "--tech",
        "--interests",
        "--hours",
    ]


def test_start_with_options_saves_profile_and_matches(api: respx.MockRouter) -> None:
    result = runner.invoke(
        app, ["start", "--tech", "python", "--interests", "1", "--hours", "8", "--output", "json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["profile"]["technologies"] == ["python"]
    assert data["profile"]["interests"] == ["science"]
    assert data["profile"]["hours_per_week"] == 8
    assert data["organizations"], "the embedded official list should match python + science"
    first = data["organizations"][0]["name"]
    assert data["next_steps"][0]["command"] == f'git-into-gsoc org "{first}"'


def test_start_says_when_the_hours_are_too_few_for_some_projects(api: respx.MockRouter) -> None:
    result = runner.invoke(app, ["start", "--tech", "python", "--interests", "1", "--hours", "3"])
    assert result.exit_code == 0, result.output
    assert "even a small project (about 90 hours)" in " ".join(result.stdout.split())


def test_start_asks_questions_and_shortlists(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    # Skip the username, then answer languages, topics, hours, and shortlist the first match.
    result = runner.invoke(app, ["start"], input="\npython\n1, 2\n12\n1\n")
    assert result.exit_code == 0, result.output
    assert "1 of 4" in result.stdout and "4 of 4" in result.stdout
    assert "Organizations that fit you" in result.stdout
    assert "Your shortlist:" in result.stdout
    toolkit = GSoCToolkit()
    assert toolkit.progress.profile()["interests"] == ["science", "ai"]
    assert len(toolkit.progress.load().shortlisted_orgs) == 1


def test_start_asks_again_for_an_unknown_username(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    api.get("https://api.github.com/users/no-such-person-x").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    result = runner.invoke(app, ["start"], input="no-such-person-x\n\npython\n\n\n\n")
    assert result.exit_code == 0, result.output
    assert "try again, or press Enter to skip" in result.stdout
    assert "github" not in GSoCToolkit().progress.profile()


def test_signed_in_login_needs_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from git_into_gsoc import config

    assert onboarding.signed_in_login(GSoCToolkit()) is None
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    config.get_settings.cache_clear()
    with respx.mock:
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat"})
        )
        assert onboarding.signed_in_login(GSoCToolkit()) == "octocat"
    with respx.mock:
        respx.get("https://api.github.com/user").mock(return_value=httpx.Response(401))
        assert onboarding.signed_in_login(GSoCToolkit()) is None


def test_start_sets_aside_an_organization_that_is_sitting_out(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = runner.invoke(
        app, ["start", "--tech", "python", "--interests", "1", "--output", "json"]
    )
    top = json.loads(first.stdout)["organizations"][0]
    owner = top["github_orgs"][0]

    def posts_for(self: GSoCToolkit, owners: list[str], *, year: int | None = None) -> dict:
        if owner in owners:
            post = {
                "status": "not_taking_part",
                "source": "wiki",
                "by_maintainer": False,
                "url": f"https://github.com/{owner}/x/wiki",
                "title": "Home",
            }
            return {"year": year or 2027, "posts": [post]}
        return {"year": year or 2027, "posts": []}

    monkeypatch.setattr(GSoCToolkit, "gsoc_posts_for", posts_for)
    result = runner.invoke(
        app, ["start", "--tech", "python", "--interests", "1", "--output", "json"]
    )
    data = json.loads(result.stdout)
    assert top["name"] not in [o["name"] for o in data["organizations"]]
    assert len(data["organizations"]) == 3
    assert data["set_aside"][0]["name"] == top["name"]
    shown = runner.invoke(app, ["start", "--tech", "python", "--interests", "1"])
    assert "Left out:" in shown.stdout
