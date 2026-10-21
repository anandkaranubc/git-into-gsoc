"""MCP server exposing git-into-gsoc intelligence tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from git_into_gsoc import __version__
from git_into_gsoc.config import PROJECT_URL
from git_into_gsoc.errors import GigError
from git_into_gsoc.guidance import ANTI_SPAM_RULES, OFFICIAL_SOURCES, journey_overview
from git_into_gsoc.models import JourneyPhase
from git_into_gsoc.service import GSoCToolkit
from git_into_gsoc.validation import split_csv

mcp = MCPServer(
    name="git-into-gsoc",
    title="git-into-gsoc",
    version=__version__,
    website_url=PROJECT_URL,
    instructions=(
        "Evidence-backed Google Summer of Code contributor toolkit. "
        "Use these tools for real org/repo/issue data. Never fabricate opportunities. "
        "Prefer high-quality contributions and respect each org's AI policy. "
        "Read-only tools are safe to call freely; gsoc_progress writes the user's local "
        "progress file. Results are JSON strings; quote the evidence (URLs, reasons) they contain."
    ),
)

# Every tool except gsoc_progress only reads public data; clients use these hints
# to decide whether a call needs confirmation.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True, idempotent_hint=True)
LOCAL_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True)


@mcp.resource("gsoc://journey", title="GSoC contributor journey", mime_type="application/json")
def journey_resource() -> str:
    """The eight journey phases with goals, actions, and the anti-spam rules."""
    return json.dumps(journey_overview(), indent=2)


@mcp.resource(
    "gsoc://official-sources", title="Official GSoC sources", mime_type="application/json"
)
def official_sources_resource() -> str:
    """Canonical Google pages for rules, dates, AI guidance, and proposal quality."""
    return json.dumps([s.model_dump() for s in OFFICIAL_SOURCES], indent=2)


@mcp.resource("gsoc://anti-spam-rules", title="Anti-spam rules", mime_type="text/plain")
def anti_spam_resource() -> str:
    """Rules the assistant must follow when helping with contributions and proposals."""
    return "\n".join(f"- {rule}" for rule in ANTI_SPAM_RULES)


_toolkit: GSoCToolkit | None = None


def toolkit() -> GSoCToolkit:
    global _toolkit
    if _toolkit is None:
        _toolkit = GSoCToolkit()
    return _toolkit


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool(annotations=READ_ONLY)
def gsoc_program_info(year: int = 2027) -> str:
    """Get GSoC program status, timeline, official links, and anti-spam rules.

    For 2027, dates may be estimates until Google publishes the official timeline.
    Always verify on summerofcode.withgoogle.com.
    """
    return _dump(toolkit().program_info(year))


@mcp.tool(annotations=READ_ONLY)
def gsoc_journey_guide(phase: str | None = None) -> str:
    """Return journey phase guidance for GSoC contributors.

    Phases: learn, discover, evaluate, find_issues, contribute, community, proposal, track.
    Omit phase to get the full overview.
    """
    overview = journey_overview()
    if not phase:
        return _dump(overview)
    key = phase.strip().lower()
    phases = overview["phases"]
    assert isinstance(phases, dict)
    if key not in phases:
        return _dump({"error": f"Unknown phase '{phase}'", "valid": list(phases)})
    phase_guide = phases[key]
    assert isinstance(phase_guide, dict)
    return _dump({"phase": key, **phase_guide, "anti_spam_rules": overview["anti_spam_rules"]})


@mcp.tool(annotations=READ_ONLY)
def gsoc_search_orgs(
    query: str = "",
    technologies: str = "",
    topics: str = "",
    category: str = "",
    year: int = 0,
    limit: int = 10,
) -> str:
    """Rank GSoC mentoring organizations by fit with a contributor's skills and interests.

    technologies/topics: comma-separated (e.g. "python,rust"; aliases like js/golang/ml work).
    year: target program year (default: configured target, 2027). If that year's orgs are not
    announced yet, the latest official list is used and `catalog.note` says so.
    Each org includes ideas_url, guide_url, github_orgs, channels, and slot history.
    """
    return _dump(
        toolkit().match_orgs(
            query=query or None,
            technologies=split_csv(technologies) or None,
            topics=split_csv(topics) or None,
            category=category or None,
            year=year or None,
            limit=limit,
        )
    )


@mcp.tool(annotations=READ_ONLY)
def gsoc_org_details(name: str, year: int = 0) -> str:
    """Full profile for one org: ideas page, contributor guide, channels, GitHub orgs,
    projects per year, and recent accepted project titles. Accepts partial names."""
    return _dump(toolkit().org_details(name, year=year or None))


@mcp.tool(annotations=READ_ONLY)
def gsoc_past_projects(query: str = "", org: str = "", since: int = 0, limit: int = 15) -> str:
    """Search accepted GSoC projects from past years by keyword and/or org.

    Use to calibrate proposal scope and discover which orgs fund a kind of work.
    Never suggest copying a past proposal.
    """
    return _dump(
        toolkit().past_projects(query or None, org=org or None, since=since or None, limit=limit)
    )


@mcp.tool(annotations=READ_ONLY)
def gsoc_evaluate_repo(full_name: str) -> str:
    """Will a newcomer's PR land here? Health grade (A-F) with signals and warnings:
    activity, CONTRIBUTING/CoC/templates, CI, open beginner issues, bot-free merge rate,
    outside-contributor merge rate, review speed; plus toolchain/dev-container setup hints.

    full_name: owner/repo or a GitHub URL (e.g. sympy/sympy)
    """
    return _dump(toolkit().evaluate_repo(full_name))


@mcp.tool(annotations=READ_ONLY)
def gsoc_discover_repos(org: str, language: str = "", limit: int = 10) -> str:
    """Rank a mentoring org's GitHub repositories for a first contribution.

    org: GSoC org name ("GNU Radio") or GitHub login. Repos named on the org's ideas page,
    with open good-first-issues, recent pushes, and the preferred `language` rank highest.
    """
    return _dump(toolkit().discover_repos(org, language=language or None, limit=limit))


@mcp.tool(annotations=READ_ONLY)
def gsoc_find_issues(
    language: str = "",
    org: str = "",
    repo: str = "",
    label: str = "",
    scope: str = "gsoc",
    max_results: int = 10,
) -> str:
    """Find beginner issues that are genuinely free to pick up.

    scope="gsoc" (default) searches only repos owned by GSoC mentoring orgs that use `language`;
    scope="all" searches all of GitHub. Excludes assigned, PR-linked, and archived-repo issues,
    then checks the top candidates' timelines for claims ("can I work on this?"), contested
    threads, and maintainer engagement. Each result has availability + reason + signals.
    """
    return _dump(
        toolkit().find_issues(
            language=language or None,
            org=org or None,
            repo=repo or None,
            label=label or None,
            scope=scope,
            max_results=max_results,
        )
    )


@mcp.tool(annotations=READ_ONLY)
def gsoc_issue_status(ref: str, number: int = 0) -> str:
    """Check if one issue is free: linked PRs, assignees, claims (with dates), maintainer
    approval, and caveats. ref: "owner/repo#123", an issue URL, or "owner/repo" + number."""
    return _dump(toolkit().issue_status(ref, number or None))


@mcp.tool(annotations=LOCAL_WRITE)
def gsoc_recommend_path(
    github_username: str = "",
    technologies: str = "",
    interests: str = "",
) -> str:
    """Personalized starting path: profile languages, matching orgs, starter issues."""
    tech = [t.strip() for t in technologies.split(",") if t.strip()]
    interests_list = [t.strip() for t in interests.split(",") if t.strip()]
    return _dump(
        toolkit().recommend_path(
            username=github_username or None,
            technologies=tech or None,
            interests=interests_list or None,
        )
    )


@mcp.tool(annotations=READ_ONLY)
def gsoc_proposal_checklist() -> str:
    """Proposal quality checklist grounded in official GSoC guidance."""
    return _dump(toolkit().proposal_help())


@mcp.tool(annotations=READ_ONLY)
def gsoc_proposal_check(
    text: str, github_username: str = "", verify_links: bool = True, ideas_text: str = ""
) -> str:
    """Check a draft proposal for what organizations reject on. Never rewrites it.

    Reports pass/warn/fail findings with reasons: required sections (synopsis,
    deliverables, timeline, about), recommended ones (benefits, contributions,
    availability, AI statement), links to the author's PRs (verified on GitHub when
    verify_links is true, flagging PRs authored by someone else when github_username is
    given), week-by-week timeline detail and buffer, concrete code references, generic
    AI-sounding phrasing, leftover template placeholders, and length. Pass the org's ideas
    page as ideas_text to flag passages copied from it. Use the findings to coach the author
    to revise in their own voice; do not draft replacement text for them.
    """
    try:
        return _dump(
            toolkit().check_proposal(
                text,
                github=github_username or None,
                verify=verify_links,
                ideas_text=ideas_text or None,
            )
        )
    except GigError as exc:
        return _dump(exc.to_dict())


@mcp.tool(annotations=LOCAL_WRITE)
def gsoc_progress(action: str = "summary", phase: str = "", value: str = "") -> str:
    """Track local GSoC journey progress.

    action: summary | complete_phase | shortlist_org | track_repo | track_issue | note
    phase: required for complete_phase
    value: org name / owner/repo / issue url / note text depending on action
    """
    store = toolkit().progress
    act = action.strip().lower()
    try:
        if act == "summary":
            return _dump(store.summary())
        if act == "complete_phase":
            if not phase:
                return _dump(
                    {"error": "phase is required", "valid": [p.value for p in JourneyPhase]}
                )
            return _dump(store.complete_phase(phase).model_dump(mode="json"))
        if act == "shortlist_org":
            return _dump(store.shortlist_org(value).model_dump(mode="json"))
        if act == "track_repo":
            return _dump(store.track_repo(value).model_dump(mode="json"))
        if act == "track_issue":
            return _dump(store.track_issue(value).model_dump(mode="json"))
        if act == "note":
            return _dump(store.add_note(value).model_dump(mode="json"))
    except GigError as exc:
        return _dump(exc.to_dict())
    return _dump(
        {
            "error": f"Unknown action '{action}'",
            "valid": [
                "summary",
                "complete_phase",
                "shortlist_org",
                "track_repo",
                "track_issue",
                "note",
            ],
        }
    )


@mcp.tool(annotations=READ_ONLY)
def gsoc_rate_limit() -> str:
    """Show GitHub API rate limit status. Set GITHUB_TOKEN for higher limits."""
    return _dump(toolkit().rate_limit())


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
