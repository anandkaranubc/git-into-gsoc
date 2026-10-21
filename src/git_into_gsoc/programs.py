"""Find external programs (gh, claude, codex, ...) without ever running one from the
current folder.

The current folder is often a repository someone just cloned, and assistants start
the MCP server inside the project folder. Windows searches the current folder before
PATH, both in ``shutil.which`` and when a program is started by name, so a ``gh.bat``
committed to a repository would run as soon as the tool looked for a GitHub token.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _never_search_the_current_folder() -> None:
    if sys.platform == "win32":
        # Honoured by Windows itself and by shutil.which; see NeedCurrentDirectoryForExePath.
        os.environ.setdefault("NoDefaultCurrentDirectoryInExePath", "1")


def find_program(name: str) -> str | None:
    """``shutil.which`` over PATH entries that are absolute and are not the current folder."""
    _never_search_the_current_folder()
    try:
        here: Path | None = Path.cwd().resolve()
    except OSError:
        here = None
    safe: list[str] = []
    for entry in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue  # "", ".", and "bin" all mean somewhere inside the current folder
        try:
            if here is not None and Path(entry).resolve() == here:
                continue
        except OSError:
            continue
        safe.append(entry)
    return shutil.which(name, path=os.pathsep.join(safe)) if safe else None
