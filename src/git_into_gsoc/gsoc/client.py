"""Mentoring-organization intelligence.

Two sources are merged:

* the **official** accepted-org list for a year (authoritative: source code,
  ideas page, contributor guidance, contact channels), and
* the community **archive** (api.gsocorganizations.dev) for multi-year history,
  slot counts, and past accepted project titles.

When the target year's orgs are not announced yet, the most recent official
year is used and labelled as such.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

from git_into_gsoc.config import LATEST_ARCHIVED_YEAR, Settings, get_settings
from git_into_gsoc.gsoc.official import OfficialGSoCClient
from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.models import ContactChannel, OrgCatalog, OrgSummary, PastProject
from git_into_gsoc.scoring.org_match import canonical, mentions, score_org_match

_GITHUB_RESERVED = {
    "orgs",
    "topics",
    "settings",
    "features",
    "sponsors",
    "apps",
    "marketplace",
    "about",
    "collections",
    "explore",
}
_CHANNEL_KINDS = {"chat", "mailingList", "email", "blog", "irc", "forum"}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _clean_text(value: str | None, limit: int = 280) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def github_refs(source_code: str | None, *others: str | None) -> tuple[list[str], list[str]]:
    """Extract GitHub orgs (from any URL) and repos (from the source-code URL only)."""
    orgs: list[str] = []
    repos: list[str] = []
    for index, value in enumerate((source_code, *others)):
        if not value:
            continue
        parsed = urlparse(str(value).strip())
        host = (parsed.netloc or "").lower().removeprefix("www.")
        parts = [p for p in parsed.path.split("/") if p]
        if host == "github.com" and parts:
            owner = parts[0]
            if owner.lower() in _GITHUB_RESERVED:
                continue
            orgs.append(owner)
            if index == 0 and len(parts) >= 2:
                repos.append(f"{owner}/{parts[1].removesuffix('.git')}")
        elif host.endswith(".github.io"):
            orgs.append(host.split(".")[0])
    return _dedupe(orgs)[:5], _dedupe(repos)[:5]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def _archive_slug(raw: dict[str, Any]) -> str | None:
    url = raw.get("projects_url") or ""
    for year_data in (raw.get("years") or {}).values():
        url = url or (year_data or {}).get("projects_url") or ""
    match = re.search(r"/organizations/([a-z0-9-]+)/?$", url)
    return match.group(1) if match else None


class GSoCClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http: CachedHttpClient | None = None,
        official: OfficialGSoCClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)
        self.official = official or OfficialGSoCClient(self.settings, self.http)
        self._archive: list[dict[str, Any]] | None = None
        self._history: dict[str, dict[str, Any]] | None = None
        self._catalogs: dict[int, tuple[OrgCatalog, list[OrgSummary]]] = {}
        self._search_text: dict[str, str] = {}

    # ------------------------------------------------------------- raw sources

    def _archive_url(self, name: str) -> str:
        return f"{self.settings.gsoc_orgs_api_url.rstrip('/')}/{name}"

    def list_all_organizations(self) -> list[dict[str, Any]]:
        if self._archive is None:
            data = self.http.get_json(
                self._archive_url("organizations.json"), ttl=self.settings.archive_ttl_seconds
            )
            if isinstance(data, dict):
                data = data.get("organizations")
            self._archive = list(data) if isinstance(data, list) else []
        return self._archive

    def list_year_organizations(self, year: int | None = None) -> list[dict[str, Any]]:
        year = year or LATEST_ARCHIVED_YEAR
        data = self.http.get_json(
            self._archive_url(f"{int(year)}.json"), ttl=self.settings.archive_ttl_seconds
        )
        if isinstance(data, dict):
            data = data.get("organizations")
        return list(data) if isinstance(data, list) else []

    def _history_index(self) -> dict[str, dict[str, Any]]:
        if self._history is None:
            self._history = {}
            for raw in self.list_all_organizations():
                self._history[normalize_name(raw.get("name") or "")] = raw
                slug = _archive_slug(raw)
                if slug:
                    self._history.setdefault(f"slug:{slug}", raw)
        return self._history

    def _history_for(self, name: str, slug: str | None = None) -> dict[str, Any] | None:
        index = self._history_index()
        return index.get(normalize_name(name)) or (index.get(f"slug:{slug}") if slug else None)

    # ----------------------------------------------------------------- catalog

    def catalog(self, year: int | None = None) -> tuple[OrgCatalog, list[OrgSummary]]:
        """Accepted orgs for `year`, or the most recent year that has data."""
        target = int(year or self.settings.target_year)
        if target not in self._catalogs:
            self._catalogs[target] = self._build_catalog(target)
        return self._catalogs[target]

    def _build_catalog(self, target: int) -> tuple[OrgCatalog, list[OrgSummary]]:
        newest_known = min(target - 1, LATEST_ARCHIVED_YEAR)
        candidates = [target, *range(newest_known, newest_known - 3, -1)]
        for ref in dict.fromkeys(candidates):
            try:
                official = self.official.organizations(ref)
            except HttpError:
                break
            if official:
                orgs = [self._from_official(raw, ref) for raw in official]
                note = (
                    f"Official {ref} accepted organizations."
                    if ref == target
                    else f"{target} orgs are not announced yet; showing official {ref} "
                    "participants, the best predictor of who returns."
                )
                return OrgCatalog(year=ref, source="official", note=note, count=len(orgs)), orgs

        ref = min(target, LATEST_ARCHIVED_YEAR)
        orgs = [self._from_archive(raw, ref) for raw in self.list_year_organizations(ref)]
        note = f"Archive copy of the {ref} org list (official site unavailable)."
        if ref != target:
            note += f" {target} orgs are not announced yet."
        return OrgCatalog(year=ref, source="archive", note=note, count=len(orgs)), orgs

    def _history_fields(self, hist: dict[str, Any] | None, year: int) -> dict[str, Any]:
        years_obj = (hist or {}).get("years") or {}
        projects_by_year: dict[int, int] = {}
        for key, value in years_obj.items():
            try:
                projects_by_year[int(key)] = int((value or {}).get("num_projects") or 0)
            except (TypeError, ValueError):
                continue
        years = sorted({*projects_by_year, year})
        latest_counted = max((y for y, n in projects_by_year.items() if n), default=None)
        return {
            "years_active": years,
            "latest_year": latest_counted or year,
            "num_projects_latest": projects_by_year.get(latest_counted or year, 0),
            "projects_by_year": dict(sorted(projects_by_year.items())),
        }

    def _from_official(self, raw: dict[str, Any], year: int) -> OrgSummary:
        name = str(raw.get("name") or "Unknown")
        slug = raw.get("slug")
        hist = self._history_for(name, slug)
        channels = [
            ContactChannel(kind=str(c.get("name")), value=str(c.get("value")))
            for c in [
                *(raw.get("direct_comm_methods") or []),
                *(raw.get("social_comm_methods") or []),
            ]
            if c.get("value") and c.get("name") in _CHANNEL_KINDS
        ]
        orgs, repos = github_refs(
            raw.get("source_code"), raw.get("ideas_link"), raw.get("contributor_guidance_url")
        )
        summary = OrgSummary(
            name=name,
            slug=slug,
            description=_clean_text(raw.get("tagline") or raw.get("description")),
            url=raw.get("website_url"),
            category=", ".join(raw.get("categories") or []) or None,
            topics=list(raw.get("topic_tags") or []),
            technologies=list(raw.get("tech_tags") or []),
            license=raw.get("license"),
            ideas_url=raw.get("ideas_link"),
            guide_url=raw.get("contributor_guidance_url"),
            source_code=raw.get("source_code"),
            github_orgs=orgs,
            github_repos=repos,
            channels=channels,
            official=True,
            **self._history_fields(hist, year),
        )
        self._search_text[name] = _clean_text(raw.get("description"), 2000)
        return summary

    def _from_archive(self, raw: dict[str, Any], year: int) -> OrgSummary:
        name = str(raw.get("name") or "Unknown")
        hist = self._history_for(name) or raw
        channels = [
            ContactChannel(kind=kind, value=str(raw.get(key)))
            for key, kind in (
                ("irc_channel", "chat"),
                ("mailing_list", "mailingList"),
                ("contact_email", "email"),
                ("blog_url", "blog"),
            )
            if raw.get(key)
        ]
        orgs, repos = github_refs(
            None, raw.get("ideas_url"), raw.get("guide_url"), raw.get("url"), raw.get("blog_url")
        )
        fields = self._history_fields(hist, year)
        if raw.get("num_projects") and not fields["projects_by_year"].get(year):
            fields["projects_by_year"][year] = int(raw["num_projects"])
            fields["num_projects_latest"] = int(raw["num_projects"])
            fields["latest_year"] = year
        summary = OrgSummary(
            name=name,
            slug=_archive_slug(raw),
            description=_clean_text(raw.get("description")),
            url=raw.get("url"),
            category=raw.get("category"),
            topics=list(raw.get("topics") or []),
            technologies=list(raw.get("technologies") or []),
            ideas_url=raw.get("ideas_url") or None,
            guide_url=raw.get("guide_url") or None,
            github_orgs=orgs,
            github_repos=repos,
            channels=channels,
            **fields,
        )
        return summary

    # ------------------------------------------------------------------ search

    def search_organizations(
        self,
        *,
        query: str | None = None,
        technologies: list[str] | None = None,
        topics: list[str] | None = None,
        category: str | None = None,
        year: int | None = None,
        limit: int = 15,
    ) -> tuple[OrgCatalog, list[OrgSummary]]:
        catalog, orgs = self.catalog(year)
        ranked: list[OrgSummary] = []
        for org in orgs:
            result = score_org_match(
                org,
                query=query or "",
                technologies=technologies,
                topics=topics,
                category=category or "",
                reference_year=catalog.year,
                search_text=self._search_text.get(org.name, ""),
            )
            if not result.relevant:
                continue
            ranked.append(
                org.model_copy(
                    update={"match_score": result.score, "match_reasons": result.reasons}
                )
            )
        ranked.sort(
            key=lambda o: (-o.match_score, -o.num_projects_latest, -len(o.years_active), o.name)
        )
        return catalog, ranked[: max(1, limit)]

    def get_organization(self, name: str, *, year: int | None = None) -> OrgSummary | None:
        needle = normalize_name(name)
        if not needle:
            return None
        _, orgs = self.catalog(year)
        org = next((o for o in orgs if normalize_name(o.name) == needle or o.slug == name), None)
        org = org or next((o for o in orgs if needle in normalize_name(o.name)), None)
        if org is None:
            hist = self._history_for(name) or next(
                (
                    raw
                    for raw in self.list_all_organizations()
                    if needle in normalize_name(raw.get("name") or "")
                ),
                None,
            )
            if hist is None:
                return None
            years = sorted(int(y) for y in (hist.get("years") or {}))
            org = self._from_archive(hist, years[-1] if years else LATEST_ARCHIVED_YEAR)
        projects = self.search_projects(org=org.name, limit=10)
        return org.model_copy(update={"recent_projects": projects})

    def search_projects(
        self,
        query: str | None = None,
        *,
        org: str | None = None,
        since: int | None = None,
        limit: int = 20,
    ) -> list[PastProject]:
        """Search accepted projects from past years (titles + short descriptions)."""
        tokens = [canonical(t) for t in (query or "").split() if len(t) > 1]
        org_key = normalize_name(org) if org else None
        results: list[PastProject] = []
        for raw in self.list_all_organizations():
            org_name = str(raw.get("name") or "")
            if org_key and org_key not in normalize_name(org_name):
                continue
            for year_key, year_data in (raw.get("years") or {}).items():
                try:
                    year = int(year_key)
                except (TypeError, ValueError):
                    continue
                if since and year < since:
                    continue
                for project in (year_data or {}).get("projects") or []:
                    title = str(project.get("title") or "")
                    summary = _clean_text(project.get("short_description"), 240)
                    score = float(year - 2000) / 100
                    if tokens:
                        title_hits = sum(1 for t in tokens if mentions(title, t))
                        text_hits = sum(1 for t in tokens if mentions(summary, t))
                        if not (title_hits or text_hits):
                            continue
                        score += 3 * title_hits + text_hits
                    results.append(
                        PastProject(
                            year=year,
                            org=org_name,
                            title=title,
                            summary=summary,
                            project_url=project.get("project_url"),
                            code_url=project.get("code_url"),
                            score=round(score, 2),
                        )
                    )
        results.sort(key=lambda p: (-p.score, -p.year, p.title))
        return results[: max(1, limit)]
