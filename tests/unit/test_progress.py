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


def test_mcp_progress_reports_errors_as_json(tmp_path: Path) -> None:
    from git_into_gsoc.mcp_server import gsoc_progress

    assert "Unknown phase" in gsoc_progress(action="complete_phase", phase="nope")
    assert "empty" in gsoc_progress(action="note", value="")
