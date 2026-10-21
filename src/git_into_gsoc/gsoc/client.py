"""Client for GSoC organization archive data."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from git_into_gsoc.config import LATEST_ARCHIVED_YEAR, Settings, get_settings
from git_into_gsoc.http_client import CachedHttpClient
from git_into_gsoc.models import OrgSummary
from git_into_gsoc.scoring.org_match import score_org_match


def _years_from_org(raw: dict[str, Any]) -> list[int]:
    years_obj = raw.get("years") or {}
    years: list[int] = []
    for key in years_obj:
        try:
            years.append(int(key))
        except (TypeError, ValueError):
            continue
    return sorted(years)


def _github_hints(raw: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for key in ("url", "blog_url"):
        value = raw.get(key)
        if not value:
            continue
        parsed = urlparse(str(value))
        host = (parsed.netloc or "").lower()
        if "github.com" in host:
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                hints.append(parts[0])
        elif host.endswith("github.io") and parsed.path:
            hints.append(host.split(".")[0])
    # Also scan description for github.com/org patterns
    text = " ".join(
        str(raw.get(k) or "") for k in ("description", "url", "blog_url", "mailing_list")
    )
    for match in re.findall(r"github\.com/([A-Za-z0-9_.-]+)", text, flags=re.I):
        if match.lower() not in {"topics", "settings", "pulls", "issues"}:
            hints.append(match)
    # Deduplicate preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for hint in hints:
        key = hint.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(hint)
    return ordered[:5]


class GSoCClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http: CachedHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or CachedHttpClient(self.settings)
        self._orgs_cache: list[dict[str, Any]] | None = None

    def _orgs_url(self) -> str:
        return f"{self.settings.gsoc_orgs_api_url.rstrip('/')}/organizations.json"

    def _year_url(self, year: int) -> str:
        return f"{self.settings.gsoc_orgs_api_url.rstrip('/')}/{year}.json"

    def list_all_organizations(self) -> list[dict[str, Any]]:
        if self._orgs_cache is not None:
            return self._orgs_cache
        data = self.http.get_json(self._orgs_url())
        if isinstance(data, list):
            self._orgs_cache = data
        elif isinstance(data, dict) and "organizations" in data:
            self._orgs_cache = list(data["organizations"])
        else:
            self._orgs_cache = []
        return self._orgs_cache

    def list_year_organizations(self, year: int | None = None) -> list[dict[str, Any]]:
        year = year or LATEST_ARCHIVED_YEAR
        data = self.http.get_json(self._year_url(year))
        if isinstance(data, dict):
            orgs = data.get("organizations")
            if isinstance(orgs, list):
                return orgs
        if isinstance(data, list):
            return data
        return []

    def to_summary(self, raw: dict[str, Any], *, year_hint: int | None = None) -> OrgSummary:
        years = _years_from_org(raw)
        latest = years[-1] if years else year_hint
        num_projects = 0
        if latest is not None:
            year_data = (raw.get("years") or {}).get(str(latest)) or {}
            num_projects = int(year_data.get("num_projects") or 0)
            if not num_projects and "num_projects" in raw:
                num_projects = int(raw.get("num_projects") or 0)
        return OrgSummary(
            name=raw.get("name") or "Unknown",
            description=raw.get("description") or "",
            url=raw.get("url"),
            category=raw.get("category"),
            topics=list(raw.get("topics") or []),
            technologies=list(raw.get("technologies") or []),
            years_active=years,
            latest_year=latest,
            num_projects_latest=num_projects,
            contact_email=raw.get("contact_email"),
            mailing_list=raw.get("mailing_list"),
            irc_channel=raw.get("irc_channel"),
            blog_url=raw.get("blog_url"),
            github_hints=_github_hints(raw),
        )

    def search_organizations(
        self,
        *,
        query: str | None = None,
        technologies: list[str] | None = None,
        topics: list[str] | None = None,
        category: str | None = None,
        year: int | None = None,
        min_years: int = 1,
        limit: int = 15,
    ) -> list[OrgSummary]:
        """Search and rank mentoring organizations.

        When `year` is set, prefer that year's org list. For GSoC 2027 planning,
        use the latest archived year (currently 2026) plus historical continuity.
        """
        if year and year <= LATEST_ARCHIVED_YEAR:
            raw_orgs = self.list_year_organizations(year)
            summaries = [self.to_summary(o, year_hint=year) for o in raw_orgs]
            # Enrich with multi-year history from the full archive when available
            history = {
                (o.get("name") or "").strip().lower(): self.to_summary(o)
                for o in self.list_all_organizations()
            }
            for s in summaries:
                hist = history.get(s.name.strip().lower())
                if hist and hist.years_active:
                    s.years_active = sorted(set([*hist.years_active, year]))
                    s.latest_year = max(s.years_active)
                    if not s.num_projects_latest and hist.num_projects_latest:
                        s.num_projects_latest = hist.num_projects_latest
                    if not s.github_hints and hist.github_hints:
                        s.github_hints = hist.github_hints
                elif year not in s.years_active:
                    s.years_active = sorted(set([*s.years_active, year]))
                    s.latest_year = max(s.years_active) if s.years_active else year
        else:
            raw_orgs = self.list_all_organizations()
            summaries = [self.to_summary(o) for o in raw_orgs]

        tech = [t.lower() for t in (technologies or [])]
        tops = [t.lower() for t in (topics or [])]
        q = (query or "").strip().lower()
        cat = (category or "").strip().lower()

        ranked: list[OrgSummary] = []
        for summary in summaries:
            # keep brand-new orgs if explicitly querying a year list
            if (
                len(summary.years_active) < min_years
                and not year
                and not q
                and not tech
                and not tops
            ):
                continue

            score, reasons = score_org_match(
                summary,
                query=q,
                technologies=tech,
                topics=tops,
                category=cat,
                prefer_year=year or LATEST_ARCHIVED_YEAR,
            )
            if score <= 0 and (q or tech or tops or cat):
                continue
            summary.match_score = score
            summary.match_reasons = reasons
            ranked.append(summary)

        ranked.sort(key=lambda s: (-s.match_score, -len(s.years_active), s.name.lower()))
        return ranked[:limit]

    def get_organization(self, name: str) -> OrgSummary | None:
        needle = name.strip().lower()
        for raw in self.list_all_organizations():
            if (raw.get("name") or "").strip().lower() == needle:
                return self.to_summary(raw)
        # fuzzy contains
        for raw in self.list_all_organizations():
            org_name = (raw.get("name") or "").strip().lower()
            if needle in org_name or org_name in needle:
                return self.to_summary(raw)
        # try latest year list
        for raw in self.list_year_organizations(LATEST_ARCHIVED_YEAR):
            org_name = (raw.get("name") or "").strip().lower()
            if needle == org_name or needle in org_name:
                return self.to_summary(raw, year_hint=LATEST_ARCHIVED_YEAR)
        return None
