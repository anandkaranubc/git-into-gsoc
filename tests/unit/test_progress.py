"""The progress store: phases, tracking, notes, the lock, atomic saves, and damaged or busy
files."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_into_gsoc.errors import InputError
from git_into_gsoc.models import JourneyPhase
from git_into_gsoc.progress.store import ProgressStore


def test_progress_roundtrip(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    store.set_profile(github="alice", top_language="Python")
    store.shortlist_org("SymPy")
    store.track_repo("sympy/sympy")
    store.complete_phase(JourneyPhase.LEARN)
    summary = store.summary()
    assert summary["profile"]["github"] == "alice"
    assert "SymPy" in summary["shortlisted_orgs"]
    assert summary["phases"]["learn"] is True
    assert summary["percent"] > 0


def test_empty_values_are_rejected(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    for method in (store.shortlist_org, store.track_repo, store.track_issue, store.add_note):
        with pytest.raises(InputError, match="empty"):
            method("   ")
    assert not (tmp_path / "progress.json").exists()


def test_unknown_phase_is_an_input_error(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    with pytest.raises(InputError, match="Unknown phase"):
        store.complete_phase("nope")
    assert store.complete_phase(" Discover ").phases["discover"] is True


def test_mcp_progress_raises_tool_errors_with_hints(tmp_path: Path) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    from git_into_gsoc.mcp_server import gsoc_progress

    with pytest.raises(ToolError, match="Unknown phase"):
        gsoc_progress(action="complete_phase", phase="nope")
    with pytest.raises(ToolError, match="empty"):
        gsoc_progress(action="note", value="")
    with pytest.raises(ToolError, match="Unknown action"):
        gsoc_progress(action="dance")


def test_mcp_progress_writes_return_the_bounded_summary(tmp_path: Path) -> None:
    """The whole state after a write put every note into the model's context each time."""
    import json

    from git_into_gsoc.mcp_server import gsoc_progress

    for i in range(12):
        out = json.loads(gsoc_progress(action="note", value=f"note {i}"))
    assert out["notes"] == 12 and len(out["recent_notes"]) == 5
    assert "weekly_log" not in out
    assert json.loads(gsoc_progress(action="shortlist_org", value="SymPy"))["shortlisted_orgs"] == [
        "SymPy"
    ]


def test_old_progress_files_gain_new_phases(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.write_text(
        '{"version": 1, "target_year": 2027, "phases": {"learn": true, "discover": false}}',
        encoding="utf-8",
    )
    store = ProgressStore(path)
    state = store.load()
    assert state.phases["learn"] is True
    assert state.phases["orient"] is False and state.phases["iterate"] is False
    assert store.summary()["completion"] == "1/10"


def test_progress_file_and_dirs_are_private(tmp_path: Path) -> None:
    import os
    import stat

    from git_into_gsoc import config

    store = ProgressStore(tmp_path / "data" / "progress.json")
    store.add_note("private")
    cache = config.cache_dir()
    if os.name == "posix":
        assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
        assert stat.S_IMODE(cache.stat().st_mode) == 0o700
    assert store.load().target_year == config.DEFAULT_TARGET_YEAR


def test_profile_saves_the_username_when_github_is_unreachable() -> None:
    import httpx
    import respx

    from git_into_gsoc.service import GSoCToolkit

    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://api.github.com/users/").mock(
            side_effect=httpx.ConnectError("offline")
        )
        profile = GSoCToolkit().save_profile(github="octocat", technologies=["python"])
    assert profile["github"] == "octocat"
    assert profile["technologies"] == ["python"]
    assert "could not be reached" in profile["warning"]
    assert "warning" not in GSoCToolkit().progress.profile()  # the hint is not persisted


def test_profile_rejects_a_user_that_does_not_exist() -> None:
    import httpx
    import respx

    from git_into_gsoc.errors import NotFoundError
    from git_into_gsoc.service import GSoCToolkit

    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://api.github.com/users/").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        with pytest.raises(NotFoundError):
            GSoCToolkit().save_profile(github="no-such-user-xyz")


def test_damaged_progress_file_is_kept_and_replaced(tmp_path: Path, caplog) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "progress.json"
    path.write_text('{"phases": {"learn": tr', encoding="utf-8")
    store = ProgressStore(path)
    with caplog.at_level("WARNING"):
        state = store.load()
    assert state.phases["learn"] is False
    kept = list(tmp_path.glob("progress.damaged-*.json"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8").startswith('{"phases"')
    assert "could not be read" in caplog.text and "moved to" in caplog.text
    store.add_note("fresh start")
    assert store.load().notes == ["fresh start"]


def test_a_mutating_call_recovers_a_damaged_file_while_holding_the_lock(tmp_path: Path) -> None:
    # _recover takes the lock; add_note already holds it, and a lock that was not
    # re-entrant would have waited for the 30-second timeout and then refused.
    import time

    path = tmp_path / "progress.json"
    path.write_text('{"phases": {"learn": tr', encoding="utf-8")
    started = time.monotonic()
    ProgressStore(path).add_note("fresh start")
    assert time.monotonic() - started < 5
    assert len(list(tmp_path.glob("progress.damaged-*.json"))) == 1
    assert ProgressStore(path).load().notes == ["fresh start"]
    assert not path.with_name("progress.json.lock").exists()


def test_wrong_shape_progress_file_is_recovered(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.write_text('{"phases": "not-a-dict"}', encoding="utf-8")
    assert ProgressStore(path).summary()["completion"].startswith("0/")


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    for i in range(5):
        store.add_note(f"note {i}")
    assert [p.name for p in tmp_path.iterdir()] == ["progress.json"]


def _add_notes(path: str, worker: int, count: int) -> None:
    from git_into_gsoc.progress.store import ProgressStore as Store

    store = Store(Path(path))
    for i in range(count):
        store.add_note(f"w{worker}-{i}")


def _read_summaries(path: str, count: int) -> None:
    from git_into_gsoc.progress.store import ProgressStore as Store

    store = Store(Path(path))
    for _ in range(count):
        store.summary()


def test_concurrent_writers_never_lose_or_corrupt_notes(tmp_path: Path) -> None:
    """Eight writers and two readers at once, like the CLI next to an assistant's server.

    On Windows a file being replaced or deleted is briefly locked; that must mean
    "wait", never a crash, and never a good file set aside as damaged.
    """
    import multiprocessing

    path = tmp_path / "progress.json"
    ProgressStore(path).add_note("seed")
    ctx = multiprocessing.get_context("spawn")
    workers = [ctx.Process(target=_add_notes, args=(str(path), w, 10)) for w in range(8)]
    workers += [ctx.Process(target=_read_summaries, args=(str(path), 40)) for _ in range(2)]
    for proc in workers:
        proc.start()
    for proc in workers:
        proc.join(90)
        assert proc.exitcode == 0
    notes = ProgressStore(path).load().notes
    assert len(notes) == 81 and len(set(notes)) == 81
    assert not list(tmp_path.glob("*.lock")) and not list(tmp_path.glob(".progress-*"))
    assert not list(tmp_path.glob("progress.damaged-*")), "a good file was set aside"


def test_an_unreadable_progress_file_is_an_error_not_a_reset(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.mkdir()  # reading a folder fails the way a locked or unreadable file does
    with pytest.raises(InputError, match="Cannot read"):
        ProgressStore(path).load()
    assert path.is_dir() and not list(tmp_path.glob("progress.damaged-*"))


def test_stale_lock_from_a_crashed_process_is_broken(tmp_path: Path) -> None:
    import os
    import time

    path = tmp_path / "progress.json"
    lock = tmp_path / "progress.json.lock"
    lock.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    ProgressStore(path).add_note("after a crash")
    assert ProgressStore(path).load().notes == ["after a crash"]


def test_a_waiter_with_a_stale_view_does_not_steal_a_fresh_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import time

    from git_into_gsoc.progress import store as store_module

    lock = tmp_path / "progress.json.lock"
    lock.write_text("", encoding="utf-8")
    os.utime(lock, (time.time() - 3600, time.time() - 3600))
    real_rename = os.rename
    calls: list[str] = []

    def other_waiter_wins_first(src, dst):  # type: ignore[no-untyped-def]
        if not calls:  # between our stale check and our rename, the other waiter won
            lock.unlink()
            lock.write_text("theirs", encoding="utf-8")
        calls.append(str(dst))
        real_rename(src, dst)

    monkeypatch.setattr(store_module.os, "rename", other_waiter_wins_first)
    monkeypatch.setattr(store_module, "LOCK_TIMEOUT_SECONDS", 0.2)
    with pytest.raises(InputError, match="Another git-into-gsoc process"):
        ProgressStore(tmp_path / "progress.json").add_note("lost")
    assert lock.read_text(encoding="utf-8") == "theirs"
    assert not list(tmp_path.glob("*.stale-*"))


def test_a_hand_edited_comma_list_reads_as_a_list(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.write_text(
        '{"profile": {"technologies": "python, rust", "interests": "science"}}',
        encoding="utf-8",
    )
    profile = ProgressStore(path).profile()
    assert profile["technologies"] == ["python", "rust"]
    assert profile["interests"] == ["science"]


def test_tracking_saves_one_canonical_link_per_issue(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    for ref in (
        "sympy/sympy#5",
        "https://github.com/SymPy/SymPy/issues/5#issuecomment-1",
        "github.com/sympy/sympy/issues/5",
    ):
        store.track_issue(ref)
    store.track_issue("https://github.com/sympy/sympy/pull/7")
    assert store.load().tracked_issues == [
        "https://github.com/sympy/sympy/issues/5",
        "https://github.com/sympy/sympy/pull/7",
    ]


@pytest.mark.parametrize("junk", ["javascript:alert(1)", "not an issue", "sympy/sympy"])
def test_tracking_refuses_what_is_not_an_issue(tmp_path: Path, junk: str) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    with pytest.raises(InputError, match="Not an issue"):
        store.track_issue(junk)
    assert not (tmp_path / "progress.json").exists()


def test_repos_and_orgs_are_saved_once_whatever_the_spelling(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    store.track_repo("https://github.com/SymPy/sympy.git")
    store.track_repo("sympy/sympy")
    store.shortlist_org("SymPy")
    store.shortlist_org("sympy")
    state = store.load()
    assert state.tracked_repos == ["SymPy/sympy"]
    assert state.shortlisted_orgs == ["SymPy"]
    with pytest.raises(InputError, match="owner/repo"):
        store.track_repo("javascript:alert(1)")


def test_notes_have_a_length_limit_but_older_long_notes_still_load(tmp_path: Path) -> None:
    import json

    from git_into_gsoc.models import LogEntry

    path = tmp_path / "progress.json"
    store = ProgressStore(path)
    store.add_note("n" * 2000)
    with pytest.raises(InputError, match="limit is 2,000"):
        store.add_note("n" * 2001)
    with pytest.raises(InputError, match="next step is"):
        store.add_log(LogEntry(next_step="n" * 2001))
    path.write_text(json.dumps({"version": 1, "notes": ["n" * 5000]}))
    assert store.load().notes == ["n" * 5000]


def test_log_links_must_be_web_links(tmp_path: Path) -> None:
    from git_into_gsoc.models import LogEntry

    store = ProgressStore(tmp_path / "progress.json")
    for junk in ("javascript:alert(1)", "not a url", "mailto:x@example.org", "https://[::1"):
        with pytest.raises(InputError, match="Not a web link"):
            store.add_log(LogEntry(done="x", links=[junk]))
    with pytest.raises(InputError, match="limit is 20"):
        store.add_log(LogEntry(done="x", links=[f"https://example.org/{i}" for i in range(21)]))
    store.add_log(
        LogEntry(
            done="x",
            links=["github.com/sympy/sympy/pull/1", "https://github.com/sympy/sympy/pull/1"],
        )
    )
    assert store.load().weekly_log[-1].links == ["https://github.com/sympy/sympy/pull/1"]


def _as_if_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat PermissionError as a Windows sharing violation, on any system."""
    from git_into_gsoc.progress import store as store_module

    monkeypatch.setattr(store_module, "_busy", lambda exc: isinstance(exc, PermissionError))
    monkeypatch.setattr(store_module, "BUSY_WAIT_SECONDS", 0)


def test_a_briefly_busy_file_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    from git_into_gsoc.progress import store as store_module

    _as_if_on_windows(monkeypatch)
    calls: list[int] = []

    def busy_twice() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError(13, "The process cannot access the file")
        return "read"

    assert store_module._retry_busy(busy_twice) == "read" and len(calls) == 3


def test_a_busy_lock_file_means_wait_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from git_into_gsoc.progress import store as store_module

    _as_if_on_windows(monkeypatch)
    real_open = os.open
    refused: list[str] = []

    def lock_busy_once(path, flags, *args):  # type: ignore[no-untyped-def]
        if str(path).endswith(".lock") and not refused:
            refused.append(str(path))
            raise PermissionError(13, "delete pending")
        return real_open(path, flags, *args)

    monkeypatch.setattr(store_module.os, "open", lock_busy_once)
    ProgressStore(tmp_path / "progress.json").add_note("after a busy lock")
    assert refused and ProgressStore(tmp_path / "progress.json").load().notes == [
        "after a busy lock"
    ]


def test_off_windows_a_permission_error_fails_at_once(tmp_path: Path) -> None:
    import os

    if os.name == "nt":
        pytest.skip("on Windows a PermissionError may be a sharing violation")
    from git_into_gsoc.progress import store as store_module

    calls: list[int] = []

    def denied() -> None:
        calls.append(1)
        raise PermissionError(13, "Permission denied")

    with pytest.raises(PermissionError):
        store_module._retry_busy(denied)
    assert calls == [1]


def test_hand_edited_times_without_a_timezone_are_read_as_utc(tmp_path: Path) -> None:
    import json

    from typer.testing import CliRunner

    from git_into_gsoc.cli import app
    from git_into_gsoc.models import LogEntry

    # docs/configuration.md invites hand edits, and a log entry dated "2026-10-01T10:00:00"
    # crashed `log`, `progress`, the home screen, and `next` with a naive/aware TypeError.
    path = tmp_path / "data" / "progress.json"
    store = ProgressStore(path)
    store.add_log(LogEntry(goal="first"))
    raw = json.loads(path.read_text())
    raw["weekly_log"].append({"at": "2026-10-01T10:00:00", "goal": "hand-added"})
    raw["last_checked_at"] = "2026-10-02T10:00:00"
    raw["updated_at"] = "2026-10-03T10:00:00"
    path.write_text(json.dumps(raw))
    state = store.load()
    assert all(t and t.tzinfo for t in (state.last_checked_at, state.updated_at))
    assert [e.goal for e in store.recent_logs()] == ["first", "hand-added"]
    assert store.summary()["log_entries"] == 2
    for command in (["log"], ["progress"]):
        result = CliRunner().invoke(app, command)
        assert result.exit_code == 0, (command, result.output, result.exception)


def test_fields_from_a_newer_version_survive_a_save(tmp_path: Path) -> None:
    import json

    # Plugins run their own copy, so an older MCP server and a newer CLI can share one
    # progress.json; the older one dropped every field it did not know on each save.
    path = tmp_path / "progress.json"
    store = ProgressStore(path)
    store.add_note("first")
    raw = json.loads(path.read_text())
    raw["streak"] = {"weeks": 3}
    raw["weekly_log"] = [{"at": "2026-10-01T10:00:00Z", "goal": "g", "mood": "good"}]
    path.write_text(json.dumps(raw))
    store.add_note("second")
    saved = json.loads(path.read_text())
    assert saved["streak"] == {"weeks": 3}
    assert saved["weekly_log"][0]["mood"] == "good"
    assert saved["notes"] == ["first", "second"]


def test_the_summary_shows_the_newest_notes(tmp_path: Path) -> None:
    # `progress note` saved notes that neither `progress` nor gsoc_progress could show.
    store = ProgressStore(tmp_path / "progress.json")
    for number in range(1, 8):
        store.add_note(f"note {number}")
    summary = store.summary()
    assert summary["notes"] == 7
    assert summary["recent_notes"] == ["note 7", "note 6", "note 5", "note 4", "note 3"]


def test_recovery_leaves_a_file_another_process_already_repaired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog,  # type: ignore[no-untyped-def]
) -> None:
    # Reads run without the lock. One process read the damaged text, a second one
    # recovered and saved a good file, then the first moved that good file aside.
    from git_into_gsoc.progress import store as store_module

    path = tmp_path / "progress.json"
    path.write_text('{"phases": {"learn": tr', encoding="utf-8")
    real = store_module.ProgressState.model_validate_json
    raced = False

    def racing(raw: bytes) -> object:
        nonlocal raced
        if not raced:
            raced = True
            ProgressStore(path).add_note("from the other process")
        return real(raw)

    monkeypatch.setattr(store_module.ProgressState, "model_validate_json", racing)
    with caplog.at_level("WARNING"):
        ProgressStore(path).load()
    assert ProgressStore(path).load().notes == ["from the other process"]
    assert len(list(tmp_path.glob("progress.damaged-*.json"))) == 1
    # The second process moved the damaged file; the first moved nothing, and its
    # warning (the last one) must not say it did.
    assert "left in place" in caplog.records[-1].getMessage()
    assert "moved to" not in caplog.records[-1].getMessage()


def test_two_recoveries_in_one_second_keep_two_backups(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    for text in ('{"phases": 1', '{"notes": 1'):
        path.write_text(text, encoding="utf-8")
        ProgressStore(path).load()
    assert len(list(tmp_path.glob("progress.damaged-*.json"))) == 2


def test_other_host_links_follow_the_same_rules_as_github_and_log_links(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    store.track_issue("https://gitlab.com/inkscape/inkscape/-/issues/5")
    store.track_issue("https://gitlab.com/inkscape/inkscape/-/issues/5?x=1")
    store.track_repo("sympy/sympy")
    store.track_repo("https://github.com:443/sympy/sympy")
    state = store.load()
    assert state.tracked_issues == ["https://gitlab.com/inkscape/inkscape/-/issues/5"]
    assert state.tracked_repos == ["sympy/sympy"]
    with pytest.raises(InputError, match="limit is 500"):
        store.track_repo("https://gitlab.com/x/" + "a" * 5000)
    with pytest.raises(InputError, match="limit is 500"):
        store.track_issue("https://gitlab.com/x/" + "a" * 5000 + "/-/issues/5")
    with pytest.raises(InputError, match="issue link, not a repository"):
        store.track_repo("https://gitlab.com/inkscape/inkscape/-/issues/5")


def test_bug_trackers_that_put_the_number_in_the_query_keep_it() -> None:
    from git_into_gsoc.progress.store import other_host_link

    # Cutting every query string turned two GCC bugs into one link (review of #425).
    gcc = "https://gcc.gnu.org/bugzilla/show_bug.cgi?id="
    assert other_host_link(gcc + "118000") == gcc + "118000"
    assert other_host_link(gcc + "118001#c3") == gcc + "118001"
    assert other_host_link("https://sourceware.org/bugzilla/show_bug.cgi?id=32000").endswith(
        "?id=32000"
    )
    savannah = "https://savannah.gnu.org/bugs/index.php?66000"
    assert other_host_link(savannah) == savannah
    # Only after /issues/N does the query name the same issue.
    gitlab = "https://gitlab.com/inkscape/inkscape/-/issues/5"
    assert other_host_link(gitlab + "?x=1#note_2") == gitlab
    assert other_host_link("https://gitlab.com/inkscape/inkscape/?x=1") == (
        "https://gitlab.com/inkscape/inkscape/?x=1"
    )


def test_a_phase_from_a_newer_version_is_never_the_next_phase(tmp_path: Path) -> None:
    import json

    # `next_phase: zzz` led to a `complete_phase zzz` command this version refuses.
    path = tmp_path / "progress.json"
    store = ProgressStore(path)
    for phase in JourneyPhase:
        store.complete_phase(phase)
    raw = json.loads(path.read_text())
    raw["phases"]["zzz"] = False
    path.write_text(json.dumps(raw))
    summary = store.summary()
    assert summary["next_phase"] is None
    assert summary["completion"] == f"{len(JourneyPhase)}/{len(JourneyPhase)}"
