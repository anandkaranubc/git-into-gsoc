from __future__ import annotations

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


def test_cli_program_mentions_disclaimer() -> None:
    result = runner.invoke(app, ["program", "--year", "2027"])
    assert result.exit_code == 0
    assert "2027" in result.stdout
