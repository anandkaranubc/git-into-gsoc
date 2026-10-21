"""Persistent local progress store."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, progress_path
from git_into_gsoc.models import JourneyPhase, ProgressState

DEFAULT_PHASES = {phase.value: False for phase in JourneyPhase}


class ProgressStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or progress_path()

    def load(self) -> ProgressState:
        if not self.path.exists():
            return ProgressState(
                target_year=DEFAULT_TARGET_YEAR,
                phases=dict(DEFAULT_PHASES),
                updated_at=datetime.now(UTC),
            )
        return ProgressState.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: ProgressState) -> ProgressState:
        state.updated_at = datetime.now(UTC)
        # ensure all phases present
        phases = dict(DEFAULT_PHASES)
        phases.update(state.phases)
        state.phases = phases
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return state

    def complete_phase(self, phase: str | JourneyPhase) -> ProgressState:
        state = self.load()
        key = phase.value if isinstance(phase, JourneyPhase) else phase
        if key not in DEFAULT_PHASES:
            raise ValueError(f"Unknown phase: {key}. Expected one of {list(DEFAULT_PHASES)}")
        state.phases[key] = True
        return self.save(state)

    def set_profile(self, **fields: object) -> ProgressState:
        state = self.load()
        state.profile.update({k: v for k, v in fields.items() if v is not None})
        return self.save(state)

    def shortlist_org(self, name: str) -> ProgressState:
        state = self.load()
        if name not in state.shortlisted_orgs:
            state.shortlisted_orgs.append(name)
        return self.save(state)

    def track_repo(self, full_name: str) -> ProgressState:
        state = self.load()
        if full_name not in state.tracked_repos:
            state.tracked_repos.append(full_name)
        return self.save(state)

    def track_issue(self, issue_ref: str) -> ProgressState:
        state = self.load()
        if issue_ref not in state.tracked_issues:
            state.tracked_issues.append(issue_ref)
        return self.save(state)

    def add_contribution(self, **payload: object) -> ProgressState:
        state = self.load()
        state.contributions.append(dict(payload))
        return self.save(state)

    def add_note(self, note: str) -> ProgressState:
        state = self.load()
        state.notes.append(note)
        return self.save(state)

    def summary(self) -> dict[str, object]:
        state = self.load()
        done = sum(1 for v in state.phases.values() if v)
        total = len(state.phases)
        next_phases = [k for k, v in state.phases.items() if not v]
        return {
            "target_year": state.target_year,
            "completion": f"{done}/{total}",
            "percent": round(100.0 * done / total, 1) if total else 0.0,
            "next_phase": next_phases[0] if next_phases else None,
            "shortlisted_orgs": state.shortlisted_orgs,
            "tracked_repos": state.tracked_repos,
            "tracked_issues": state.tracked_issues,
            "contributions": len(state.contributions),
            "profile": state.profile,
            "phases": state.phases,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }
