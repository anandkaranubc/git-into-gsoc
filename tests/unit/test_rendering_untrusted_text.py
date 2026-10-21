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
        return value + HOSTILE
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
