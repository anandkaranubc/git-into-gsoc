"""Sorting a contributor's open pull requests into "needs you" and "waiting"."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.github.pulls import pull_request_status

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def _at(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _pull(**extra: Any) -> dict[str, Any]:
    return {
        "number": 4,
        "title": "Fix the parser",
        "html_url": "https://github.com/o/r/pull/4",
        "user": {"login": "Alice", "type": "User"},
        "created_at": _at(12),
        "draft": False,
        "mergeable_state": "clean",
        "base": {"ref": "main", "repo": {"full_name": "o/r"}},
        **extra,
    }


def _commit(days: float) -> dict[str, Any]:
    return {"event": "committed", "author": {"date": _at(days)}}


def _comment(who: str, days: float, kind: str = "User") -> dict[str, Any]:
    return {"event": "commented", "user": {"login": who, "type": kind}, "created_at": _at(days)}


def _review(who: str, state: str, days: float) -> dict[str, Any]:
    return {"event": "reviewed", "user": {"login": who}, "state": state, "submitted_at": _at(days)}


def test_conflict_and_failing_check_come_first() -> None:
    checks = [
        {"name": "lint", "status": "completed", "conclusion": "failure"},
        {"name": "tests", "status": "completed", "conclusion": "success"},
    ]
    status = pull_request_status(_pull(mergeable_state="dirty"), [_commit(5)], checks, now=NOW)
    assert status["status"] == "needs_you"
    assert status["ref"] == "o/r#4" and status["repo"] == "o/r"
    assert status["reasons"][0].startswith("Merge conflict with main")
    assert status["reasons"][1].startswith("Failing check: lint.")


def test_requested_changes_are_answered_only_by_a_later_commit() -> None:
    pending = pull_request_status(
        _pull(), [_commit(6), _review("bob", "CHANGES_REQUESTED", 4)], [], now=NOW
    )
    assert pending["status"] == "needs_you"
    assert pending["summary"].startswith("@bob requested changes 4 days ago")
    answered = pull_request_status(
        _pull(),
        [_commit(6), _review("bob", "CHANGES_REQUESTED", 4), _commit(3), _comment("alice", 3)],
        [],
        now=NOW,
    )
    assert answered["status"] == "waiting"
    assert answered["summary"] == "Waiting for review; your last update was 3 days ago"
    assert answered["follow_up"] is False


def test_an_unanswered_comment_needs_a_reply_and_bots_do_not_count() -> None:
    asked = pull_request_status(_pull(), [_commit(5), _comment("bob", 2)], [], now=NOW)
    assert asked["status"] == "needs_you"
    assert asked["summary"].startswith("@bob commented 2 days ago with no reply from you")
    replied = pull_request_status(
        _pull(), [_commit(5), _comment("bob", 2), _comment("alice", 1)], [], now=NOW
    )
    assert replied["status"] == "waiting"
    bot = pull_request_status(
        _pull(),
        [_commit(5), _comment("codecov[bot]", 1, kind="Bot"), _comment("stdlib-bot", 1)],
        [],
        now=NOW,
    )
    assert bot["status"] == "waiting"
    assert bot["summary"] == (
        "No reply from a reviewer yet; you last opened or updated it 5 days ago; "
        "one short, polite follow-up in the thread is fine"
    )


def test_approved_and_green_waits_and_long_silence_suggests_one_follow_up() -> None:
    approved = pull_request_status(
        _pull(), [_commit(5), _review("bob", "APPROVED", 1), _comment("bob", 1)], [], now=NOW
    )
    assert approved["status"] == "waiting"
    assert approved["summary"] == "Approved by @bob; waiting for a maintainer to merge"
    assert approved["follow_up"] is False
    quiet = pull_request_status(_pull(), [_commit(8)], [], now=NOW)
    assert quiet["follow_up"] is True and quiet["quiet_days"] == 8
    assert quiet["summary"].endswith("one short, polite follow-up in the thread is fine")


def test_draft_and_running_checks() -> None:
    checks = [{"name": "tests", "status": "in_progress", "conclusion": None}]
    status = pull_request_status(_pull(draft=True), [_commit(1)], checks, now=NOW)
    assert status["reasons"] == ["Still a draft: mark it ready for review when it is"]
    assert status["checks_running"] is True
