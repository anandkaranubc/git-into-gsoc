"""Weekly notes: saving, listing, and the reminder in `next`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.coach import plan_actions
from git_into_gsoc.errors import InputError
from git_into_gsoc.models import LogEntry
from git_into_gsoc.progress.store import ProgressStore

runner = CliRunner()
NOW = datetime(2026, 10, 20, tzinfo=UTC)


def test_log_roundtrip_and_summary() -> None:
    store = ProgressStore()
    store.add_log(
        LogEntry(goal="Run the test suite", done="Built it; 3 tests fail", links=["https://x"])
    )
    store.add_log(LogEntry(goal="Fix the first failure", stuck="Fixture missing"))
    entries = store.recent_logs(limit=5)
    assert [e.goal for e in entries] == ["Fix the first failure", "Run the test suite"]
    summary = store.summary()
    assert summary["log_entries"] == 2
    assert summary["last_log_days_ago"] == 0


def test_log_requires_some_content() -> None:
    with pytest.raises(InputError, match="empty"):
        ProgressStore().add_log(LogEntry())


def test_cli_log_write_and_list() -> None:
    result = runner.invoke(
        app,
        [
            "log",
            "--goal",
            "Reproduce #12",
            "--done",
            "Reproduced on main",
            "--links",
            "https://github.com/a/b/issues/12, https://github.com/a/b/pull/13",
            "--stuck",
            "Flaky test",
            "--next",
            "Ask in Zulip",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Reproduce #12" in result.stdout
    shown = runner.invoke(app, ["log"])
    assert shown.exit_code == 0
    assert "Flaky test" in shown.stdout
    assert "Ask in Zulip" in shown.stdout
    as_json = runner.invoke(app, ["log", "--output", "json"])
    assert '"links"' in as_json.stdout


def test_cli_log_empty_hint() -> None:
    result = runner.invoke(app, ["log"])
    assert result.exit_code == 0
    assert "No notes yet" in result.stdout


def test_next_reminds_to_log_when_contributing() -> None:
    store = ProgressStore()
    store.shortlist_org("SymPy")
    store.track_repo("sympy/sympy")
    store.track_issue("https://github.com/sympy/sympy/issues/5")
    state = store.load()
    state.weekly_log = [LogEntry(goal="old", at=NOW - timedelta(days=10))]
    program = {"phase": {"id": "before_announcement"}, "timeline": []}
    tracked = [{"ref": "sympy/sympy#5", "availability": "available", "reason": "free"}]
    actions = plan_actions(state, program, tracked_issues=tracked, new_issues=[], now=NOW)
    assert any("git-into-gsoc log" in a["command"] for a in actions)
    state.weekly_log = [LogEntry(goal="fresh", at=NOW - timedelta(days=2))]
    actions = plan_actions(state, program, tracked_issues=tracked, new_issues=[], now=NOW)
    assert not any("git-into-gsoc log" in a["command"] for a in actions)


def test_recent_logs_break_timestamp_ties_by_insertion_order() -> None:
    store = ProgressStore()
    same = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    store.add_log(LogEntry(goal="first", at=same))
    store.add_log(LogEntry(goal="second", at=same))
    assert [e.goal for e in store.recent_logs(limit=2)] == ["second", "first"]
