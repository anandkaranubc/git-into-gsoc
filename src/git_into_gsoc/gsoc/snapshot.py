"""Embedded snapshot of GSoC organization data.

Two compact JSON files ship inside the package so that organization search
works on a fresh install with no network, keeps working when either upstream
source is down, and never needs the 15 MB archive just to rank organizations:

* ``org_history.json``: every organization that ever participated, with its
  archive slug and the number of accepted projects per year.
* ``official_orgs.json``: the most recent official accepted-organization list
  (name, tags, description, links, channels), used when the live site and the
  archive are both unavailable, and by ranking for the description text.

The snapshot-refresh workflow runs ``python -m git_into_gsoc.gsoc.snapshot`` every
Monday and opens a pull request when the data changed; run it by hand before a
release if that is sooner.
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
    "description",
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


# Descriptions are matched against what people say they care about; the first
# part says what an organization works on, so the rest is not needed offline.
DESCRIPTION_LIMIT = 1200


def build_official(raw_orgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # The official API lists organizations in a different order on every call; sorting
    # keeps an unchanged list byte-identical.
    kept = [{k: org.get(k) for k in _OFFICIAL_FIELDS if org.get(k) is not None} for org in raw_orgs]
    for org in kept:
        text = " ".join(str(org.get("description") or "").split())
        if len(text) > DESCRIPTION_LIMIT:
            text = text[:DESCRIPTION_LIMIT].rsplit(" ", 1)[0] + " …"
        if text:
            org["description"] = text
    return sorted(kept, key=lambda org: (str(org.get("slug") or ""), str(org.get("name") or "")))


def _write_json(path: Path, payload: dict[str, Any], *, sort_keys: bool) -> None:
    """Write the snapshot, but keep the old "generated" date when nothing else changed.

    The weekly refresh workflow opens a pull request on any difference, so an
    unchanged refresh must leave the file byte-identical.
    """
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    if isinstance(previous, dict) and "generated" in previous:
        unchanged = {k: v for k, v in previous.items() if k != "generated"} == {
            k: v for k, v in payload.items() if k != "generated"
        }
        if unchanged:
            payload = {**payload, "generated": previous["generated"]}
    path.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=sort_keys) + "\n",
        encoding="utf-8",
    )


def write_snapshot(
    *, archive: list[dict[str, Any]], official: list[dict[str, Any]], year: int, out: Path
) -> tuple[Path, Path]:
    stamp = datetime.now(UTC).date().isoformat()
    history_path = out / HISTORY_FILE
    official_path = out / OFFICIAL_FILE
    _write_json(
        history_path,
        {"generated": stamp, "organizations": build_history(archive)},
        sort_keys=True,
    )
    _write_json(
        official_path,
        {"generated": stamp, "year": year, "organizations": build_official(official)},
        sort_keys=False,
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
