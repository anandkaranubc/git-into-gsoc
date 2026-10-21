"""Persistent local progress store."""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import tempfile
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, progress_path
from git_into_gsoc.errors import InputError
from git_into_gsoc.models import JourneyPhase, LogEntry, ProgressState

DEFAULT_PHASES = {phase.value: False for phase in JourneyPhase}
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 60.0

log = logging.getLogger(__name__)
_T = TypeVar("_T")


def _mutating(method: Callable[..., _T]) -> Callable[..., _T]:
    """Hold the store's lock for a whole read-modify-write, so the CLI and an
    assistant's MCP server never overwrite each other's changes."""

    @functools.wraps(method)
    def wrapper(self: ProgressStore, *args: Any, **kwargs: Any) -> _T:
        with self._lock():
            return method(self, *args, **kwargs)

    return wrapper


def _require(value: str, what: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise InputError(f"Nothing to save: {what} is empty.", hint=f"Pass the {what} as --value.")
    return cleaned


class ProgressStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or progress_path()

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        """Cross-platform exclusive lock: a lock file created with O_EXCL."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name + ".lock")
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                break
            except FileExistsError:
                with contextlib.suppress(OSError):
                    if time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS:
                        lock.unlink()  # left behind by a process that crashed
                        continue
                if time.monotonic() > deadline:
                    raise InputError(
                        f"Another git-into-gsoc process is saving progress ({lock}).",
                        hint="Wait a moment and retry; delete the .lock file if no other "
                        "git-into-gsoc command is running.",
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                lock.unlink()

    def load(self) -> ProgressState:
        if not self.path.exists():
            return self._fresh()
        try:
            state = ProgressState.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError, OSError) as exc:
            return self._recover(exc)
        state.phases = {**DEFAULT_PHASES, **state.phases}  # files saved before a phase was added
        return state

    def _fresh(self) -> ProgressState:
        return ProgressState(
            target_year=DEFAULT_TARGET_YEAR,
            phases=dict(DEFAULT_PHASES),
            updated_at=datetime.now(UTC),
        )

    def _recover(self, exc: Exception) -> ProgressState:
        """Keep a damaged file for the user and carry on with a fresh one."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        backup = self.path.with_name(f"{self.path.stem}.damaged-{stamp}{self.path.suffix}")
        with contextlib.suppress(OSError):
            self.path.replace(backup)
        log.warning(
            "progress.json could not be read (%s); it was kept as %s and a fresh one "
            "will be saved. Copy entries back from the kept file if you need them.",
            type(exc).__name__,
            backup,
        )
        return self._fresh()

    def save(self, state: ProgressState) -> ProgressState:
        state.updated_at = datetime.now(UTC)
        # ensure all phases present
        phases = dict(DEFAULT_PHASES)
        phases.update(state.phases)
        state.phases = phases
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write a sibling temp file, then rename over the old one: a crash or a
        # concurrent reader never sees a half-written progress.json.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".progress-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(state.model_dump_json(indent=2))
            if os.name == "posix":
                os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        return state

    @_mutating
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

    @_mutating
    def set_profile(self, **fields: object) -> ProgressState:
        state = self.load()
        state.profile.update({k: v for k, v in fields.items() if v is not None})
        return self.save(state)

    def profile(self) -> dict[str, Any]:
        return dict(self.load().profile)

    @_mutating
    def set_issue_status(self, ref: str, status: str) -> ProgressState:
        state = self.load()
        state.issue_status[ref] = status
        return self.save(state)

    @_mutating
    def mark_checked(self, statuses: dict[str, str], at: datetime) -> ProgressState:
        state = self.load()
        state.issue_status.update(statuses)
        state.last_checked_at = at
        return self.save(state)

    @_mutating
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

    @_mutating
    def shortlist_org(self, name: str) -> ProgressState:
        name = _require(name, "organization name")
        state = self.load()
        if name not in state.shortlisted_orgs:
            state.shortlisted_orgs.append(name)
        return self.save(state)

    @_mutating
    def track_repo(self, full_name: str) -> ProgressState:
        full_name = _require(full_name, "repository")
        state = self.load()
        if full_name not in state.tracked_repos:
            state.tracked_repos.append(full_name)
        return self.save(state)

    @_mutating
    def track_issue(self, issue_ref: str) -> ProgressState:
        issue_ref = _require(issue_ref, "issue reference")
        state = self.load()
        if issue_ref not in state.tracked_issues:
            state.tracked_issues.append(issue_ref)
        return self.save(state)

    @_mutating
    def add_contribution(self, **payload: object) -> ProgressState:
        state = self.load()
        state.contributions.append(dict(payload))
        return self.save(state)

    @_mutating
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
