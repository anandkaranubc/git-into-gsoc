"""High-level facade used by CLI and MCP tools."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.config import DEFAULT_TARGET_YEAR, LATEST_ARCHIVED_YEAR, get_settings
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.gsoc.client import GSoCClient
from git_into_gsoc.gsoc.timeline import program_status
from git_into_gsoc.guidance import journey_overview, proposal_checklist
from git_into_gsoc.http_client import CachedHttpClient
from git_into_gsoc.progress.store import ProgressStore


class GSoCToolkit:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = CachedHttpClient(self.settings)
        self.github = GitHubClient(self.settings, self.http)
        self.gsoc = GSoCClient(self.settings, self.http)
        self.progress = ProgressStore()

    def program_info(self, year: int | None = None) -> dict[str, Any]:
        year = year or self.settings.target_year
        status = program_status(year)
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
    ) -> list[dict[str, Any]]:
        # For 2027 aspirants, default to latest archived participation year.
        search_year = year
        if search_year is None or search_year > LATEST_ARCHIVED_YEAR:
            search_year = LATEST_ARCHIVED_YEAR
        results = self.gsoc.search_organizations(
            query=query,
            technologies=technologies,
            topics=topics,
            category=category,
            year=search_year,
            limit=limit,
        )
        return [r.model_dump() for r in results]

    def org_details(self, name: str) -> dict[str, Any]:
        org = self.gsoc.get_organization(name)
        if not org:
            return {
                "found": False,
                "error": f"No organization matched '{name}' in archive data",
                "hint": "Try a partial name or list orgs with a technology filter",
            }
        return {"found": True, "organization": org.model_dump()}

    def evaluate_repo(self, full_name: str) -> dict[str, Any]:
        health = self.github.repo_health(full_name)
        guide = self.github.contribution_guide(full_name)
        return {
            "health": health.model_dump(mode="json"),
            "contribution_guide": guide.model_dump(),
            "recommendation": _repo_recommendation(health.health_score, health.warnings),
        }

    def find_issues(
        self,
        *,
        language: str | None = None,
        org: str | None = None,
        repo: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        issues = self.github.find_beginner_issues(
            language=language,
            org=org,
            repo=repo,
            max_results=max_results,
        )
        return [i.model_dump(mode="json") for i in issues]

    def issue_status(self, full_name: str, number: int) -> dict[str, Any]:
        availability, reason = self.github.check_issue_availability(full_name, number)
        return {
            "repo": full_name,
            "number": number,
            "availability": availability.value,
            "reason": reason,
            "url": f"https://github.com/{full_name}/issues/{number}",
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
        )
        issue_language = techs[0] if techs else None
        issues: list[dict[str, Any]] = []
        if issue_language:
            try:
                issues = self.find_issues(language=issue_language, max_results=5)
            except Exception as exc:
                issues = [{"error": str(exc)}]

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
