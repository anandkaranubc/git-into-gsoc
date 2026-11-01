"""One parser for the ISO 8601 timestamps GitHub, GitLab and the GSoC pages return."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_iso(value: Any) -> datetime | None:
    """An aware UTC datetime, or None when the value is empty or not a timestamp.

    A stamp without a zone is read as UTC, which is what every source here sends.
    """
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
