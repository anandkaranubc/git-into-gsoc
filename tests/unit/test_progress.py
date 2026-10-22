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


def test_unknown_phase_raises(tmp_path: Path) -> None:
    store = ProgressStore(tmp_path / "progress.json")
    try:
        store.complete_phase("not-a-phase")
        raised = False
    except ValueError:
        raised = True
    assert raised


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
    assert "could not be read" in caplog.text
    store.add_note("fresh start")
    assert store.load().notes == ["fresh start"]


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
