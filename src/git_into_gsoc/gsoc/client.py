"""Mentoring organizations: the list for a year, one organization's record, and
past projects.

Three sources are layered:

* the **official** accepted-org list for a year (authoritative: source code,
  ideas page, contributor guidance, contact channels),
* an **embedded snapshot** of multi-year history (slug and projects per year
  for every org that ever participated) plus the latest official list, so
  ranking never needs the 15 MB community archive and still works offline, and
* the community **archive** (api.gsocorganizations.dev), fetched lazily only
  for past accepted project titles and for orgs missing from the snapshot.

When the target year's orgs are not announced yet, the most recent official
year is used and labelled as such.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

from git_into_gsoc.config import (
    LATEST_ARCHIVED_YEAR,
    Settings,
    get_settings,
    latest_program_year,
)
from git_into_gsoc.gsoc.names import core_key, resolve_name, same_org, suggest_names
from git_into_gsoc.gsoc.official import OfficialGSoCClient
from git_into_gsoc.gsoc.snapshot import load_history, load_official
from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.matching.profile import ContributorProfile, build_profile
from git_into_gsoc.matching.rank import OrgIndex
from git_into_gsoc.matching.signals import load_signals
from git_into_gsoc.models import ContactChannel, OrgCatalog, OrgSummary, PastProject
from git_into_gsoc.scoring.org_match import canonical, mentions
from git_into_gsoc.validation import validate_year

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


# Words that end in "s" but are not plurals of a shorter word ("news" is not "new").
_NOT_PLURAL = frozenset({"news", "series", "species"})


def _word_forms(token: str) -> set[str]:
    """A word with its plural or singular: "polynomial" also finds "Polynomials"."""
    forms = {token}
    if len(token) <= 3 or not token.isalpha() or token in _NOT_PLURAL:
        return forms  # acronyms and short words stay exact
    # Both guesses for an "-es" or "-ies" plural: "classes" is "class" but "databases" is
    # "database", and "libraries" is "library" but "movies" is "movie". The wrong guess
    # is not a word, so it finds nothing.
    if token.endswith("ies"):
        forms |= {token[:-3] + "y", token[:-1]}
    elif token.endswith(("ses", "xes", "ches", "shes")):
        forms |= {token[:-2], token[:-1]}
        if token.endswith("ses"):
            forms.add(token[:-2] + "is")  # "analyses" is "analysis"
    elif token.endswith("is"):
        forms.add(token[:-2] + "es")  # "analysis" and "analyses"
    elif token.endswith("s") and not token.endswith(("ss", "us")):
        forms.add(token[:-1])
    elif token.endswith("y") and token[-2:-1] not in "aeiou":
        forms.add(token[:-1] + "ies")
    else:
        forms.add(token + ("es" if token.endswith(("s", "x", "ch", "sh")) else "s"))
    return forms


def _mentions_any(text: str, token: str) -> bool:
    return any(mentions(text, form) for form in _word_forms(token))


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
        self._indexes: dict[int, OrgIndex] = {}

    # ------------------------------------------------------------- raw sources

    def _archive_url(self, name: str) -> str:
        return f"{self.settings.gsoc_orgs_api_url.rstrip('/')}/{name}"

    def list_all_organizations(self) -> list[dict[str, Any]]:
        """The full community archive (large); loaded lazily and overlaid on the snapshot."""
        if self._archive is None:
            data = self.http.get_json(
                self._archive_url("organizations.json"), ttl=self.settings.archive_ttl_seconds
            )
            if isinstance(data, dict):
                data = data.get("organizations")
            self._archive = list(data) if isinstance(data, list) else []
            self._history = None  # rebuild so archive records (richer) win over the snapshot
        return self._archive

    def list_year_organizations(self, year: int | None = None) -> list[dict[str, Any]]:
        """One year's organizations from the community archive, as raw records."""
        year = year or LATEST_ARCHIVED_YEAR
        data = self.http.get_json(
            self._archive_url(f"{int(year)}.json"), ttl=self.settings.archive_ttl_seconds
        )
        if isinstance(data, dict):
            data = data.get("organizations")
        return list(data) if isinstance(data, list) else []

    def _history_index(self) -> dict[str, dict[str, Any]]:
        """Name/slug -> history record, from the embedded snapshot plus any loaded archive."""
        if self._history is None:
            self._history = {}
            snapshot = load_history().get("organizations") or {}
            records = [{"name": name, **entry} for name, entry in snapshot.items()]
            records.extend(self._archive or [])
            cores: dict[str, dict[str, Any]] = {}
            for raw in records:
                name = str(raw.get("name") or "")
                self._history[normalize_name(name)] = raw
                slug = _archive_slug(raw)
                if slug:
                    self._history[f"slug:{slug}"] = raw
                # "Apache Software Foundation" is "The Apache Software Foundation" in the
                # archive. A filler-free key finds it; the record with more years wins.
                key = f"core:{core_key(name)}"
                kept = cores.get(key)
                if kept is None or len(raw.get("years") or {}) > len(kept.get("years") or {}):
                    cores[key] = raw
            for key, raw in cores.items():
                self._history.setdefault(key, raw)
        return self._history

    def _history_for(self, name: str, slug: str | None = None) -> dict[str, Any] | None:
        index = self._history_index()
        return (
            index.get(normalize_name(name))
            or (index.get(f"slug:{slug}") if slug else None)
            or index.get(f"core:{core_key(name)}")
        )

    def _past_names(self) -> list[str]:
        index = self._history_index()
        return [str(raw.get("name") or "") for key, raw in index.items() if ":" not in key]

    # ----------------------------------------------------------------- catalog

    def catalog(self, year: int | None = None) -> tuple[OrgCatalog, list[OrgSummary]]:
        """Accepted orgs for `year`, or the most recent year that has data."""
        year = validate_year(year, latest=latest_program_year(self.settings))
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
        try:
            raw_orgs = self.list_year_organizations(ref)
        except HttpError:
            raw_orgs = []
        if raw_orgs:
            orgs = [self._from_archive(raw, ref) for raw in raw_orgs]
            note = f"Archive copy of the {ref} org list (official site unavailable)."
            if ref != target:
                note += f" {target} orgs are not announced yet."
            return OrgCatalog(year=ref, source="archive", note=note, count=len(orgs)), orgs

        snapshot = load_official()
        if snapshot.get("organizations") and snapshot.get("year"):
            ref = int(snapshot["year"])
            orgs = [self._from_official(raw, ref) for raw in snapshot["organizations"]]
            note = (
                f"Embedded snapshot of the official {ref} org list from {snapshot['generated']} "
                "(live sources unreachable). Verify on summerofcode.withgoogle.com."
            )
            return OrgCatalog(year=ref, source="snapshot", note=note, count=len(orgs)), orgs
        raise HttpError(
            "GSoC organization data is unavailable (official site and archive unreachable).",
            hint="Check your connection and retry; see https://summerofcode.withgoogle.com.",
        )

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

    def org_index(self, year: int | None = None) -> tuple[OrgCatalog, OrgIndex]:
        """The ranking index for a year's list, built once per client."""
        catalog, orgs = self.catalog(year)
        if catalog.year not in self._indexes:
            self._indexes[catalog.year] = OrgIndex.build(
                orgs,
                descriptions=self._search_text,
                signals=load_signals(),
                reference_year=catalog.year,
            )
        return catalog, self._indexes[catalog.year]

    def rank_organizations(
        self,
        *,
        query: str | None = None,
        technologies: list[str] | None = None,
        topics: list[str] | None = None,
        category: str | None = None,
        experience: str | None = None,
        hours_per_week: int | None = None,
        year: int | None = None,
        limit: int = 15,
    ) -> tuple[OrgCatalog, list[OrgSummary], ContributorProfile]:
        """Organizations ranked for one person, each with its fit and evidence.

        Also returns how the person's words were read, so callers can say when a
        misspelling was corrected.
        """
        catalog, index = self.org_index(year)
        person = build_profile(
            technologies=technologies,
            interests=topics,
            experience=experience,
            hours_per_week=hours_per_week,
        )
        matches = index.rank(
            person, query=query or "", category=category or "", limit=max(1, limit)
        )
        ranked = [
            m.org.model_copy(
                update={
                    "match_score": m.score,
                    "match_reasons": m.reasons(),
                    "fit": m.fit,
                    "interest_fit": m.interest_fit,
                    "skill_fit": m.skill_fit,
                    "evidence": m.evidence(),
                    "readiness": m.readiness,
                    "caveats": m.caveats,
                    "skills_to_learn": m.skills_to_learn,
                    "participation": m.participation,
                    "ideas_unread": m.ideas_unread,
                }
            )
            for m in matches
        ]
        return catalog, ranked, person

    def search_organizations(
        self,
        *,
        query: str | None = None,
        technologies: list[str] | None = None,
        topics: list[str] | None = None,
        category: str | None = None,
        experience: str | None = None,
        hours_per_week: int | None = None,
        year: int | None = None,
        limit: int = 15,
    ) -> tuple[OrgCatalog, list[OrgSummary]]:
        """`rank_organizations` without the profile, for callers that only want the list."""
        catalog, ranked, _ = self.rank_organizations(
            query=query,
            technologies=technologies,
            topics=topics,
            category=category,
            experience=experience,
            hours_per_week=hours_per_week,
            year=year,
            limit=limit,
        )
        return catalog, ranked

    def resolve_org_name(self, name: str, *, year: int | None = None) -> str | None:
        """The full name of the organization `name` means: current list, then history.

        Raises AmbiguousNameError when the name fits several organizations equally.
        """
        if not normalize_name(name):
            return None
        _, orgs = self.catalog(year)
        by_slug = next((o.name for o in orgs if o.slug == name), None)
        if by_slug:
            return by_slug
        current = [o.name for o in orgs]
        chosen = resolve_name(name, current, self._past_names())
        if chosen is None and self._archive is None:
            self.list_all_organizations()  # full archive, for orgs the snapshot lacks
            chosen = resolve_name(name, current, self._past_names())
        return chosen

    def get_organization(self, name: str, *, year: int | None = None) -> OrgSummary | None:
        """The organization `name` means, or None.

        Raises AmbiguousNameError when the name fits several organizations equally.
        """
        if not normalize_name(name):
            return None
        _, orgs = self.catalog(year)
        chosen = self.resolve_org_name(name, year=year)
        if chosen is None:
            return None
        org = next((o for o in orgs if o.name == chosen), None)
        if org is None:
            self.list_all_organizations()  # full records for orgs outside the current list
            hist = self._history_for(chosen)
            if hist is None:
                return None
            years = sorted(int(y) for y in (hist.get("years") or {}))
            org = self._from_archive(hist, years[-1] if years else LATEST_ARCHIVED_YEAR)
        try:
            projects = self.search_projects(org=org.name, limit=10)
        except HttpError:
            projects = []  # the archive is optional detail; the profile itself still shows
        return org.model_copy(update={"recent_projects": projects})

    def suggest_organizations(
        self, name: str, *, year: int | None = None
    ) -> tuple[list[str], list[str]]:
        """For a name that matched nothing: near spellings, and orgs that mention it.

        Many projects (NumPy, Kubernetes) take part under an umbrella organization
        (NumFOCUS, CNCF), whose description names them.
        """
        _, orgs = self.catalog(year)
        similar = suggest_names(name, [o.name for o in orgs])
        similar += [n for n in suggest_names(name, self._past_names()) if n not in similar][:3]
        _, mentioned = self.search_organizations(query=name, year=year, limit=4)
        mentions = [o.name for o in mentioned if o.name not in similar]
        return similar[:5], mentions[:4]

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
        results: list[PastProject] = []
        for raw in self.list_all_organizations():
            org_name = str(raw.get("name") or "")
            # Whole-name match: "Git" must not pull in GitLab's or "diGITal" projects.
            if org and not same_org(org, org_name):
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
                        title_hits = sum(1 for t in tokens if _mentions_any(title, t))
                        text_hits = sum(1 for t in tokens if _mentions_any(summary, t))
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
