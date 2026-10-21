"""High-level facade used by CLI and MCP tools."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, LATEST_ARCHIVED_YEAR, get_settings
from git_into_gsoc.errors import GigError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.gsoc.client import GSoCClient
from git_into_gsoc.gsoc.official import OfficialGSoCClient
from git_into_gsoc.gsoc.timeline import program_status
from git_into_gsoc.guidance import journey_overview, proposal_checklist
from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.validation import parse_issue_ref

BEFORE_YOU_COMMENT = [
    "Read the whole thread and any linked PRs first.",
    "Reproduce the problem locally (or confirm the docs gap) before claiming.",
    "Point to the code you would change and outline your approach in 2-3 sentences.",
    "Ask whether the approach fits; do not just write 'can I work on this?'.",
    "If someone claimed it recently, pick another issue rather than competing.",
]


class GSoCToolkit:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = CachedHttpClient(self.settings)
        self.github = GitHubClient(self.settings, self.http)
        self.official = OfficialGSoCClient(self.settings, self.http)
        self.gsoc = GSoCClient(self.settings, self.http, self.official)
        self.progress = ProgressStore()

    def program_info(self, year: int | None = None, project_size: str = "medium") -> dict[str, Any]:
        year = year or self.settings.target_year
        offline = False
        try:
            official = self.official.program(year)
        except HttpError:
            official, offline = None, True
        status = program_status(
            year, official_program=official, project_size=project_size, offline=offline
        )
        overview = journey_overview()
        return {
            **status,
            "latest_archived_org_year": LATEST_ARCHIVED_YEAR,
            "default_target_year": DEFAULT_TARGET_YEAR,
            "official_sources": overview["official_sources"],
            "anti_spam_rules": overview["anti_spam_rules"],
        }

    def match_orgs(
        self,
        *,
        query: str | None = None,
        technologies: list[str] | None = None,
        topics: list[str] | None = None,
        category: str | None = None,
        year: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        catalog, results = self.gsoc.search_organizations(
            query=query,
            technologies=technologies,
            topics=topics,
            category=category,
            year=year,
            limit=limit,
        )
        return {
            "catalog": catalog.model_dump(),
            "count": len(results),
            "organizations": [r.model_dump(exclude={"recent_projects"}) for r in results],
        }

    def org_details(self, name: str, year: int | None = None) -> dict[str, Any]:
        org = self.gsoc.get_organization(name, year=year)
        if not org:
            return {
                "found": False,
                "error": f"No organization matched '{name}'",
                "hint": "Try a partial name, or search with `orgs --query`.",
            }
        catalog, _ = self.gsoc.catalog(year)
        return {"found": True, "catalog": catalog.model_dump(), "organization": org.model_dump()}

    def past_projects(
        self,
        query: str | None = None,
        *,
        org: str | None = None,
        since: int | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        projects = self.gsoc.search_projects(query, org=org, since=since, limit=limit)
        return {
            "count": len(projects),
            "projects": [p.model_dump() for p in projects],
            "note": (
                "Accepted GSoC projects from the public archive. Use them to understand scope "
                "and what each org values. Never copy a past proposal."
            ),
        }

    def evaluate_repo(self, full_name: str) -> dict[str, Any]:
        health = self.github.repo_health(full_name)
        guide = self.github.contribution_guide(full_name)
        return {
            "health": health.model_dump(mode="json"),
            "contribution_guide": guide.model_dump(),
            "recommendation": _repo_recommendation(health.health_score, health.warnings),
        }

    def gsoc_github_orgs(
        self, *, language: str | None = None, year: int | None = None, limit: int = 12
    ) -> tuple[dict[str, str], list[str], str]:
        """Map GitHub owners to GSoC org names, plus a language-ranked owner shortlist."""
        try:
            catalog, orgs = self.gsoc.catalog(year)
            _, ranked = self.gsoc.search_organizations(
                technologies=[language] if language else None, year=year, limit=60
            )
        except HttpError:
            return {}, [], "GSoC org data unavailable; searched all of GitHub."
        owner_names = {gh.lower(): org.name for org in orgs for gh in org.github_orgs}
        shortlist = [org.github_orgs[0] for org in ranked if org.github_orgs][:limit]
        note = (
            f"Searching GitHub orgs of GSoC {catalog.year} organizations"
            + (f" that use {language}" if language else "")
            + ". Use --scope all to search every repository."
        )
        return owner_names, shortlist, note

    def find_issues(
        self,
        *,
        language: str | None = None,
        org: str | None = None,
        repo: str | None = None,
        label: str | None = None,
        scope: str = "gsoc",
        max_results: int = 10,
        year: int | None = None,
    ) -> dict[str, Any]:
        owner_names, shortlist, note = self.gsoc_github_orgs(language=language, year=year)
        use_gsoc = scope == "gsoc" and not org and not repo and bool(shortlist)
        if not use_gsoc:
            note = "Searching " + (f"{repo}" if repo else f"org {org}" if org else "all of GitHub")
        issues = self.github.find_beginner_issues(
            language=language,
            org=org,
            orgs=shortlist if use_gsoc else None,
            repo=repo,
            label=label,
            max_results=max_results,
            org_names=owner_names,
        )
        return {
            "scope": "gsoc" if use_gsoc else "custom",
            "note": note,
            "count": len(issues),
            "issues": [
                i.model_dump(mode="json", exclude={"signals"}) | {"signals": i.signals}
                for i in issues
            ],
            "before_you_comment": BEFORE_YOU_COMMENT,
        }

    def issue_status(self, ref: str, number: int | None = None) -> dict[str, Any]:
        owner, repo, num = parse_issue_ref(ref, number)
        issue, assessment = self.github.assess(f"{owner}/{repo}", num)
        return {
            "repo": f"{owner}/{repo}",
            "number": num,
            "title": issue.get("title"),
            "url": issue.get("html_url") or f"https://github.com/{owner}/{repo}/issues/{num}",
            "labels": [
                lab.get("name") for lab in issue.get("labels") or [] if isinstance(lab, dict)
            ],
            "comments": issue.get("comments"),
            "availability": assessment.availability.value,
            "reason": assessment.reason,
            "assessment": assessment.model_dump(mode="json"),
            "before_you_comment": BEFORE_YOU_COMMENT,
        }

    def profile_from_github(self, username: str) -> dict[str, Any]:
        profile = self.github.infer_profile_languages(username)
        self.progress.set_profile(
            github=username, **{k: profile.get(k) for k in ("top_language", "languages", "bio")}
        )
        return profile

    def recommend_path(
        self,
        *,
        username: str | None = None,
        technologies: list[str] | None = None,
        interests: list[str] | None = None,
    ) -> dict[str, Any]:
        techs = list(technologies or [])
        profile = None
        if username:
            profile = self.profile_from_github(username)
            if profile.get("top_language") and profile["top_language"] not in techs:
                techs.insert(0, profile["top_language"])

        orgs = self.match_orgs(
            technologies=techs or None,
            topics=interests,
            limit=8,
        )["organizations"]
        issue_language = techs[0] if techs else None
        issues: list[dict[str, Any]] = []
        if issue_language:
            try:
                issues = self.find_issues(language=issue_language, max_results=5)["issues"]
            except GigError as exc:
                issues = [exc.to_dict()]

        return {
            "profile": profile,
            "technologies_used": techs,
            "recommended_orgs": orgs,
            "starter_issues": issues,
            "next_steps": [
                "Shortlist 3 orgs and join their communication channels",
                "Evaluate 1-2 flagship repos for health and CONTRIBUTING fit",
                "Land a meaningful first contribution before writing a proposal",
                "Read official AI guidance and each org's AI policy",
            ],
            "evidence_note": (
                f"Org rankings use archive data through {LATEST_ARCHIVED_YEAR}. "
                "GSoC 2027 org lists are not final until officially announced."
            ),
        }

    def proposal_help(self) -> dict[str, Any]:
        return {
            "checklist": [i.model_dump() for i in proposal_checklist()],
            "structure": [
                "Synopsis — one paragraph problem + proposed outcome",
                "Benefits to the community",
                "Deliverables and non-goals",
                "Implementation plan with milestones",
                "Timeline (weekly) with buffer",
                "Related prior art / design notes",
                "About you — relevant experience + links to contributions",
                "AI usage statement aligned to org policy",
            ],
            "warnings": [
                "Generic LLM essays are frequently rejected — see official spam guidance",
                "Submit only through the official GSoC website",
                "Prior org interaction is often the strongest acceptance signal",
            ],
        }

    def rate_limit(self) -> dict[str, Any]:
        return self.github.rate_limit()


def _repo_recommendation(score: float, warnings: list[str]) -> str:
    if score >= 80:
        return "Strong candidate for contribution — proceed with setup and issue selection"
    if score >= 65:
        return "Promising with caveats — read warnings and confirm mentor responsiveness"
    if score >= 45:
        return "Risky — only continue if you have a specific mentor contact or strong fit"
    return "Poor fit for a first GSoC contribution — choose a healthier repository"
