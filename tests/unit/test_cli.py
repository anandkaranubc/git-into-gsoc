from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


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
