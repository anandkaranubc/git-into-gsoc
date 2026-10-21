from __future__ import annotations

from pathlib import Path

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
