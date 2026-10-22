"""The CLI's output and errors: tables, hints, next steps, and the home screen, through Typer's
test runner."""

from __future__ import annotations

import re

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    from git_into_gsoc import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_journey_json() -> None:
    result = runner.invoke(app, ["journey", "--output", "json"])
    assert result.exit_code == 0
    assert "learn" in result.stdout
    assert "proposal" in result.stdout


def test_cli_proposal_json() -> None:
    result = runner.invoke(app, ["proposal", "--output", "json"])
    assert result.exit_code == 0
    assert "checklist" in result.stdout


def test_cli_invalid_repo_is_a_friendly_error() -> None:
    result = runner.invoke(app, ["repo", "../../etc"])
    assert result.exit_code == 1
    assert "error:" in result.output
    assert "Traceback" not in result.output


@respx.mock
def test_cli_program_shows_estimate_and_phase() -> None:
    respx.get("https://summerofcode.withgoogle.com/api/program/2027/").mock(
        return_value=httpx.Response(404, json={})
    )
    result = runner.invoke(app, ["program", "--year", "2027"])
    assert result.exit_code == 0, result.output
    assert "2027" in result.stdout
    assert "estimate" in result.stdout
    assert "Now:" in result.stdout


def test_cli_setup_dry_run_reports_plan(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIG_HOME", str(tmp_path))
    result = runner.invoke(app, ["setup", "--dry-run", "--assistant", "cursor", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert '"dry_run": true' in result.output
    assert "mcp.json" in result.output
    assert not (tmp_path / ".cursor").exists()


def test_cli_setup_rejects_unknown_assistant(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIG_HOME", str(tmp_path))
    result = runner.invoke(app, ["setup", "--assistant", "emacs"])
    assert result.exit_code == 1
    assert "Unknown assistant" in result.output


@respx.mock
def test_cli_contributions_repo_scope() -> None:
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(app, ["contributions", "--github", "alice", "--repo", "acme/lib"])
    assert result.exit_code == 0, result.output
    assert "@alice" in result.stdout
    assert "none" in result.stdout
    assert "merged" in result.stdout.lower()


def test_cli_contributions_requires_scope() -> None:
    result = runner.invoke(app, ["contributions", "--github", "alice"])
    assert result.exit_code == 2


@respx.mock
def test_cli_next_without_live_checks() -> None:
    respx.get("https://summerofcode.withgoogle.com/api/program/2027/").mock(
        return_value=httpx.Response(404, json={})
    )
    result = runner.invoke(app, ["next", "--no-check"])
    assert result.exit_code == 0, result.output
    assert "Do next" in result.stdout
    assert "git-into-gsoc" in result.stdout


@respx.mock
def test_doctor_reachability_reports_each_source() -> None:
    from git_into_gsoc.cli import _reachable

    respx.head("https://up.example/").mock(return_value=httpx.Response(200))
    respx.head("https://nohead.example/").mock(return_value=httpx.Response(405))
    respx.get("https://nohead.example/").mock(return_value=httpx.Response(200))
    respx.head("https://down.example/").mock(side_effect=httpx.ConnectError("boom"))
    respx.head("https://broken.example/").mock(return_value=httpx.Response(503))
    assert "ok" in _reachable("https://up.example/", "ua")
    assert "ok" in _reachable("https://nohead.example/", "ua")
    assert "unreachable" in _reachable("https://down.example/", "ua")
    assert "HTTP 503" in _reachable("https://broken.example/", "ua")


def test_help_groups_commands_for_beginners() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for panel in (
        "Start here",
        "Find an organization",
        "Pick a repository and an issue",
        "Contribute and apply",
        "Track your journey",
        "Maintenance",
    ):
        assert panel in result.output, panel


def test_cli_setup_remove_dry_run(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIG_HOME", str(tmp_path))
    result = runner.invoke(
        app, ["setup", "--remove", "--dry-run", "--assistant", "cursor", "--output", "json"]
    )
    assert result.exit_code == 0, result.output
    assert '"remove": true' in result.output


def test_contributions_uses_the_saved_profile_or_asks_for_a_username(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli
    from git_into_gsoc.progress.store import ProgressStore

    seen: list[str] = []

    class Fake:
        progress = ProgressStore()

        def contribution_evidence(self, username, **kw):  # type: ignore[no-untyped-def]
            seen.append(username)
            return {"username": username}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    missing = runner.invoke(app, ["contributions", "--org", "SymPy"])
    assert missing.exit_code == 1 and "No GitHub username" in missing.output
    Fake.progress.set_profile(github="octocat")
    saved = runner.invoke(app, ["contributions", "--org", "SymPy", "--output", "json"])
    assert saved.exit_code == 0, saved.output
    assert seen == ["octocat"]


def test_not_found_org_is_an_error_and_limits_must_be_positive(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli

    missing = {"found": False, "error": "No organization matched 'zz'", "hint": "Try orgs --query"}

    class Fake:
        def org_details(self, *a, **k):  # type: ignore[no-untyped-def]
            return missing

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    rich = runner.invoke(app, ["org", "zz"])
    assert rich.exit_code == 1
    assert "error:" in rich.output and "hint:" in rich.output and "{" not in rich.output
    as_json = runner.invoke(app, ["org", "zz", "--output", "json"])
    assert as_json.exit_code == 1 and '"found": false' in as_json.output
    assert runner.invoke(app, ["orgs", "-n", "0"]).exit_code == 2
    assert runner.invoke(app, ["issues", "-n", "-5"]).exit_code == 2


def test_cli_setup_says_when_nothing_was_set_up(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIG_HOME", str(tmp_path))
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/mcp.json").write_text('{\n  // mine\n  "mcpServers": {}\n}\n')
    result = runner.invoke(app, ["setup", "--assistant", "cursor", "--no-skill"])
    assert result.exit_code == 0, result.output
    assert "Nothing was set up" in result.output
    assert "Restart your assistant" not in result.output


def test_org_from_an_earlier_year_is_not_shown_as_current(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli

    past = {
        "found": True,
        "catalog": {"year": 2026},
        "organization": {
            "name": "The Tor Project",
            "description": "Privacy tools",
            "official": False,
            "years_active": [2017, 2023, 2025],
            "projects_by_year": {2025: 3},
        },
    }

    class Fake:
        def org_details(self, *a, **k):  # type: ignore[no-untyped-def]
            return past

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["org", "Tor"])
    assert result.exit_code == 0, result.output
    assert "not in the 2026 list" in result.output
    assert "last took part in 2025" in result.output
    assert "2026 · accepted" not in result.output


def test_unknown_org_for_past_projects_is_an_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli

    class Fake:
        def past_projects(self, *a, **k):  # type: ignore[no-untyped-def]
            return {"found": False, "error": "No GSoC organization is named 'zz'", "hint": "x"}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["projects", "--org", "zz"])
    assert result.exit_code == 1
    assert "No GSoC organization is named 'zz'" in result.output


@respx.mock
def test_program_speaks_to_the_person_and_ends_with_a_next_step() -> None:
    respx.get("https://summerofcode.withgoogle.com/api/program/2027/").mock(
        return_value=httpx.Response(404, json={})
    )
    result = runner.invoke(app, ["program", "--year", "2027"])
    assert result.exit_code == 0, result.output
    # Rules meant for an assistant ("Never fabricate organizations") are not shown to people.
    assert "fabricate" not in result.stdout
    assert "Good habits" in result.stdout
    assert "git-into-gsoc start" in result.stdout  # no profile saved yet


def test_an_empty_issue_search_prints_next_steps_not_an_empty_table(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli

    class Fake:
        def find_issues(self, **kw):  # type: ignore[no-untyped-def]
            return {
                "note": "Searching GitHub orgs of GSoC 2026 organizations that use html.",
                "issues": [],
                "next_steps": ["Pick an organization first: git-into-gsoc orgs --tech html"],
            }

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["issues", "--language", "html"])
    assert result.exit_code == 0, result.output
    assert "No free beginner issues found." in result.output
    assert "git-into-gsoc orgs --tech html" in result.output
    assert "┏" not in result.output


def _listed(status: str, **extra: object) -> dict[str, object]:
    return {
        "repo": "acme/lib",
        "number": 7,
        "title": "Fix the thing",
        "availability": status,
        "beginner_score": 70,
        "signals": [],
        "assessment": {"claims": []},
        **extra,
    }


def test_the_issues_table_reads_like_words_and_flags_old_requests(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # From a blind beginner test (2026-10-22): the table printed "likely_taken", showed
    # "available" for an issue someone asked for months ago, and gave no hint that an
    # issue had only "help wanted".
    from git_into_gsoc import cli

    issues = [
        _listed("likely_taken"),
        _listed("available", number=8, assessment={"claims": [{"login": "a"}]}),
        _listed(
            "available",
            number=9,
            signals=["No beginner label: issues marked only 'help wanted' are often harder"],
        ),
    ]

    class Fake:
        def find_issues(self, **k):  # type: ignore[no-untyped-def]
            return {"issues": issues, "note": "Searching acme", "next_steps": []}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["issues", "--repo", "acme/lib"], env={"COLUMNS": "160"})
    assert result.exit_code == 0, result.output
    assert "likely taken" in result.output and "likely_taken" not in result.output
    assert result.output.count("asked before") == 1
    assert "no beginner label" in result.output


def test_tracking_an_issue_says_so(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc import cli
    from git_into_gsoc.progress.store import ProgressStore

    class Fake:
        progress = ProgressStore()

        def issue_status(self, ref, number=None):  # type: ignore[no-untyped-def]
            return {
                "title": "Fix the thing",
                "url": "https://github.com/acme/lib/issues/7",
                "repo": "acme/lib",
                "number": 7,
                "availability": "available",
                "reason": "Open",
                "assessment": {
                    "maintainer_engaged": False,
                    "linked_prs": [],
                    "claims": [],
                    "caveats": [],
                },
                "before_you_comment": [],
            }

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["issue", "acme/lib#7", "--track"])
    assert result.exit_code == 0, result.output
    assert "Saved to your progress" in result.output


def test_an_empty_repo_search_names_its_owner_in_the_tip() -> None:
    from git_into_gsoc.service import _when_no_issues

    steps = _when_no_issues("python", org=None, repo="MDAnalysis/mdacli")
    assert "git-into-gsoc repos MDAnalysis" in steps[-1]
    assert "ORG NAME" not in " ".join(steps)


def test_a_long_issue_reference_stays_on_one_line(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 0.18.2's clean-install check at 110 columns showed "learning-unlimited/ESP-Website#"
    # with "2455" on the next line, beside a long status note.
    from git_into_gsoc import cli

    row = _listed(
        "available",
        repo="learning-unlimited/ESP-Website",
        number=2455,
        title="Grade range errors are confusing when a class has no grades set at all",
        assessment={"claims": [{"login": "a"}]},
    )

    class Fake:
        def find_issues(self, **k):  # type: ignore[no-untyped-def]
            return {"issues": [row], "note": "Searching", "next_steps": []}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    # 0.19.0 kept the reference whole but cropped the table at 80 columns, the default
    # macOS Terminal width: no right border, titles cut mid-word.
    for width in (60, 80, 100, 110):
        result = runner.invoke(
            app, ["issues", "--org", "Learning Unlimited"], env={"COLUMNS": str(width)}
        )
        assert result.exit_code == 0, result.output
        table = [line for line in result.output.splitlines() if line[:1] in "┏┃┡│└"]
        assert table and all(line.rstrip().endswith(tuple("┓┃┩│┘")) for line in table), width
        if width >= 80:
            assert "learning-unlimited/ESP-Website#2455" in result.output, width
            words = set(re.findall(r"[\w']+", result.output))
            assert set(row["title"].split()) <= words, width  # no word cut off
