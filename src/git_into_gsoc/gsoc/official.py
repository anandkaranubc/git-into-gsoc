"""Client for the public JSON endpoints behind summerofcode.withgoogle.com.

These power the official site. They are unauthenticated and undocumented, so
every caller must degrade gracefully (archive data, embedded snapshot) when
they change or are unreachable.
"""

from __future__ import annotations

from typing import Any

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.http_client import CachedHttpClient, NotFoundError

PROGRAM_TTL_SECONDS = 6 * 3600


class OfficialGSoCClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http: CachedHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)

    def _url(self, path: str) -> str:
        return f"{self.settings.gsoc_official_api_url.rstrip('/')}/{path.lstrip('/')}"

    def program(self, year: int) -> dict[str, Any] | None:
        """Program metadata and milestones, or None if Google hasn't published `year`."""
        try:
            data = self.http.get_json(self._url(f"program/{int(year)}/"), ttl=PROGRAM_TTL_SECONDS)
        except NotFoundError:
            return None
        if isinstance(data, dict) and isinstance(data.get("milestones"), list):
            return data
        return None

    def organizations(self, year: int) -> list[dict[str, Any]] | None:
        """Accepted organizations for `year`, or None if not published."""
        try:
            data = self.http.get_json(
                self._url(f"program/{int(year)}/organizations/"),
                ttl=self.settings.archive_ttl_seconds,
            )
        except NotFoundError:
            return None
        return data if isinstance(data, list) and data else None
