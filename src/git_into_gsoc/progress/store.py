"""Persistent local progress store."""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

from pydantic import ValidationError

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, _private_dir, data_location
from git_into_gsoc.errors import InputError
from git_into_gsoc.models import JourneyPhase, LogEntry, ProgressState
from git_into_gsoc.validation import parse_issue_ref, parse_repo

DEFAULT_PHASES = {phase.value: False for phase in JourneyPhase}
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 60.0
# Windows briefly denies access to a file another process is replacing or deleting
# (a sharing violation, raised as PermissionError). A replace takes milliseconds.
BUSY_RETRIES = 40
BUSY_WAIT_SECONDS = 0.025
# Notes are re-read by every `log` listing and by assistants, so each text stays
# short enough to scan. Limits apply when saving; older, longer notes still load.
MAX_TEXT_CHARS = 2000
MAX_NAME_CHARS = 200
MAX_LINKS = 20
MAX_LINK_CHARS = 500
_LOG_TEXT_FIELDS = {
    "goal": "goal",
    "done": "done",
    "learned": "learned",
    "stuck": "stuck",
    "next_step": "next step",
}

log = logging.getLogger(__name__)
_T = TypeVar("_T")


def _mutating(method: Callable[..., _T]) -> Callable[..., _T]:
    """Hold the store's lock for a whole read-modify-write, so the CLI and an
    assistant's MCP server never overwrite each other's changes."""

    @functools.wraps(method)
    def wrapper(self: ProgressStore, *args: Any, **kwargs: Any) -> _T:
        try:
            with self._lock():
                return method(self, *args, **kwargs)
        except OSError as exc:
            raise InputError(
                f"Cannot save your progress in {self.path.parent}: {exc.strerror or exc}",
                hint="If an AI assistant ran this in a sandbox, let it write to that folder, "
                "or set GIG_DATA_DIR to a folder it may write to.",
            ) from exc

    return wrapper


def _busy(exc: OSError) -> bool:
    """A Windows sharing violation: the file is mid-replace or mid-delete elsewhere."""
    return os.name == "nt" and isinstance(exc, PermissionError)


def _retry_busy(action: Callable[[], _T]) -> _T:
    for attempt in range(BUSY_RETRIES):
        try:
            return action()
        except PermissionError as exc:
            if not _busy(exc) or attempt == BUSY_RETRIES - 1:
                raise
            time.sleep(BUSY_WAIT_SECONDS)
    raise AssertionError("unreachable")  # pragma: no cover


def _require(value: str, what: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise InputError(f"Nothing to save: {what} is empty.", hint=f"Pass the {what} as --value.")
    return cleaned


def _bounded(value: str, what: str, limit: int = MAX_TEXT_CHARS) -> str:
    if len(value) > limit:
        raise InputError(
            f"The {what} is {len(value):,} characters long; the limit is {limit:,}.",
            hint="Keep it to what happened and link to the details.",
        )
    return value


def _web_links(links: list[str]) -> list[str]:
    """Check that every link is a plain web address; a bare `github.com/...` gets https://."""
    if len(links) > MAX_LINKS:
        raise InputError(f"{len(links)} links given; the limit is {MAX_LINKS}.")
    cleaned: list[str] = []
    for raw in links:
        link = raw.strip()
        candidate = link if "://" in link else f"https://{link}"
        try:
            parsed = urlparse(candidate)
            _ = parsed.port  # "javascript:alert(1)" reads as host "javascript", port "alert(1)"
            web = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            web = web and parsed.username is None
        except ValueError:  # a port that is not a number, or an unclosed [IPv6] bracket
            web = False
        if not web or re.search(r"\s", candidate) or len(candidate) > MAX_LINK_CHARS:
            raise InputError(
                f"Not a web link: {raw!r}",
                hint="Give links as https:// addresses, separated by commas.",
            )
        if candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def _issue_key(ref: str) -> tuple[str, str, int] | str:
    try:
        owner, repo, number = parse_issue_ref(ref)
    except InputError:
        return ref.lower()
    return owner.lower(), repo.lower(), number


def other_host_link(value: str) -> str | None:
    """A project or issue link on a code host other than GitHub, tidied, or None.

    GNOME, KDE, Debian, and about one in six GSoC organizations keep their code on
    GitLab or their own servers; their links are saved as they are.
    """
    raw = (value or "").strip()
    if not raw.startswith(("https://", "http://")):
        return None
    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    path = [p for p in parsed.path.split("/") if p]
    if not host or "." not in host or host.removeprefix("www.") == "github.com" or len(path) < 2:
        return None
    return raw.split("#", 1)[0].rstrip("/").removesuffix(".git")


_OTHER_HOST_ISSUE = re.compile(r"/(?:-/)?(?:issues|merge_requests|pulls?|bugs?|tickets?)/\d+")


def _repo_key(full_name: str) -> str:
    try:
        owner, repo = parse_repo(full_name)
    except InputError:
        return full_name.lower()
    return f"{owner}/{repo}".lower()


class ProgressStore:
    """Reads and writes progress.json.

    Every change loads the file, edits it, and writes it back whole under a lock
    file, so the CLI and an assistant's MCP server never lose each other's changes.
    Reading works where writing is not allowed, and a damaged file is kept aside,
    never overwritten.
    """

    def __init__(self, path: Path | None = None) -> None:
        # Created on the first save, so reading works where writing is not allowed.
        self.path = path or (data_location() / "progress.json")

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        """Cross-platform exclusive lock: a lock file created with O_EXCL."""
        _private_dir(self.path.parent)
        lock = self.path.with_name(self.path.name + ".lock")
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                break
            except (FileExistsError, PermissionError) as exc:
                if isinstance(exc, PermissionError) and not _busy(exc):
                    raise  # a folder we may not write to; waiting will not help
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
            text = _retry_busy(lambda: self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            # Unreadable is not damaged: moving the file aside would hide the person's
            # progress behind a fresh, empty one.
            raise InputError(
                f"Cannot read {self.path}: {exc.strerror or exc}",
                hint="Check the file's permissions, or close other programs using it.",
            ) from exc
        try:
            state = ProgressState.model_validate_json(text)
        except (ValidationError, ValueError) as exc:
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
        # A file saved before a phase was added lacks it; every phase is written.
        phases = dict(DEFAULT_PHASES)
        phases.update(state.phases)
        state.phases = phases
        _private_dir(self.path.parent)
        # Write a sibling temp file, then rename over the old one: a crash or a
        # concurrent reader never sees a half-written progress.json.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".progress-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(state.model_dump_json(indent=2))
            if os.name == "posix":
                os.chmod(tmp, 0o600)
            _retry_busy(lambda: os.replace(tmp, self.path))
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
        for field, label in _LOG_TEXT_FIELDS.items():
            _bounded(getattr(entry, field), label)
        entry.links = _web_links(entry.links)
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
        name = _bounded(_require(name, "organization name"), "organization name", MAX_NAME_CHARS)
        state = self.load()
        if name.lower() not in {org.lower() for org in state.shortlisted_orgs}:
            state.shortlisted_orgs.append(name)
        return self.save(state)

    @_mutating
    def track_repo(self, full_name: str) -> ProgressState:
        link = other_host_link(_require(full_name, "repository"))
        if link:
            full_name = link
        else:
            owner, repo = parse_repo(full_name)
            full_name = f"{owner}/{repo}"
        state = self.load()
        if _repo_key(full_name) not in {_repo_key(r) for r in state.tracked_repos}:
            state.tracked_repos.append(full_name)
        return self.save(state)

    @_mutating
    def track_issue(self, issue_ref: str) -> ProgressState:
        issue_ref = _require(issue_ref, "issue reference")
        link = other_host_link(issue_ref)
        if link and _OTHER_HOST_ISSUE.search(link):
            state = self.load()
            if link.lower() not in {i.lower() for i in state.tracked_issues}:
                state.tracked_issues.append(link)
            return self.save(state)
        try:
            owner, repo, number = parse_issue_ref(issue_ref)
        except InputError as exc:
            raise InputError(
                f"Not an issue or pull request: {issue_ref!r}",
                hint="Use owner/repo#123, the GitHub link, or the full link to an issue "
                "on GitLab or another code host.",
            ) from exc
        kind = "pull" if re.search(r"/pull/\d", issue_ref) else "issues"
        canonical = f"https://github.com/{owner}/{repo}/{kind}/{number}"
        state = self.load()
        if _issue_key(canonical) not in {_issue_key(i) for i in state.tracked_issues}:
            state.tracked_issues.append(canonical)
        return self.save(state)

    @_mutating
    def add_contribution(self, **payload: object) -> ProgressState:
        state = self.load()
        state.contributions.append(dict(payload))
        return self.save(state)

    @_mutating
    def add_note(self, note: str) -> ProgressState:
        note = _bounded(_require(note, "note"), "note")
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
