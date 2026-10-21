"""Embedded snapshot of GSoC organization data.

Two compact JSON files ship inside the package so that organization search
works on a fresh install with no network, keeps working when either upstream
source is down, and never needs the 15 MB archive just to rank organizations:

* ``org_history.json``: every organization that ever participated, with its
  archive slug and the number of accepted projects per year.
* ``official_orgs.json``: the most recent official accepted-organization list
  (name, tags, links, channels), used only when the live site and the
  archive are both unavailable.

Refresh before a release with ``python -m git_into_gsoc.gsoc.snapshot``.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

HISTORY_FILE = "org_history.json"
OFFICIAL_FILE = "official_orgs.json"
_OFFICIAL_FIELDS = (
    "name",
    "slug",
    "tagline",
    "categories",
    "topic_tags",
    "tech_tags",
    "ideas_link",
    "contributor_guidance_url",
    "source_code",
    "website_url",
    "license",
    "direct_comm_methods",
    "social_comm_methods",
)


def _data_dir() -> Path:
    return Path(str(resources.files("git_into_gsoc").joinpath("data")))


@lru_cache(maxsize=1)
def load_history() -> dict[str, Any]:
    """``{"generated": date, "organizations": {name: {"slug": str, "years": {year: {...}}}}}``."""
    return _read(HISTORY_FILE)


@lru_cache(maxsize=1)
def load_official() -> dict[str, Any]:
    """``{"generated": date, "year": int, "organizations": [raw official records]}``."""
    return _read(OFFICIAL_FILE)


def _read(name: str) -> dict[str, Any]:
    path = _data_dir() / name
    if not path.is_file():
        return {"generated": None, "organizations": {} if name == HISTORY_FILE else []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_history(archive: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Strip the archive down to slug + projects per year (drops project lists)."""
    out: dict[str, dict[str, Any]] = {}
    for raw in archive:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        years = {
            str(year): {"num_projects": int((data or {}).get("num_projects") or 0)}
            for year, data in (raw.get("years") or {}).items()
            if str(year).isdigit()
        }
        entry: dict[str, Any] = {"years": years}
        url = raw.get("projects_url") or next(
            (str((d or {}).get("projects_url") or "") for d in (raw.get("years") or {}).values()),
            "",
        )
        if url:
            entry["projects_url"] = url
        out[name] = entry
    return out


def build_official(raw_orgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: org.get(k) for k in _OFFICIAL_FIELDS if org.get(k) is not None} for org in raw_orgs]


def write_snapshot(
    *, archive: list[dict[str, Any]], official: list[dict[str, Any]], year: int, out: Path
) -> tuple[Path, Path]:
    stamp = datetime.now(UTC).date().isoformat()
    history_path = out / HISTORY_FILE
    official_path = out / OFFICIAL_FILE
    history_path.write_text(
        json.dumps(
            {"generated": stamp, "organizations": build_history(archive)},
            separators=(",", ":"),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    official_path.write_text(
        json.dumps(
            {"generated": stamp, "year": year, "organizations": build_official(official)},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return history_path, official_path


def main(argv: list[str] | None = None) -> int:
    """Refresh the embedded snapshot from live sources (maintainers only)."""
    from git_into_gsoc.config import LATEST_ARCHIVED_YEAR, get_settings
    from git_into_gsoc.gsoc.official import OfficialGSoCClient
    from git_into_gsoc.http_client import CachedHttpClient

    args = list(sys.argv[1:] if argv is None else argv)
    year = int(args[0]) if args else LATEST_ARCHIVED_YEAR
    settings = get_settings()
    http = CachedHttpClient(settings)
    official = OfficialGSoCClient(settings, http).organizations(year)
    if not official:
        print(f"No official organization list published for {year}", file=sys.stderr)
        return 1
    archive = http.get_json(f"{settings.gsoc_orgs_api_url.rstrip('/')}/organizations.json", ttl=0)
    if isinstance(archive, dict):
        archive = archive.get("organizations")
    history_path, official_path = write_snapshot(
        archive=list(archive or []), official=official, year=year, out=_data_dir()
    )
    print(f"wrote {history_path} ({history_path.stat().st_size // 1024} KiB)")
    print(f"wrote {official_path} ({official_path.stat().st_size // 1024} KiB)")
    load_history.cache_clear()
    load_official.cache_clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
