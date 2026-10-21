"""The official GSoC archive: completed projects with mentor names, per year.

summerofcode.withgoogle.com serves the archive its own site reads. It is the
only public source that names who mentored which project at which
organization, so it answers "who should I talk to, and who comes back every
year" without guessing. Only passed projects are published; counts here are
of completed work, not of all accepted projects.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from git_into_gsoc.config import Settings, get_settings
from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.text import clean_untrusted

PROJECTS_TTL_SECONDS = 86400
_RESERVED = {"orgs", "topics", "settings", "features", "sponsors", "apps", "marketplace"}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def github_repo_of(url: str | None) -> str | None:
    """owner/repo when a project's code URL points at a GitHub repository."""
    if not url:
        return None
    parsed = urlparse(str(url).strip())
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host != "github.com":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() in _RESERVED:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def _split_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        for part in re.split(r"\s*[,/;]\s*", str(tag)):
            part = part.strip().lower()
            if part and part not in out:
                out.append(part)
    return out


def summarize_mentors(
    projects_by_year: dict[int, list[dict[str, Any]]],
    *,
    org_slug: str | None,
    org_name: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Mentors, repositories and tags of one organization's completed projects."""
    wanted_slug = (org_slug or "").lower()
    wanted_name = normalize_name(org_name)
    years_seen: set[int] = set()
    per_mentor: dict[str, dict[str, Any]] = {}
    repos: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    mentors_per_year: dict[str, set[str]] = {}
    total = 0
    for year in sorted(projects_by_year):
        for project in projects_by_year[year]:
            slug = str(project.get("organization_slug") or "").lower()
            name = normalize_name(str(project.get("organization_name") or ""))
            if not ((wanted_slug and slug == wanted_slug) or (wanted_name and name == wanted_name)):
                continue
            total += 1
            years_seen.add(year)
            title = clean_untrusted(project.get("title"), limit=120)
            repo = github_repo_of(project.get("project_code_url"))
            if repo:
                repos[repo] += 1
            for tag in _split_tags(project.get("tech_tags") or []):
                tags[tag] += 1
            for raw in project.get("mentor_names") or []:
                mentor = clean_untrusted(raw, limit=80)
                if not mentor:
                    continue
                entry = per_mentor.setdefault(
                    mentor, {"name": mentor, "years": set(), "projects": 0, "recent_projects": []}
                )
                entry["years"].add(year)
                entry["projects"] += 1
                entry["recent_projects"].append(
                    {"year": year, "title": title, "code_url": project.get("project_code_url")}
                )
                mentors_per_year.setdefault(str(year), set()).add(mentor)
    mentors = []
    for entry in per_mentor.values():
        recent = sorted(entry["recent_projects"], key=lambda p: -int(p["year"]))[:3]
        mentors.append(
            {
                "name": entry["name"],
                "years": sorted(entry["years"]),
                "projects": entry["projects"],
                "recent_projects": recent,
            }
        )
    mentors.sort(key=lambda m: (-len(m["years"]), -m["projects"], m["name"]))
    returning = sum(1 for m in mentors if len(m["years"]) >= 2)
    return {
        "org": org_name,
        "years_covered": sorted(years_seen),
        "projects": total,
        "mentors_total": len(mentors),
        "returning_mentors": returning,
        "mentors_per_year": {y: len(v) for y, v in sorted(mentors_per_year.items())},
        "mentors": mentors[:limit],
        "repos_touched": [{"repo": r, "projects": n} for r, n in repos.most_common(10)],
        "top_tech_tags": [{"tag": t, "projects": n} for t, n in tags.most_common(10)],
    }


PROPOSAL_ARCHIVES = (
    "SammanSarkar/GSoC_archive_2025",
    "satwiksps/GSoC_archive_2026",
    "pavanjoshi914/GSoC_archive",
    "Google-Summer-of-Code-Archive/gsoc-proposals-archive",
    "COPS-IITBHU/GSoC-Accepted-Proposals",
)


def proposal_folders(
    tree_of: Callable[[str, str], list[dict[str, Any]]], org_name: str, *, limit: int = 6
) -> list[dict[str, Any]]:
    """Folders in community proposal archives that hold proposals for the organization.

    A folder counts when its own name matches the organization, or when it holds
    files whose names start with the organization (archives that sort by year
    name each file "Org - Year - Author"). `tree_of(owner, repo)` returns a
    recursive tree listing. Results link to the folder on GitHub; nothing is
    downloaded, because the files hold personal data.
    """
    wanted = normalize_name(org_name)
    if len(wanted) < 4:
        return []
    found: list[dict[str, Any]] = []
    for full in PROPOSAL_ARCHIVES:
        owner, repo = full.split("/", 1)
        entries = tree_of(owner, repo)
        folders = [str(e["path"]) for e in entries if e.get("type") == "tree" and e.get("path")]
        blobs = [str(e["path"]) for e in entries if e.get("type") == "blob" and e.get("path")]
        counts: dict[str, int] = {}
        for folder in folders:
            name = normalize_name(folder.rsplit("/", 1)[-1])
            if name == wanted or (len(name) >= 4 and (name in wanted or wanted in name)):
                files = sum(1 for b in blobs if b.startswith(folder + "/"))
                if files:
                    counts[folder] = files
        matched = tuple(f + "/" for f in counts)
        for blob in blobs:
            folder, _, base = blob.rpartition("/")
            if not folder or blob.startswith(matched):
                continue
            if normalize_name(base).startswith(wanted):
                counts[folder] = counts.get(folder, 0) + 1
        for folder, files in counts.items():
            found.append(
                {
                    "repo": full,
                    "path": folder,
                    "files": files,
                    "url": f"https://github.com/{full}/tree/HEAD/{folder}",
                }
            )
    found.sort(key=lambda f: (-f["files"], f["repo"], f["path"]))
    return found[:limit]


class ArchiveClient:
    def __init__(
        self, settings: Settings | None = None, http: CachedHttpClient | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)

    def _url(self, path: str) -> str:
        base = self.settings.gsoc_official_api_url.rstrip("/")
        return f"{base}/archive/{path.lstrip('/')}"

    def programs(self) -> list[dict[str, Any]]:
        try:
            data = self.http.get_json(self._url("programs/"), ttl=PROJECTS_TTL_SECONDS)
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def archived_years(self) -> list[int]:
        years = []
        for program in self.programs():
            try:
                years.append(int(str(program.get("year") or program.get("slug") or "")))
            except (TypeError, ValueError):
                continue
        return sorted(set(years), reverse=True)

    def projects(self, year: int) -> list[dict[str, Any]]:
        """Every completed project of one archived year (about 2 MB, cached for a day)."""
        try:
            data = self.http.get_json(
                self._url(f"programs/{int(year)}/projects/"), ttl=PROJECTS_TTL_SECONDS
            )
        except HttpError:
            return []
        return data if isinstance(data, list) else []

    def projects_by_year(self, *, years: int = 3) -> dict[int, list[dict[str, Any]]]:
        recent = self.archived_years()[:years]
        return {year: self.projects(year) for year in recent}
