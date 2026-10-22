"""Every rich renderer must print text from strangers literally.

Issue titles, ideas pages, CONTRIBUTING sentences, label names, and org
descriptions all come from people outside the project. Rich treats ``[...]``
as markup, so an unescaped ``[x]`` vanishes and an unescaped ``[/]`` crashes
the command. These tests replay real captured output of every command with
hostile markup appended to every string and require a clean, literal render.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

from conftest import FIXTURES
from git_into_gsoc import cli
from git_into_gsoc.progress.store import ProgressStore

HOSTILE = " [/]x[bold]y[/bold][link=z]"
# A clipboard-writing terminal sequence, a zero-width space, a Unicode tag letter,
# and a right-to-left override: none may reach a terminal or an assistant.
HIDDEN = "\x1b]52;c;aGk=\x1b\\\u200b\U000e0041\u202e"
HIDDEN_CHARS = ("\x1b", "\u200b", "\U000e0041", "\u202e")
# Values the CLI uses as lookup keys or parses, rather than prints as text.
STRUCTURAL_KEYS = {
    "status",
    "availability",
    "kind",
    "id",
    "action",
    "strength",
    "phase_id",
    "scope",
    "source",
    "fmt",
    "project_size",
}


def poison(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: poison(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [poison(v, key) for v in value]
    if isinstance(value, str):
        if key in STRUCTURAL_KEYS or key.endswith(("_at", "datetime")) or key in {"at", "date"}:
            return value
        return value + HOSTILE + HIDDEN
    return value


def load(name: str) -> Any:
    return json.loads((FIXTURES / "rendering" / f"{name}.json").read_text(encoding="utf-8"))


CASES = [
    ("program_info", "program", ["program"]),
    ("match_orgs", "orgs", ["orgs", "--tech", "python"]),
    ("org_details", "org", ["org", "SymPy"]),
    ("past_projects", "projects", ["projects", "symbolic"]),
    ("org_ideas", "ideas", ["ideas", "SymPy"]),
    ("org_mentors", "mentors", ["mentors", "SymPy"]),
    ("discover_repos", "repos", ["repos", "SymPy"]),
    ("evaluate_repo", "repo", ["repo", "sympy/sympy"]),
    ("orient_repo", "orient", ["orient", "sympy/sympy"]),
    ("find_issues", "issues", ["issues", "--repo", "sympy/sympy"]),
    ("issue_status", "issue", ["issue", "sympy/sympy#1"]),
    ("issue_pointers", "pointers", ["pointers", "sympy/sympy#1"]),
    ("draft", "draft", ["draft", "claim", "--issue", "sympy/sympy#1"]),
    ("recommend_path", "recommend", ["recommend", "--tech", "python"]),
    ("contribution_evidence", "contributions", ["contributions", "-g", "x", "--org", "SymPy"]),
    ("proposal_help", "proposal_help", ["proposal"]),
    ("next_steps", "next", ["next"]),
]


class FakeToolkit:
    def __init__(self, method: str, data: Any) -> None:
        self.progress = ProgressStore()
        setattr(self, method, lambda *a, **k: data)


@pytest.fixture
def wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    # Module-level consoles write to the current sys.stdout; a wide one keeps
    # cells from wrapping so the literal check below is meaningful.
    monkeypatch.setattr(cli, "console", Console(width=400, color_system=None))


@pytest.mark.parametrize(("method", "fixture", "argv"), CASES, ids=[c[1] for c in CASES])
def test_command_renders_untrusted_text_literally(
    method: str,
    fixture: str,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    wide_console: None,
) -> None:
    data = poison(load(fixture))
    monkeypatch.setattr(cli, "_toolkit", lambda: FakeToolkit(method, data))
    result = CliRunner().invoke(cli.app, argv)
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(
        result.exception
    )
    assert result.exit_code == 0, result.output[-800:]
    assert "[/]x[bold]y[/bold]" in result.output, "untrusted text was not printed literally"
    assert "\\[" not in result.output, "escaped text was printed with its backslashes"
    assert not [c for c in HIDDEN_CHARS if c in result.output], "hidden characters were printed"


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return [value] if isinstance(value, str) else []


@pytest.mark.parametrize(("method", "fixture", "argv"), CASES, ids=[c[1] for c in CASES])
def test_json_output_carries_no_hidden_characters(
    method: str,
    fixture: str,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    wide_console: None,
) -> None:
    data = poison(load(fixture))
    monkeypatch.setattr(cli, "_toolkit", lambda: FakeToolkit(method, data))
    result = CliRunner().invoke(cli.app, [*argv, "--output", "json"])
    assert result.exit_code == 0, result.output[-800:]
    hidden = [s for s in _strings(json.loads(result.output)) if any(c in s for c in HIDDEN_CHARS)]
    assert not hidden, hidden[:3]


def test_proposal_check_renders_untrusted_text_literally(
    monkeypatch: pytest.MonkeyPatch, wide_console: None, tmp_path: Path
) -> None:
    data = poison(load("proposal_check"))
    monkeypatch.setattr(cli, "_toolkit", lambda: FakeToolkit("check_proposal", data))
    draft = tmp_path / "draft.md"
    draft.write_text("# Draft\n", encoding="utf-8")
    result = CliRunner().invoke(cli.app, ["proposal", str(draft), "--no-verify"])
    assert result.exit_code == 0, result.output[-800:]
    assert "[/]x[bold]y[/bold]" in result.output
    assert "\\[" not in result.output


def test_profile_renders_literally(wide_console: None) -> None:
    ProgressStore().set_profile(technologies=["c[x]", "[/]rust"], timezone="UTC[/]")
    result = CliRunner().invoke(cli.app, ["profile"])
    assert result.exit_code == 0, result.output
    assert "c[x]" in result.output and "[/]rust" in result.output
    assert "\\[" not in result.output


def test_user_notes_render_literally(wide_console: None) -> None:
    runner = CliRunner()
    note = "Fixed [x] and closed [/] tags"
    assert runner.invoke(cli.app, ["progress", "note", "--value", note]).exit_code == 0
    logged = runner.invoke(cli.app, ["log", "--goal", note, "--next", "[/]"])
    assert logged.exit_code == 0, logged.output
    assert "[x]" in logged.output and "[/]" in logged.output
    listed = runner.invoke(cli.app, ["log"])
    assert listed.exit_code == 0 and "[x]" in listed.output
    assert "\\[" not in logged.output + listed.output


def test_error_messages_quote_input_literally() -> None:
    # The message quotes what was typed; as markup, "[/bold]" crashed the command.
    result = CliRunner().invoke(cli.app, ["issue", "sympy/sympy#[/bold]x"])
    assert result.exit_code == 1, repr(result.exception)
    assert "[/bold]x" in result.output


def test_mcp_results_carry_no_hidden_characters() -> None:
    from git_into_gsoc.mcp_server import _dump

    out = json.loads(_dump({"title": "Free" + HIDDEN, "items": [{"body": "ok" + HIDDEN}]}))
    assert not [s for s in _strings(out) if any(c in s for c in HIDDEN_CHARS)]
    assert out["title"].startswith("Free]52;c;aGk=")


def test_progress_reads_as_a_checklist_and_json_is_unchanged(wide_console: None) -> None:
    runner = CliRunner()
    assert runner.invoke(cli.app, ["progress", "complete_phase", "--phase", "learn"]).exit_code == 0
    saved = runner.invoke(cli.app, ["progress", "shortlist_org", "--value", "Org [/] Lab"])
    assert saved.exit_code == 0 and "Saved." in saved.output
    shown = runner.invoke(cli.app, ["progress"])
    assert shown.exit_code == 0, shown.output
    assert "1/10 phases done" in shown.output and "discover  (next)" in shown.output
    assert "Org [/] Lab" in shown.output and "\\\\[" not in shown.output
    assert not shown.output.lstrip().startswith("{"), "rich output is still raw JSON"
    as_json = json.loads(runner.invoke(cli.app, ["progress", "--output", "json"]).output)
    assert as_json["completion"] == "1/10" and as_json["shortlisted_orgs"] == ["Org [/] Lab"]


def test_the_repos_table_says_what_its_score_means(
    monkeypatch: pytest.MonkeyPatch, wide_console: None
) -> None:
    monkeypatch.setattr(cli, "_toolkit", lambda: FakeToolkit("discover_repos", load("repos")))
    result = CliRunner().invoke(cli.app, ["repos", "SymPy"])
    assert result.exit_code == 0, result.output[-800:]
    assert "Not a grade or a chance of acceptance" in result.output
