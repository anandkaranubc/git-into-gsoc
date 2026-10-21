"""Persistent local progress store."""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, progress_path
from git_into_gsoc.errors import InputError
from git_into_gsoc.models import JourneyPhase, LogEntry, ProgressState

DEFAULT_PHASES = {phase.value: False for phase in JourneyPhase}


def _require(value: str, what: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise InputError(f"Nothing to save: {what} is empty.", hint=f"Pass the {what} as --value.")
    return cleaned


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
        state = ProgressState.model_validate_json(self.path.read_text(encoding="utf-8"))
        state.phases = {**DEFAULT_PHASES, **state.phases}  # files saved before a phase was added
        return state

    def save(self, state: ProgressState) -> ProgressState:
        state.updated_at = datetime.now(UTC)
        # ensure all phases present
        phases = dict(DEFAULT_PHASES)
        phases.update(state.phases)
        state.phases = phases
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        if os.name == "posix":
            with contextlib.suppress(OSError):
                self.path.chmod(0o600)
        return state

    def complete_phase(self, phase: str | JourneyPhase) -> ProgressState:
        state = self.load()
        key = phase.value if isinstance(phase, JourneyPhase) else (phase or "").strip().lower()
        if key not in DEFAULT_PHASES:
            raise InputError(
                f"Unknown phase: {phase!r}",
                hint="Choose one of: " + ", ".join(DEFAULT_PHASES),
            )
        state.phases[key] = True
        return self.save(state)

    def set_profile(self, **fields: object) -> ProgressState:
        state = self.load()
        state.profile.update({k: v for k, v in fields.items() if v is not None})
        return self.save(state)

    def profile(self) -> dict[str, Any]:
        return dict(self.load().profile)

    def set_issue_status(self, ref: str, status: str) -> ProgressState:
        state = self.load()
        state.issue_status[ref] = status
        return self.save(state)

    def mark_checked(self, statuses: dict[str, str], at: datetime) -> ProgressState:
        state = self.load()
        state.issue_status.update(statuses)
        state.last_checked_at = at
        return self.save(state)

    def add_log(self, entry: LogEntry) -> ProgressState:
        if entry.is_empty():
            raise InputError(
                "Nothing to save: the note is empty.",
                hint="Give at least one of --goal, --done, --links, --learned, --stuck, --next.",
            )
        state = self.load()
        state.weekly_log.append(entry)
        return self.save(state)

    def recent_logs(self, limit: int = 5) -> list[LogEntry]:
        # Newest first; entries saved within the same clock tick keep insertion order,
        # so the index breaks ties (Windows timestamps are coarse).
        indexed = list(enumerate(self.load().weekly_log))
        indexed.sort(key=lambda pair: (pair[1].at, pair[0]), reverse=True)
        return [entry for _, entry in indexed][: max(1, limit)]

    def shortlist_org(self, name: str) -> ProgressState:
        name = _require(name, "organization name")
        state = self.load()
        if name not in state.shortlisted_orgs:
            state.shortlisted_orgs.append(name)
        return self.save(state)

    def track_repo(self, full_name: str) -> ProgressState:
        full_name = _require(full_name, "repository")
        state = self.load()
        if full_name not in state.tracked_repos:
            state.tracked_repos.append(full_name)
        return self.save(state)

    def track_issue(self, issue_ref: str) -> ProgressState:
        issue_ref = _require(issue_ref, "issue reference")
        state = self.load()
        if issue_ref not in state.tracked_issues:
            state.tracked_issues.append(issue_ref)
        return self.save(state)

    def add_contribution(self, **payload: object) -> ProgressState:
        state = self.load()
        state.contributions.append(dict(payload))
        return self.save(state)

    def add_note(self, note: str) -> ProgressState:
        note = _require(note, "note")
        state = self.load()
        state.notes.append(note)
        return self.save(state)

    def summary(self) -> dict[str, object]:
        state = self.load()
        done = sum(1 for v in state.phases.values() if v)
        total = len(state.phases)
        next_phases = [k for k, v in state.phases.items() if not v]
        last_log = max((e.at for e in state.weekly_log), default=None)
        return {
            "log_entries": len(state.weekly_log),
            "last_log_days_ago": (datetime.now(UTC) - last_log).days if last_log else None,
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
