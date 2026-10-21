"""Links to the project's GitHub issue forms, filled in with what helps a maintainer.

Nothing is sent from here. The link opens a form in the browser, the person reads and
edits it, and only their own Submit click posts anything. The prefilled text is the tool
version, the Python version, and the operating system name: no paths, usernames, tokens,
or saved progress.
"""

from __future__ import annotations

import platform
import sys
from urllib.parse import urlencode

from git_into_gsoc import __version__
from git_into_gsoc.config import PROJECT_URL

# Template file name and the id of the form field that holds the setup details.
FORMS = {
    "feedback": ("feedback.yml", "setup"),
    "bug": ("bug_report.yml", "env"),
}


def system_summary() -> str:
    """One line a maintainer can act on, with nothing that identifies the person."""
    python = ".".join(str(part) for part in sys.version_info[:3])
    return f"git-into-gsoc {__version__}, Python {python}, {platform.system()} {platform.release()}"


def form_url(kind: str = "feedback") -> str:
    template, field = FORMS[kind]
    query = urlencode({"template": template, field: system_summary()})
    return f"{PROJECT_URL.rstrip('/')}/issues/new?{query}"
