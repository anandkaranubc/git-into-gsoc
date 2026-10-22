"""High-level facade used by CLI and MCP tools."""

from __future__ import annotations

import contextlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse

from git_into_gsoc.coach import (
    GSOC_FAQ_URL,
    LONGEST_CODING_WEEKS,
    hours_note,
    plan_actions,
    time_budget,
    upcoming_deadlines,
)
from git_into_gsoc.config import (
    DEFAULT_TARGET_YEAR,
    LATEST_ARCHIVED_YEAR,
    get_settings,
    latest_program_year,
)
from git_into_gsoc.drafts import DRAFT_KINDS, claim_convention, manifest_commands, render_draft
from git_into_gsoc.errors import GigError, InputError, reset_phrase
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.orientation import (
    active_committers,
    branch_gates,
    ci_environment,
    ci_install_commands,
    ci_test_commands,
    ci_test_dirs_first,
    code_map,
    codeowners_for,
    codetour_from_orientation,
    conventions,
    days_since,
    entry_points,
    find_paths,
    policy_quotes,
    rank_gate_workflows,
    rank_workflows,
    reading_plan,
    since_iso,
    workflow_gates,
)
from git_into_gsoc.github.pointers import (
    closing_pull_request,
    code_first,
    days_between,
    extract_mentions,
    fix_norm,
    rank_similar,
    resolve_paths,
    title_file_matches,
    title_keywords,
)
from git_into_gsoc.github.prcheck import check_pull_request
from git_into_gsoc.github.pulls import pull_request_status
from git_into_gsoc.github.repos import (
    OUTSIDER_ROLES,
    beginner_labels,
    channels_in,
    is_bot,
    is_event_repo,
    is_main_repo,
    mentioned_repos,
    mirror_source,
    pick_beginner_label,
    repo_kind,
    repo_lead_score,
)
from git_into_gsoc.github.search import (
    RELATED_LANGUAGES,
    build_issue_query,
    language_family,
    or_group,
)
from git_into_gsoc.gitlab import gitlab_issue_status, parse_gitlab_issue
from git_into_gsoc.gsoc.archive import ArchiveClient, proposal_folders, summarize_mentors
from git_into_gsoc.gsoc.client import GSoCClient
from git_into_gsoc.gsoc.ideas import fetch_ideas_text
from git_into_gsoc.gsoc.official import OfficialGSoCClient
from git_into_gsoc.gsoc.project_ideas import (
    fetch_ideas_document,
    issues_page_target,
    rank_ideas,
)
from git_into_gsoc.gsoc.timeline import program_status
from git_into_gsoc.guidance import journey_overview, proposal_checklist
from git_into_gsoc.http_client import CachedHttpClient, HttpError, NotFoundError
from git_into_gsoc.matching.concepts import SKILL, kind_of
from git_into_gsoc.matching.concepts import resolve as resolve_concept
from git_into_gsoc.matching.ideas import ideas_for
from git_into_gsoc.matching.issues import (
    OLD_ISSUE_YEARS,
    personalize,
    starter_problem,
)
from git_into_gsoc.matching.path import learning_path
from git_into_gsoc.matching.profile import (
    EXPERIENCE_HELP,
    EXPERIENCE_LEVELS,
    ContributorProfile,
    build_profile,
    effective_experience,
    languages_of,
)
from git_into_gsoc.matching.signals import load_signals, signals_for
from git_into_gsoc.models import (
    Availability,
    ContactChannel,
    IdeasDocument,
    OrgSummary,
    ProgressState,
    ProjectIdea,
    RepoLead,
)
from git_into_gsoc.progress.store import ProgressStore, other_host_link
from git_into_gsoc.scoring.health import DORMANT_DAYS
from git_into_gsoc.scoring.org_match import canonical
from git_into_gsoc.text import clean_untrusted
from git_into_gsoc.validation import (
    parse_issue_ref,
    parse_repo,
    plain_skill,
    validate_login,
    validate_year,
)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


BEFORE_YOU_COMMENT = [
    "Read the whole thread and any linked PRs first.",
    "Reproduce the problem locally (or confirm the docs gap) before claiming.",
    "Point to the code you would change and outline your approach in 2-3 sentences.",
    "Ask whether the approach fits; do not just write 'can I work on this?'.",
    "If someone claimed it recently, pick another issue rather than competing.",
]


# Project files that say how to install and test, in the order they are trusted.
_MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "Gemfile")

# Beginner labels GSoC organizations use under other names ("Starter" at Learning
# Unlimited), searched when --org names a few organizations.
_COMMON_BEGINNER_LABELS = (
    "good first issue",
    "good-first-issue",
    "starter",
    "beginner",
    "easy",
    "first-timers-only",
)
# An organization counts as matching someone's interests from this interest fit up; a
# passing mention in its description (LLVM mentions "embedded") stays below it.
INTEREST_MATCH = 0.5
HOW_RANKED = (
    "Fit compares your skills and interests with each organization's official listing, its "
    "ideas page, and its GitHub repositories; every reason names its source. It says how well "
    "the work matches you, not your chance of being accepted. See docs/recommendations.md."
)


# Repository descriptions that say no new work is wanted there.
_RETIRED_RE = re.compile(
    r"\b(?:deprecated|legacy|no longer (?:maintained|developed|accepting)|unmaintained|"
    r"read-only mirror|mirror of|archived)\b",
    re.I,
)


def _retired_repo(raw: dict[str, Any]) -> str | None:
    """Why a repository should get no new work, or None."""
    if raw.get("archived"):
        return (
            "The repository is archived, so it is read-only: nobody can comment or open "
            "a pull request there"
        )
    found = _RETIRED_RE.search(str(raw.get("description") or ""))
    return f"The repository's description says '{found.group(0)}'" if found else None


def _unlinked_caveat(pull: dict[str, Any]) -> str:
    """What a look-alike pull request that does not link the issue means for a newcomer."""
    title = clean_untrusted(pull.get("title"), limit=90)
    ref = f'PR #{pull.get("number")} "{title}"'
    if (pull.get("pull_request") or {}).get("merged_at"):
        return (
            f"Merged {ref} looks like the same work but does not link this issue; it may "
            "already be fixed, so ask in the thread before you start"
        )
    if pull.get("state") == "open":
        return (
            f"Open {ref} looks like the same work but does not link this issue; read it "
            "before you start, someone may already be on it"
        )
    return (
        f"{ref} tried what looks like the same work and was closed without merging; read "
        "its review comments first"
    )


def _dormant_days(raw: dict[str, Any]) -> int | None:
    """Days since anything was pushed to the repository, when that is over DORMANT_DAYS."""
    pushed = _parse_iso(raw.get("pushed_at"))
    days = (datetime.now(UTC) - pushed).days if pushed else 0
    return days if days > DORMANT_DAYS else None


# Skills that are not programming, for the "GSoC is a coding program" note.
_NOT_CODING = frozenset({"latex", "git", "html", "css"})


def _no_issue_note(orgs: list[dict[str, Any]]) -> str:
    """What to do when no first task is left, naming the best organization."""
    if not orgs:
        return "No open first task turned up right now. Ask in a community's chat which task suits a newcomer."
    name = str(orgs[0]["name"]).replace('"', "")
    return (
        "No open first task passed the checks in these organizations right now (announcements, "
        "trackers, claimed, old, or out-of-profile issues are left out). Look in "
        f'{orgs[0]["name"]}\'s repositories with `git-into-gsoc repos "{name}"` and '
        f'`git-into-gsoc issues --org "{name}"`, or ask in its chat which task would suit a '
        "newcomer."
    )


def participation_from(found: dict[str, Any]) -> dict[str, Any]:
    """What an organization's own posts say about a GSoC year (from gsoc_posts_for)."""
    if found.get("error"):
        return {"status": "unknown"}
    posts = found.get("posts") or []
    trusted = [p for p in posts if p.get("by_maintainer") or p.get("source") == "wiki"]
    for status in ("not_taking_part", "undecided", "mentions"):
        post = next((p for p in trusted if p.get("status") == status), None)
        if post:
            return {
                "status": "posted" if status == "mentions" else status,
                "url": post.get("url"),
                "title": post.get("title"),
            }
    return {"status": "no_post"}


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


# Where a newcomer should say hello, best first. A contact email reaches the
# org admins or mentors privately, so a public introduction never goes there.
_PUBLIC_CHANNEL_ORDER = ("chat", "irc", "forum", "mailingList")


def public_channels(channels: list[ContactChannel]) -> list[str]:
    """The org's public channels, chat first, leaving out private emails and blogs."""
    ranked = sorted(
        (c for c in channels if c.kind in _PUBLIC_CHANNEL_ORDER),
        key=lambda c: _PUBLIC_CHANNEL_ORDER.index(c.kind),
    )
    return [c.value for c in ranked]


def _mark_ideas_too_big(ideas: list[dict[str, Any]], hours_per_week: Any) -> str | None:
    """Mark ideas bigger than the saved hours allow, move them last, and say so.

    A beginner with 5 hours a week saw a 350-hour idea ranked as their best fit.
    """
    try:
        hours = int(hours_per_week or 0)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    capacity = hours * LONGEST_CODING_WEEKS
    too_big = 0
    for idea in ideas:
        idea["too_big_for_your_hours"] = bool(idea.get("hours") and idea["hours"] > capacity)
        too_big += idea["too_big_for_your_hours"]
    if not too_big:
        return None
    ideas.sort(key=lambda idea: idea["too_big_for_your_hours"])  # stable: fit order kept
    return (
        f"At {hours} hours a week you have about {capacity} hours in the longest coding "
        f"period ({LONGEST_CODING_WEEKS} weeks, only if your mentor agrees). {too_big} idea(s) "
        "here need more than that and are listed last. Ask a mentor whether a smaller version "
        f"would work. Source: {GSOC_FAQ_URL}"
    )


def _off_github_issue(link: str) -> dict[str, Any]:
    """A tracked issue on another code host: listed, but never re-checked."""
    return {
        "ref": link,
        "url": link,
        "availability": "unknown",
        "reason": "Not on GitHub, so it is not re-checked: look for an assignee, a linked "
        "merge request, and recent claims yourself",
        "previous": None,
        "changed": False,
        "off_github": True,
    }


def _when_no_issues(language: str | None, *, org: str | None, repo: str | None) -> list[str]:
    """What to try when a search finds no free beginner issues."""
    if repo:
        return [
            f"Read {repo}'s open issues yourself: a small bug, a docs gap, or a missing "
            "test is a fine first contribution even without a beginner label.",
            "Ask in the project's public channel which small task would help most.",
            f"Or pick another of its repositories: git-into-gsoc repos {repo.split('/')[0]}",
        ]
    where = f'"{org}"' if org else '"ORG NAME"'
    steps = (
        []
        if org
        else [
            "Pick an organization first: git-into-gsoc orgs"
            + (f" --tech {language}" if language else "")
        ]
    )
    steps.append(
        f"List its repositories: git-into-gsoc repos {where}, then "
        "git-into-gsoc issues --repo owner/name (it uses that repository's own beginner label)."
    )
    if not org:
        steps.append("Search every repository, not only GSoC organizations: add --scope all")
    steps.append(
        "Beginner labels go fast before GSoC. A small fix you find yourself counts too; "
        "ask in the project's channel before you start."
    )
    return steps


class GSoCToolkit:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.http = CachedHttpClient(self.settings)
        self.github = GitHubClient(self.settings, self.http)
        self.official = OfficialGSoCClient(self.settings, self.http)
        self.gsoc = GSoCClient(self.settings, self.http, self.official)
        self.archive = ArchiveClient(self.settings, self.http)
        self.progress = ProgressStore()

    def program_info(self, year: int | None = None, project_size: str = "medium") -> dict[str, Any]:
        year = validate_year(year, latest=latest_program_year(self.settings))
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
            "contributor_habits": overview["contributor_habits"],
            "profile_saved": bool(self.progress.profile().get("technologies")),
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
        check_posts: bool = False,
    ) -> dict[str, Any]:
        """Organizations ranked for the person. With `check_posts`, the top three are
        checked for posts about the coming year, and one that says it sits out moves last
        (one search each)."""
        from_profile = False
        saved = self.progress.profile()
        if not (query or technologies or topics or category):
            # No filters: rank for the person, as recommend and next do.
            technologies = list(saved.get("technologies") or []) or None
            topics = list(saved.get("interests") or []) or None
            from_profile = bool(technologies or topics)
        catalog, results, person = self.gsoc.rank_organizations(
            query=query,
            technologies=technologies,
            topics=topics,
            category=category,
            experience=effective_experience(saved)[0],
            hours_per_week=_int_or_none(saved.get("hours_per_week")),
            year=year,
            limit=limit,
        )
        return {
            "catalog": catalog.model_dump(),
            "matched_on": {
                "technologies": list(technologies or []),
                "topics": list(topics or []),
                "from_profile": from_profile,
                "experience": person.experience,
                "hours_per_week": person.hours_per_week,
            },
            "read_as": person.notes,
            "sharpen": self._sharpen(person, year),
            "notes": self._coverage(person, year),
            "count": len(results),
            "organizations": self.check_participation(
                [r.model_dump(exclude={"recent_projects"}) for r in results], check=3
            )
            if check_posts
            else [r.model_dump(exclude={"recent_projects"}) for r in results],
            "how_ranked": HOW_RANKED,
            "hint": self._empty_search_hint(query, catalog.year) if not results else None,
        }

    def _sharpen(self, person: ContributorProfile, year: int | None = None) -> list[dict[str, Any]]:
        """Narrower words to try when a skill or interest matches dozens of organizations."""
        try:
            _, index = self.gsoc.org_index(year)
        except GigError:
            return []
        return [
            {
                "word": tip["word"],
                "kind": tip["kind"],
                "matches": tip["matches"],
                "suggest": [{"words": name, "organizations": n} for name, n in tip["suggest"]],
            }
            for tip in index.sharpen(person)
        ]

    def _empty_search_hint(self, query: str | None, list_year: int) -> str:
        """Why nothing matched: often the name is an organization from an earlier year."""
        default = "Try broader --tech or --topics, or fewer words in --query."
        # A skill or subject word ("js", "robotics") is not an organization's name.
        if not query or len(query.strip()) < 4 or resolve_concept(query).concepts:
            return default
        try:
            name = self.gsoc.resolve_org_name(query)
        except GigError:
            return default
        current = {o.name for o in self.gsoc.catalog(None)[1]}
        if not name or name in current:
            return default
        years = sorted(
            int(y)
            for y in ((self.gsoc._history_for(name) or {}).get("years") or {})
            if str(y).isdigit()
        )
        if not years:
            return default
        shown = ", ".join(str(y) for y in years[-5:])
        return (
            f"{name} took part in GSoC in {shown}, but it is not on the official {list_year} "
            "list. Organizations apply again every year; check "
            "https://summerofcode.withgoogle.com when the next list is published, and run "
            f'`git-into-gsoc org "{name}"` to see its history.'
        )

    def org_details(self, name: str, year: int | None = None) -> dict[str, Any]:
        org = self.gsoc.get_organization(name, year=year)
        if not org:
            return self._org_not_found(name, year=year)
        catalog, _ = self.gsoc.catalog(year)
        result = {"found": True, "catalog": catalog.model_dump(), "organization": org.model_dump()}
        if org.github_orgs:
            result["gsoc_posts"] = self.gsoc_posts_for(org.github_orgs[:3], year=year)
        return result

    def gsoc_posts_for(self, owners: list[str], *, year: int | None = None) -> dict[str, Any]:
        """What these GitHub owners posted about a GSoC year (the coming one by default)."""
        year = year or self.settings.target_year
        try:
            posts = self.github.gsoc_year_posts(owners, year)
        except GigError as exc:
            return {"year": year, "posts": [], "error": exc.to_dict()}
        return {"year": year, "posts": posts[:6]}

    def check_participation(
        self, orgs: list[dict[str, Any]], *, year: int | None = None, check: int = 5
    ) -> list[dict[str, Any]]:
        """Check what the top organizations posted about the coming year, and act on it.

        An organization that says it will not take part keeps its place in the data
        but moves after the others, with the post as the first caveat. One whose
        maintainers posted about the year gets that as a readiness line. Costs one
        search (plus wiki reads) per checked organization; failures become
        "unknown". Returns a new list and leaves `orgs` unchanged.
        """
        year = year or self.settings.target_year
        out = [dict(org) for org in orgs]
        targets = [org for org in out[: max(0, check)] if org.get("github_orgs")]

        def one(org: dict[str, Any]) -> dict[str, Any]:
            return participation_from(self.gsoc_posts_for(list(org["github_orgs"])[:3], year=year))

        if targets:
            workers = min(len(targets), max(1, self.settings.max_concurrency))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(one, targets))
            for org, participation in zip(targets, results, strict=True):
                if participation["status"] == "unknown" and org.get("participation"):
                    continue  # the monthly check's answer stands
                org["participation"] = participation
                status = participation["status"]
                if status == "not_taking_part":
                    org["caveats"] = [
                        f"Says it will not take part in GSoC {year}: {participation['url']}",
                        *(org.get("caveats") or []),
                    ]
                elif status == "undecided":
                    org["caveats"] = [
                        *(org.get("caveats") or []),
                        f"Has not decided about GSoC {year} yet: {participation['url']}",
                    ]
                elif status == "posted":
                    org["readiness"] = [
                        f"Its maintainers posted about GSoC {year}: {participation['url']}",
                        *(org.get("readiness") or []),
                    ]
        return sorted(
            out, key=lambda o: (o.get("participation") or {}).get("status") == "not_taking_part"
        )

    def _org_not_found(self, name: str, *, year: int | None = None) -> dict[str, Any]:
        similar, mentioned_by = self.gsoc.suggest_organizations(name, year=year)
        hints = []
        if similar:
            hints.append("Did you mean: " + "; ".join(similar) + "?")
        if mentioned_by:
            hints.append(
                f"Organizations whose description mentions '{name}' (projects often take "
                "part under an umbrella organization): " + "; ".join(mentioned_by) + "."
            )
        return {
            "found": False,
            "error": f"No GSoC organization is named '{name}'",
            "did_you_mean": similar,
            "mentioned_by": mentioned_by,
            "hint": " ".join(hints)
            or "Check the spelling, or search by keyword with `orgs --query`.",
        }

    def past_projects(
        self,
        query: str | None = None,
        *,
        org: str | None = None,
        since: int | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        if org:
            resolved = self.gsoc.resolve_org_name(org)
            if resolved is None:
                return self._org_not_found(org)
            org = resolved
        projects = self.gsoc.search_projects(query, org=org, since=since, limit=limit)
        return {
            "org": org,
            "count": len(projects),
            "projects": [p.model_dump() for p in projects],
            "note": (
                "Accepted GSoC projects from the public archive. Use them to understand scope "
                "and what each org values. Never copy a past proposal."
            ),
        }

    def evaluate_repo(self, full_name: str) -> dict[str, Any]:
        owner, name = parse_repo(full_name)
        source = mirror_source(self.github.get_repo(owner, name))
        if source:
            # The mirror's pull requests and issues say nothing about the project.
            return {
                "full_name": f"{owner}/{name}",
                "mirror_of": source,
                "health": None,
                "recommendation": (
                    f"Not graded: {owner}/{name} is a read-only mirror of {source}. Its "
                    "GitHub history does not show how the project treats newcomers. Judge "
                    "the project, and contribute, where its code really lives."
                ),
            }
        health = self.github.repo_health(full_name)
        guide = self.github.contribution_guide(full_name)
        return {
            "health": health.model_dump(mode="json"),
            "contribution_guide": guide.model_dump(),
            "recommendation": _repo_recommendation(health.grade, health.warnings),
        }

    def gsoc_github_orgs(
        self,
        *,
        language: str | None = None,
        topics: list[str] | None = None,
        year: int | None = None,
        limit: int = 12,
    ) -> tuple[dict[str, str], list[str], str]:
        """Map GitHub owners to GSoC org names, plus an owner shortlist ranked by fit."""
        try:
            catalog, orgs = self.gsoc.catalog(year)
            _, ranked = self.gsoc.search_organizations(
                technologies=[language] if language else None,
                topics=topics or None,
                year=year,
                limit=60,
            )
        except HttpError:
            return {}, [], "GSoC org data unavailable; searched all of GitHub."
        owner_names = {gh.lower(): org.name for org in orgs for gh in org.github_orgs}
        if topics:
            # Only organizations whose work matches the interests, when there are enough.
            fitting = [o for o in ranked if (o.interest_fit or 0.0) >= INTEREST_MATCH]
            if len([o for o in fitting if o.github_orgs]) >= 3:
                ranked = fitting
            else:
                topics = None
        shortlist = [org.github_orgs[0] for org in ranked if org.github_orgs][:limit]
        note = (
            f"Searching GitHub orgs of GSoC {catalog.year} organizations"
            + (f" that use {language}" if language else "")
            + (f" and match your interests ({', '.join(topics)})" if topics else "")
            + ". Use --scope all to search every repository."
        )
        return owner_names, shortlist, note

    def discover_repos(
        self,
        org: str,
        *,
        language: str | None = None,
        limit: int = 10,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Rank an org's repositories for a first contribution.

        `org` may be a GSoC org name (resolved to its GitHub orgs and ideas page)
        or a GitHub login.
        """
        gsoc_org = self.gsoc.get_organization(org, year=year)
        if gsoc_org is None:
            owners = [validate_login(org, kind="GitHub org/user or GSoC org name")]
        else:
            # Umbrellas such as the Python Software Foundation list no GitHub owner
            # of their own; their projects are found through the ideas page below.
            owners = list(gsoc_org.github_orgs[:3])
        ideas_url = gsoc_org.ideas_url if gsoc_org else None
        ideas = fetch_ideas_text(self.http, ideas_url, self.settings.archive_ttl_seconds)
        # An umbrella organization's page only links to its member projects, which
        # live under their own GitHub owners; follow those links too.
        linked_owners: list[tuple[str, str]] = []
        linked_repos: set[str] = set()
        if gsoc_org and ideas_url:
            doc = fetch_ideas_document(self.http, ideas_url, self.settings.archive_ttl_seconds)
            if doc is not None and (doc.layout == "index" or not owners):
                linked_owners, linked_repos = _linked_github_projects(
                    doc.sub_pages or _github_links(ideas or ""),
                    exclude=owners,
                    any_link=not owners,
                )
        # Code hosted elsewhere (ns-3 and Inkscape on GitLab) cannot be ranked here.
        source = (gsoc_org.source_code or "") if gsoc_org else ""
        host = urlparse(source).netloc.lower().removeprefix("www.")
        main_code = source if source and not owners and host != "github.com" else None
        if gsoc_org is not None and not owners and not linked_owners:
            raise NotFoundError(
                f"{gsoc_org.name} lists no GitHub organization, and its ideas page links to "
                "no GitHub projects. Its code may live on GitLab or its own servers.",
                hint=f"Its code is at {main_code}; the ideas page is {ideas_url or 'not listed'}."
                if main_code
                else f"Open the ideas page to find its repositories: {ideas_url}"
                if ideas_url
                else "Check the organization's page on the official GSoC site.",
            )

        cutoff = datetime.now(UTC) - timedelta(days=365)
        person = self._saved_person(technologies=[language] if language else None)
        leads: list[RepoLead] = []
        for owner, via in [*((o, None) for o in owners), *linked_owners]:
            try:
                listed = self.github.list_owner_repos(owner, pages=2)
            except GigError:
                if via is None:
                    raise
                continue
            # Repositories with GitHub issues turned off stay: ScummVM's and Mifos's main
            # code track bugs elsewhere. Deprecated ones and mirrors go.
            repos = [
                r
                for r in listed
                if not r.get("fork")
                and not _retired_repo(r)
                and (_parse_iso(r.get("pushed_at")) or cutoff) >= cutoff
            ]
            ranked_by_stars = sorted(
                (r for r in repos if repo_kind(str(r.get("full_name"))) is None),
                key=lambda r: -int(r.get("stargazers_count") or 0),
            )
            top_starred = str(ranked_by_stars[0].get("full_name")) if ranked_by_stars else ""
            counts = self.github.beginner_issue_counts(owner) if repos else {}
            mentioned = mentioned_repos(ideas, [owner], repos) if ideas else set()
            for repo in repos:
                full = str(repo.get("full_name"))
                beginner = counts.get(full.lower(), 0)
                in_ideas = full.lower() in mentioned or full.lower() in linked_repos
                score, reasons = repo_lead_score(
                    repo,
                    beginner_issues=beginner,
                    ideas_mention=in_ideas,
                    language=language,
                    person=person,
                    main_repo=is_main_repo(full, most_starred=full == top_starred),
                )
                if via:
                    reasons.append(f"Linked from the umbrella ideas page ({via})")
                leads.append(
                    RepoLead(
                        full_name=full,
                        url=str(repo.get("html_url")),
                        description=clean_untrusted(repo.get("description"), limit=300) or None,
                        language=repo.get("language"),
                        stars=int(repo.get("stargazers_count") or 0),
                        pushed_at=_parse_iso(repo.get("pushed_at")),
                        open_beginner_issues=beginner,
                        ideas_mention=in_ideas,
                        score=score,
                        reasons=reasons,
                    )
                )
        searched = [*owners, *(o for o, _ in linked_owners)]
        leads.extend(self._repos_named_on_page(ideas or "", searched, language=language))
        leads.sort(key=lambda lead: (-lead.score, -lead.stars))
        return {
            "org": gsoc_org.name if gsoc_org else owners[0],
            "github_owners": [*owners, *(o for o, _ in linked_owners)],
            "linked_projects": [{"owner": o, "title": t} for o, t in linked_owners],
            "ideas_url": ideas_url,
            "ideas_page_read": bool(ideas),
            "count": min(limit, len(leads)),
            "repos": [lead.model_dump(mode="json") for lead in leads[:limit]],
            "main_code": main_code,
            "note": (
                f"{gsoc_org.name if gsoc_org else 'This organization'}'s own code is at "
                f"{main_code}, outside GitHub, so this tool cannot rank it. The repositories "
                "below are GitHub projects its ideas page links to; start with the main code "
                "unless an idea names one of them."
                if main_code
                else ""
            ),
            "next_step": "Run `repo owner/name` on your top pick, then `issues --repo owner/name`.",
        }

    def _gsoc_owners(self, name: str, *, language: str | None) -> tuple[list[str], list[str], str]:
        """A GSoC organization's own GitHub owners, the ones its ideas page links to, and a note.

        Both lists are empty when the name is not a GSoC organization with GitHub owners.
        """
        try:
            gsoc_org = self.gsoc.get_organization(name)
        except GigError:
            return [], [], ""
        if gsoc_org is None:
            return [], [], ""
        if not gsoc_org.github_orgs:
            return self._owners_off_github(gsoc_org, language=language)
        owners = list(gsoc_org.github_orgs[:3])
        ideas = fetch_ideas_text(self.http, gsoc_org.ideas_url, self.settings.archive_ttl_seconds)
        linked: list[str] = []
        for lead in self._repos_named_on_page(ideas or "", owners, language=language):
            owner = lead.full_name.split("/", 1)[0]
            if owner.lower() not in {o.lower() for o in [*owners, *linked]}:
                linked.append(owner)
        note = f"Searching {gsoc_org.name}: {', '.join(owners)}"
        if linked:
            note += f", and {', '.join(linked[:4])} (named on its ideas page)"
        return owners, linked[:4], note + "."

    def _owners_off_github(
        self, gsoc_org: OrgSummary, *, language: str | None
    ) -> tuple[list[str], list[str], str]:
        """For an org with no GitHub owner: the GitHub projects its ideas page names.

        An umbrella such as the Python Software Foundation lists member projects on
        GitHub. An org whose code lives elsewhere (GNOME on gitlab.gnome.org, KDE on
        invent.kde.org) gets a clear error naming that place, instead of being read
        as a mistyped GitHub login.
        """
        ideas = fetch_ideas_text(self.http, gsoc_org.ideas_url, self.settings.archive_ttl_seconds)
        linked: list[str] = []
        for lead in self._repos_named_on_page(ideas or "", [], language=language):
            owner = lead.full_name.split("/", 1)[0]
            if owner.lower() not in {o.lower() for o in linked}:
                linked.append(owner)
        if linked:
            note = (
                f"Searching {gsoc_org.name}: it lists no GitHub organization, so the GitHub "
                f"projects its ideas page names: {', '.join(linked[:4])}."
            )
            return [], linked[:4], note
        where = gsoc_org.source_code or gsoc_org.url or "its own site"
        raise NotFoundError(
            f"{gsoc_org.name} keeps its code outside GitHub ({where}), so this tool cannot "
            "search its issues",
            hint=f"Open {where} and look for a newcomer or beginner label, and read the ideas "
            f"page ({gsoc_org.ideas_url or 'not listed'}). org, ideas, mentors, projects, and "
            "proposal still work for this organization.",
        )

    def _repos_named_on_page(
        self, text: str, searched: list[str], *, language: str | None, limit: int = 6
    ) -> list[RepoLead]:
        """Organization-owned repositories an ideas page names under other GitHub owners.

        Open Robotics names colcon/colcon-mixin and open-rmf/crossflow on its page,
        outside its own openrobotics and osrf owners. A link to a person's repository
        is usually a reference or a mentor's profile, so only organizations count.
        """
        skip = {o.lower() for o in searched} | _NOT_OWNERS  # already listed in full
        named: list[str] = []
        for match in _GITHUB_PROJECT_RE.finditer(text):
            owner, repo = match.group(1), match.group(2)
            if not repo or owner.lower() in skip or repo.lower() in _NOT_REPOS:
                continue
            # A link to someone's pull request or commit is an example to follow,
            # not a project to work on: Zulip's page links a flutter/flutter PR.
            if _CHANGE_LINK_RE.match(text, match.end()):
                continue
            full = f"{owner}/{repo.removesuffix('.git')}"
            if full not in named:
                named.append(full)
        found: list[RepoLead] = []
        for full in named[:limit]:
            try:
                raw = self.github.get_repo(*full.split("/", 1))
            except GigError:
                continue
            if (raw.get("owner") or {}).get("type") != "Organization":
                continue
            if raw.get("archived") or raw.get("fork") or mirror_source(raw):
                continue  # a mirror's issues and pull requests live elsewhere
            score, reasons = repo_lead_score(
                raw, beginner_issues=0, ideas_mention=True, language=language
            )
            reasons.append("Under another GitHub owner that the ideas page links to")
            found.append(
                RepoLead(
                    full_name=str(raw.get("full_name") or full),
                    url=str(raw.get("html_url") or f"https://github.com/{full}"),
                    description=clean_untrusted(raw.get("description"), limit=300) or None,
                    language=raw.get("language"),
                    stars=int(raw.get("stargazers_count") or 0),
                    pushed_at=_parse_iso(raw.get("pushed_at")),
                    open_beginner_issues=0,
                    ideas_mention=True,
                    score=score,
                    reasons=reasons,
                )
            )
        return found

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
        from_profile = False
        asked_org = org  # cleared below when it names a GSoC organization
        self.github.rate_limited = None
        if not (language or org or repo):
            saved = list(self.progress.profile().get("technologies") or [])
            language, from_profile = (saved[0], True) if saved else (None, False)
        # Interests pick which organizations to search: C++ plus robotics should mean
        # robotics organizations that use C++, not every big C++ project.
        topics = None
        if scope == "gsoc" and not (org or repo):
            topics = list(self.progress.profile().get("interests") or []) or None
        owner_names, shortlist, note = self.gsoc_github_orgs(
            language=language, topics=topics, year=year
        )
        narrowed = bool(topics) and "match your interests" in note
        # --org may be a GSoC organization's name: search its GitHub owners and the
        # organizations whose repositories its ideas page names (Open Robotics lists
        # only openrobotics and osrf; its ROS work is under ros2 and open-rmf).
        gsoc_owners: list[str] = []
        linked: list[str] = []
        if org and not repo:
            own_owners, linked, owners_note = self._gsoc_owners(org, language=language)
            gsoc_owners = [*own_owners, *linked]
            if gsoc_owners:
                shortlist, org = gsoc_owners, None
                gsoc_name = owners_note.removeprefix("Searching ").split(":", 1)[0]
                # A linked project is not the organization's own: say where it came from.
                owner_names = {
                    **owner_names,
                    **{o.lower(): gsoc_name for o in own_owners},
                    **{o.lower(): f"named on the {gsoc_name} ideas page" for o in linked},
                }
        use_gsoc = scope == "gsoc" and not org and not repo and bool(shortlist)
        if gsoc_owners:
            note = owners_note
        elif not use_gsoc:
            note = "Searching " + (f"{repo}" if repo else f"org {org}" if org else "all of GitHub")
            if repo:
                # `repo` counts every unassigned beginner issue; this list is stricter.
                note += (
                    ". Left out: issues with an assignee or a linked pull request, and ones "
                    "not updated in a year, so `repo` may count more."
                )
        if from_profile:
            note += f" Using {language} from your saved profile; pass a language to change it."
        labels_used: list[str] = [label] if label else ["good first issue", "help wanted"]
        if gsoc_owners and not label:
            # A few named organizations: their own spellings fit in one query.
            labels_used = [*_COMMON_BEGINNER_LABELS, "help wanted"]
        if repo and not label:
            owner_name, repo_name = parse_repo(repo)
            taken = {x.lower() for x in labels_used}
            own = [
                name
                for name in beginner_labels(self.github.list_labels(owner_name, repo_name))
                if name.lower() not in taken
            ]
            if own:
                labels_used = [*own, *labels_used]
                quoted = ", ".join(f"'{name}'" for name in own)
                note += f" Using this repository's own beginner label(s) {quoted} first."
        issues = self.github.find_beginner_issues(
            language=language,
            org=org,
            orgs=shortlist if use_gsoc or gsoc_owners else None,
            repo=repo,
            labels=labels_used,
            max_results=max_results,
            org_names=owner_names,
        )
        if gsoc_owners and linked:
            # Free issues first; among them, the organization's own before linked projects.
            linked_owners = {o.lower() for o in linked}
            issues.sort(
                key=lambda i: (
                    i.availability != Availability.AVAILABLE,
                    i.repo.split("/", 1)[0].lower() in linked_owners,
                    -i.beginner_score,
                )
            )
            note += " Its own repositories come first, then the linked ones."
        if use_gsoc and narrowed and not gsoc_owners and len(issues) < 3:
            # Too few in the organizations that fit the interests: keep those first and
            # fill the list from every organization that uses the language.
            first = len(issues)
            owner_names, shortlist, _ = self.gsoc_github_orgs(language=language, year=year)
            wider = self.github.find_beginner_issues(
                language=language,
                orgs=shortlist,
                labels=labels_used,
                max_results=max_results,
                org_names=owner_names,
            )
            have = {(i.repo, i.number) for i in issues}
            fits = {*have}
            issues = [*issues, *(i for i in wider if (i.repo, i.number) not in have)]
            # Free issues first; among them, the organizations that fit the interests.
            issues.sort(
                key=lambda i: (
                    i.availability != Availability.AVAILABLE,
                    (i.repo, i.number) not in fits,
                    -i.beginner_score,
                )
            )
            issues = issues[:max_results]
            note += (
                f" Only {first} issue(s) came from those; the rest are from other "
                f"organizations that use {language}."
                if len(issues) > first
                else f" Other organizations that use {language} had none free either."
            )
        if use_gsoc and language:
            note += self._skipped_off_github(language, year=year)
        related = RELATED_LANGUAGES.get(canonical(language), []) if language else []
        if related and not repo:
            note += (
                f" Also searching {', '.join(related)} repositories, which often hold this work."
            )
        unchecked = sum(i.availability == Availability.UNKNOWN for i in issues)
        limit = self.github.rate_limited
        if unchecked and limit is not None:
            # Otherwise half a list can read "unknown" with no word about why.
            # First, so it is not lost at the end of the other notes.
            when = reset_phrase(limit.reset_at)
            note = (
                f"GitHub's request limit ran out, so {unchecked} issue(s) marked unknown were "
                "not checked for claims or pull requests."
                + (f" It {when}." if when else "")
                + (f" {limit.hint}" if limit.hint else "")
                + f" {note}"
            )
        return {
            "scope": "gsoc" if use_gsoc else "custom",
            "language_used": language,
            "labels_used": labels_used,
            "note": note,
            "count": len(issues),
            # What in each issue fits the saved profile; the order above stands.
            "issues": personalize(
                [_issue_dict(i) for i in issues], self._saved_person(), reorder=False
            ),
            "before_you_comment": BEFORE_YOU_COMMENT,
            "next_steps": [] if issues else _when_no_issues(language, org=asked_org, repo=repo),
        }

    def issue_status(self, ref: str, number: int | None = None) -> dict[str, Any]:
        if number is None and parse_gitlab_issue(ref):
            # GNOME, KDE, and others keep issues on GitLab; its public API has the basics.
            found = gitlab_issue_status(
                self.http,
                ref,
                token=self.settings.gitlab_token,
                token_host=self.settings.gitlab_host,
            )
            return {**found, "before_you_comment": BEFORE_YOU_COMMENT}
        owner, repo, num = parse_issue_ref(ref, number)
        issue, assessment = self.github.assess(f"{owner}/{repo}", num)
        # The issue alone cannot show that nobody will review the work: a real check
        # (2026-10-22) called issues "available" in an archived repository and in one
        # with nothing pushed for 28 months.
        try:
            raw_repo = self.github.get_repo(owner, repo)
        except GigError:
            raw_repo = {}
        retired = _retired_repo(raw_repo)
        if raw_repo.get("archived") and assessment.availability != Availability.CLOSED:
            assessment.availability = Availability.NOT_OPEN
            assessment.reason = f"{retired}; pick another issue"
            # Nobody can post in its threads, so advice to ask there does not apply.
            assessment.caveats = [c for c in assessment.caveats if "in the thread" not in c]
        elif retired:
            assessment.caveats.append(f"{retired}; ask the project whether it still takes work")
        # A pull request that names no issue leaves no trace on its timeline.
        linked = {p.number for p in assessment.linked_prs}
        self.github.rate_limited = None
        try:
            unlinked = self.github.unlinked_pulls(owner, repo, issue)
        except GigError:
            unlinked = []
        for pull in [p for p in unlinked if p.get("number") not in linked][:2]:
            assessment.caveats.append(_unlinked_caveat(pull))
        if (limit := self.github.rate_limited) is not None:
            # Silence would read as "no look-alike pull requests", which is not known.
            when = reset_phrase(limit.reset_at)
            assessment.caveats.append(
                "GitHub's search limit stopped the check for pull requests that look like "
                "the same work" + (f"; it {when}, so run this again then" if when else "")
            )
        dormant = _dormant_days(raw_repo)
        if dormant and not raw_repo.get("archived"):
            assessment.caveats.append(
                f"Nothing has been pushed to this repository for {dormant // 30} months, so a "
                "pull request may wait a long time for review; ask the project whether it is "
                "still maintained before you start"
            )
        return {
            "repo": f"{owner}/{repo}",
            "number": num,
            "title": clean_untrusted(issue.get("title"), limit=256),
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

    def contribution_evidence(
        self,
        username: str,
        *,
        org: str | None = None,
        repo: str | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """What `username` has done in an org's repos, as proposal-ready evidence."""
        owners: list[str] = []
        gsoc_org = None
        if org and not repo:
            gsoc_org = self.gsoc.get_organization(org, year=year)
            owners = list((gsoc_org.github_orgs if gsoc_org else [])[:3])
            if not owners:
                owners = [validate_login(org, kind="GitHub org or GSoC org name")]
        activity = self.github.user_activity(username, owners=owners or None, repo=repo)
        return {
            "scope": {
                "org": gsoc_org.name if gsoc_org else org,
                "github_owners": owners,
                "repo": repo,
            },
            **activity,
            "how_to_use": [
                "Paste the evidence lines into the 'About you' / prior contributions section.",
                "Mention what each PR taught you about the codebase, not just that it merged.",
                "Reviewers can see the same history; never list work you did not do.",
            ],
        }

    def profile_from_github(self, username: str) -> dict[str, Any]:
        profile = self.github.infer_profile_languages(username)
        merged = self.github.merged_pull_requests_elsewhere(username)
        if merged is not None:
            profile["merged_prs_elsewhere"] = merged
        self.progress.set_profile(
            github=username,
            **{
                k: profile.get(k)
                for k in ("top_language", "languages", "bio", "merged_prs_elsewhere")
            },
        )
        return profile

    def save_profile(
        self,
        *,
        github: str | None = None,
        technologies: list[str] | None = None,
        interests: list[str] | None = None,
        hours_per_week: int | None = None,
        timezone: str | None = None,
        experience: str | None = None,
    ) -> dict[str, Any]:
        """Save the self-profile that personalises recommendations and `next`.

        The username is saved even when GitHub cannot be reached; only the language
        summary read from public repositories waits for the next online run. A user
        that does not exist is still an error.
        """
        warning = None
        if experience is not None and experience.strip().lower() not in EXPERIENCE_LEVELS:
            raise InputError(
                f"Unknown experience level '{experience}'.",
                hint="Use one of: " + ", ".join(EXPERIENCE_LEVELS) + f" ({EXPERIENCE_HELP}).",
            )
        if github:
            login = validate_login(github)
            try:
                self.profile_from_github(login)
            except NotFoundError:
                raise
            except HttpError as exc:
                self.progress.set_profile(github=login)
                warning = (
                    f"Saved @{login}, but GitHub could not be reached ({exc}). Run "
                    f"`profile --github {login}` again when online to add your languages."
                )
        self.progress.set_profile(
            technologies=[plain_skill(t) for t in technologies or []] or None,
            interests=[plain_skill(t) for t in interests or []] or None,
            hours_per_week=hours_per_week,
            timezone=timezone,
            experience=experience.strip().lower() if experience else None,
        )
        profile = self.progress.profile()
        level, source = effective_experience(profile)
        if level and not profile.get("experience"):
            profile["experience_inferred"] = {"level": level, "from": source}
        if warning:
            profile["warning"] = warning
        if hours_per_week is not None and hours_note(hours_per_week):
            profile["hours_note"] = hours_note(hours_per_week)
        return profile

    def _saved_person(
        self,
        *,
        technologies: list[str] | None = None,
        interests: list[str] | None = None,
        experience: str | None = None,
        hours_per_week: int | None = None,
    ) -> ContributorProfile:
        """The person as saved, with any of the given values in place of the saved ones."""
        saved = self.progress.profile()
        return build_profile(
            technologies=technologies or list(saved.get("technologies") or []),
            interests=interests or list(saved.get("interests") or []),
            experience=experience or effective_experience(saved)[0],
            hours_per_week=hours_per_week or _int_or_none(saved.get("hours_per_week")),
        )

    def recommend_path(
        self,
        *,
        username: str | None = None,
        technologies: list[str] | None = None,
        interests: list[str] | None = None,
        experience: str | None = None,
        hours_per_week: int | None = None,
        check_posts: bool = True,
    ) -> dict[str, Any]:
        """Organizations, ideas, starter issues, and a learning path for one person.

        Every organization comes with its fit, the evidence for it, and caveats.
        With `check_posts`, the top five are checked for posts saying they will not
        take part in the coming year (one search each).
        """
        if experience is not None and experience.strip().lower() not in EXPERIENCE_LEVELS:
            raise InputError(
                f"Unknown experience level '{experience}'.",
                hint="Use one of: " + ", ".join(EXPERIENCE_LEVELS) + f" ({EXPERIENCE_HELP}).",
            )
        saved = self.progress.profile()
        technologies = [plain_skill(t) for t in technologies or []] or None
        interests = [plain_skill(t) for t in interests or []] or None
        techs = list(technologies or [])
        wants = list(interests or [])
        source = "flags" if techs or wants or username else "saved profile"
        if technologies or interests:
            self.progress.set_profile(technologies=technologies, interests=interests)
        if not techs:
            techs = list(saved.get("technologies") or [])
        if not wants:
            wants = list(saved.get("interests") or [])
        profile = None
        username = username or (saved.get("github") if not techs else None)
        if username:
            profile = self.profile_from_github(username)
            top = profile.get("top_language")
            if top and top.lower() not in {t.lower() for t in techs}:
                techs.insert(0, top)
            saved = self.progress.profile()
        if not (techs or wants):
            source = "none"
        level, level_source = (
            (experience.strip().lower(), "you said so")
            if experience
            else effective_experience(saved)
        )
        hours = hours_per_week or _int_or_none(saved.get("hours_per_week"))

        target = self.settings.target_year
        catalog, ranked, person = self.gsoc.rank_organizations(
            technologies=techs or None,
            topics=wants or None,
            experience=level,
            hours_per_week=hours,
            limit=20,
        )
        # Eight to show; the first twenty also decide which wider issues are close enough.
        nearby_names = {o.name for o in ranked}
        nearby_owners = {gh.lower() for o in ranked for gh in o.github_orgs}
        orgs = [o.model_dump(exclude={"recent_projects"}) for o in ranked[:8]]
        if check_posts and orgs:
            # One search each; without a token GitHub allows ten a minute, shared with
            # the issue search below.
            checked = 5 if self.settings.resolve_github_token() else 3
            orgs = self.check_participation(orgs, year=target, check=checked)
        taking_part = [
            o for o in orgs if (o.get("participation") or {}).get("status") != "not_taking_part"
        ]
        ideas = self._ideas_that_fit(taking_part[:3], person)

        languages = languages_of(person)
        issue_language = languages[0] if languages else (techs[0] if techs else None)
        issues: list[dict[str, Any]] = []
        issue_error: dict[str, str] | None = None
        issue_scope = None
        hidden = 0
        skipped = 0
        # Up to two GitHub owners for each of the first six organizations: projects
        # often keep their beginner work in a second owner (a web app, a docs site).
        owners: dict[str, str] = {}
        for o in taking_part[:6]:
            for gh in (o.get("github_orgs") or [])[:2]:
                if len(owners) < 12:
                    owners.setdefault(gh, o["name"])
        sitting_out = {
            owner.lower()
            for o in orgs
            if (o.get("participation") or {}).get("status") == "not_taking_part"
            for owner in o.get("github_orgs") or []
        }

        def screen(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
            """First tasks only: free, from nearby organizations still taking part, not an
            announcement, a tracker, years old, in a retired repository, or out of profile."""
            near = [
                i
                for i in candidates
                if str(i["repo"]).split("/")[0].lower() not in sitting_out
                and not is_event_repo(str(i["repo"]))
                and (
                    str(i["repo"]).split("/")[0].lower() in nearby_owners
                    or i.get("gsoc_org") in nearby_names
                )
            ]
            unique = list({(i["repo"], i["number"]): i for i in near}.values())
            free = [i for i in unique if _open(i)]
            good = [i for i in free if starter_problem(i, person) is None]
            good = self._without_retired_repos(good, languages)
            return good, len(unique) - len(free), len(free) - len(good)

        if issue_language or owners:
            try:
                candidates: list[dict[str, Any]] = []
                if owners:
                    found = self.github.find_beginner_issues(
                        language=languages or issue_language,
                        orgs=list(owners),
                        # Not "help wanted": it mostly marks work too big for a first task.
                        labels=list(_COMMON_BEGINNER_LABELS),
                        org_names={k.lower(): v for k, v in owners.items()},
                        max_results=15,
                        # Issues the starter screen would call too old never take a slot.
                        created_after=f"{datetime.now(UTC).year - OLD_ISSUE_YEARS + 1}-01-01",
                    )
                    candidates = [_issue_dict(i) for i in found]
                    issue_scope = "the recommended organizations above"
                screened, hidden, skipped = screen(candidates)
                if len(screened) < 3 and issue_language:
                    broad = self.find_issues(language=issue_language, max_results=5)
                    candidates += broad["issues"]
                    issue_scope = (
                        f"{issue_scope}, then other GSoC organizations that use {issue_language}"
                        if issue_scope
                        else f"GSoC organizations that use {issue_language}"
                    )
                    screened, hidden, skipped = screen(candidates)
                if len(screened) < 2 and self.settings.resolve_github_token():
                    # Each of the two best organizations on its own, with the projects its
                    # ideas page names and the beginner labels it really uses.
                    for o in taking_part[:2]:
                        try:
                            own = self.find_issues(
                                org=o["name"], language=issue_language, max_results=4
                            )
                        except GigError:
                            continue
                        candidates += own["issues"]
                    screened, hidden, skipped = screen(candidates)
                issues = personalize(screened, person)[:5]
            except GigError as exc:
                issue_error = exc.to_dict()

        confirmed = catalog.year >= target
        program_note = (
            f"These organizations are on Google's official GSoC {catalog.year} list."
            if confirmed
            else f"Google has not announced the GSoC {target} organizations yet. These "
            f"took part in {catalog.year}, which is the best guide to who returns, but "
            "none is confirmed until the official list is published."
        )
        program = {
            "target_year": target,
            "list_year": catalog.year,
            "confirmed": confirmed,
            "note": program_note,
        }
        note = HOW_RANKED + " " + program_note
        if source == "none":
            note = (
                "No technologies or interests given and no saved profile. Run "
                "`profile --tech ... --interests ...` once, or pass --tech/--interests. " + note
            )
        return {
            "profile": profile,
            "profile_source": source,
            "technologies_used": techs,
            "interests_used": wants,
            "read_as": person.notes,
            "sharpen": self._sharpen(person),
            "experience": {"level": level, "from": level_source},
            "hours_per_week": hours,
            "hours_note": hours_note(hours) if hours else None,
            "program": program,
            "recommended_orgs": orgs,
            "ideas_that_fit": ideas,
            "starter_issues": issues,
            "starter_issue_scope": issue_scope,
            "starter_issues_hidden": hidden,
            "starter_issue_error": issue_error,
            "starter_issues_skipped": skipped,
            "starter_issue_note": None if issues or issue_error else _no_issue_note(taking_part),
            "notes": self._recommend_notes(person, level),
            "learning_path": learning_path(person, taking_part, ideas),
            "next_steps": [
                "Shortlist three organizations and join their community channels",
                "Check one or two of their main repositories for health and a contributing guide",
                "Make one meaningful contribution before writing a proposal",
                "Read Google's AI guidance and each organization's AI policy",
            ],
            "evidence_note": note,
        }

    def _without_retired_repos(
        self, issues: list[dict[str, Any]], languages: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Leave out issues in repositories that are retired or have gone quiet for a year,
        and, given the person's languages, in repositories mostly written in another one."""
        keep = []
        verdicts: dict[str, bool] = {}
        wanted = {canonical(x) for x in language_family(languages or [])}
        for issue in issues:
            repo = str(issue.get("repo") or "")
            if repo not in verdicts:
                try:
                    raw = self.github.get_repo(*repo.split("/", 1))
                except (GigError, ValueError):
                    verdicts[repo] = True
                else:
                    main = canonical(str(raw.get("language") or ""))
                    off_language = bool(wanted) and bool(main) and main not in wanted
                    verdicts[repo] = not (_retired_repo(raw) or _dormant_days(raw) or off_language)
            if verdicts[repo]:
                keep.append(issue)
        return keep

    def _coverage(self, person: ContributorProfile, year: int | None = None) -> list[str]:
        try:
            _, index = self.gsoc.org_index(year)
        except GigError:
            return []
        return index.coverage(person)

    def _recommend_notes(self, person: ContributorProfile, level: str | None) -> list[str]:
        """Facts that decide whether and where someone can apply, with their source."""
        notes = self._coverage(person)
        if level == "experienced":
            notes.append(
                'GSoC is for students and beginners to open source. The FAQ says: "GSoC is '
                'not for experienced open source developers" and "Regular contributors to an '
                f'open source project are not beginners." Source: {GSOC_FAQ_URL}'
            )
        coding = [
            c
            for w in person.skills
            for c in w.concepts
            if kind_of(c) == SKILL and c not in _NOT_CODING
        ]
        if person.skills and not coding:
            notes.append(
                'GSoC projects are coding projects ("Participants write code for an open '
                'source organization", from the FAQ). Documentation and design work is a good '
                f"way to start in a community, but a proposal needs code. Source: {GSOC_FAQ_URL}"
            )
        notes.append(
            "To take part you must be 18 or older when you register, and a student or a "
            f"beginner to open source. Source: {GSOC_FAQ_URL}"
        )
        return notes

    def _ideas_that_fit(
        self, orgs: list[dict[str, Any]], person: ContributorProfile
    ) -> list[dict[str, Any]]:
        """Ideas from each organization's last ideas page that match the person (offline)."""
        signals = load_signals()
        year = signals.get("year")
        target = self.settings.target_year
        out = []
        for org in orgs:
            ideas = (signals_for(org.get("slug")).get("ideas") or {}) if org.get("slug") else {}
            picked = ideas_for(
                list(ideas.get("ideas") or []),
                person,
                year=year,
                source_url=org.get("ideas_url") or ideas.get("url"),
            )
            if picked:
                out.append(
                    {
                        "org": org["name"],
                        "ideas_url": org.get("ideas_url") or ideas.get("url"),
                        "year": year,
                        "note": (
                            f"From its GSoC {year} ideas page. {target} ideas usually appear "
                            "in January or February; use these to see the kind of work."
                            if year and year < target
                            else f"From its GSoC {year} ideas page."
                        ),
                        "ideas": picked,
                    }
                )
        return out

    def check_proposal(
        self,
        text: str,
        *,
        github: str | None = None,
        verify: bool = True,
        ideas_text: str | None = None,
    ) -> dict[str, Any]:
        """Structural and evidence checks on a draft proposal (never rewrites it)."""
        from git_into_gsoc.proposal import check_proposal

        def lookup(repo: str, number: int) -> dict[str, Any] | None:
            owner, name = repo.split("/", 1)
            return self.github.get_pull(owner, name, number)

        def mr_lookup(host: str, path: str, iid: int) -> dict[str, Any] | None:
            # Public GitLab instances answer this without a token. The HTTP client
            # refuses local and private addresses, so a link cannot reach them.
            url = f"https://{host}/api/v4/projects/{quote(path, safe='')}/merge_requests/{iid}"
            try:
                data = self.http.get_json(url, ttl=900)
            except GigError:
                return None
            return data if isinstance(data, dict) else None

        report = check_proposal(
            text,
            github_user=github,
            lookup=lookup if verify else None,
            ideas_text=ideas_text,
            mr_lookup=mr_lookup if verify else None,
        )
        # True only when at least one link was actually checked against its host.
        report["links_verified"] = any(link["verified"] for link in report["links"])
        report["checklist"] = [i.model_dump() for i in proposal_checklist()]
        return report

    def proposal_help(self) -> dict[str, Any]:
        return {
            "checklist": [i.model_dump() for i in proposal_checklist()],
            "structure": [
                "Synopsis: one paragraph on the problem and what you will deliver",
                "Benefits to the community",
                "Deliverables, and what is out of scope",
                "Implementation plan with milestones",
                "Week-by-week timeline, with spare time for surprises",
                "Related work and design notes",
                "About you: relevant experience and links to your contributions",
                "How you will use AI, following the organization's policy",
            ],
            "warnings": [
                "Generic AI-written essays are often rejected. See Google's guidance on low-quality proposals.",
                "Submit only through the official GSoC website.",
                "Earlier interaction with the organization is often the strongest signal in your favor.",
            ],
        }

    def rate_limit(self) -> dict[str, Any]:
        return self.github.rate_limit()

    # ------------------------------------------------------------- next steps

    def next_steps(
        self,
        *,
        year: int | None = None,
        now: datetime | None = None,
        recheck: bool = True,
    ) -> dict[str, Any]:
        """What to do right now: phase, deadlines, tracked-issue changes, new issues, actions."""
        now = now or datetime.now(UTC)
        year = year or self.settings.target_year
        offline = False
        try:
            official = self.official.program(year)
        except HttpError:
            official, offline = None, True
        program = program_status(year, official_program=official, offline=offline, now=now)
        state = self.progress.load()

        tracked: list[dict[str, Any]] = []
        changes: list[str] = []
        statuses: dict[str, str] = {}
        if recheck and state.tracked_issues:
            refs: list[tuple[str, str, str, int]] = []
            for raw in state.tracked_issues[:10]:
                try:
                    owner, repo, num = parse_issue_ref(raw)
                except GigError:
                    if parse_gitlab_issue(raw):
                        tracked.append(self._tracked_gitlab_issue(raw, state.issue_status))
                    elif other_host_link(raw):
                        tracked.append(_off_github_issue(raw))
                    continue
                refs.append((raw, f"{owner}/{repo}", f"{owner}/{repo}#{num}", num))
            with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
                futures = [
                    (raw, full, key, pool.submit(self._availability_of, full, num))
                    for raw, full, key, num in refs
                ]
                for raw, full, key, future in futures:
                    status, reason = future.result()
                    previous = state.issue_status.get(key)
                    statuses[key] = status
                    entry = {
                        "ref": key,
                        "url": raw
                        if raw.startswith("http")
                        else f"https://github.com/{full}/issues/{key.rsplit('#', 1)[1]}",
                        "availability": status,
                        "reason": reason,
                        "previous": previous,
                        "changed": bool(previous and previous != status),
                    }
                    tracked.append(entry)
                    if entry["changed"]:
                        changes.append(f"{key} went from {previous} to {status}: {reason}")

        new_issues = self._new_beginner_issues(state, now=now) if recheck else []
        org_posts = self._shortlist_posts(state, year) if recheck else []
        github_login = str((state.profile or {}).get("github") or "").strip()
        open_prs = (
            self.open_pull_requests(github_login, now=now) if recheck and github_login else []
        )
        merged = self.merged_pull_requests(github_login) if recheck and github_login else []
        recorded = {str(c.get("ref")) for c in state.contributions}
        newly_merged = [m for m in merged if m["ref"] not in recorded]
        # Only one merged pull request in someone else's project, ever, and it is new.
        first_merge = len(merged) == 1 and bool(newly_merged)
        if newly_merged:
            with contextlib.suppress(InputError):
                for item in newly_merged:
                    self.progress.add_contribution(kind="merged_pull_request", **item)
        # A first run records older merges quietly; only recent ones are news.
        news_since = state.last_checked_at or now - timedelta(days=14)
        merged_news = [m for m in newly_merged if _after(m.get("merged_at"), news_since)]
        if recheck:
            # Where the progress folder cannot be written (a sandboxed assistant), the
            # results still count; the next run just reports the same changes again.
            with contextlib.suppress(InputError):
                self.progress.mark_checked(statuses, now)

        # Plan around orgs that are taking part; one that says it is sitting out goes last.
        sitting_out = {p["org"] for p in org_posts if p["status"] == "not_taking_part"}
        if sitting_out:
            ordered = sorted(state.shortlisted_orgs, key=lambda name: name in sitting_out)
            state = state.model_copy(update={"shortlisted_orgs": ordered})
        actions = plan_actions(
            state,
            program,
            tracked_issues=tracked,
            new_issues=new_issues,
            open_pull_requests=open_prs,
            now=now,
            code_elsewhere=self._code_elsewhere(state.shortlisted_orgs[:3]),
        )
        for item in reversed(merged_news[:2]):
            actions.insert(
                0,
                {
                    "title": f"{item['ref']} was merged. Write down what you did and learned "
                    "while it is fresh",
                    "command": f'git-into-gsoc log --done "Merged {item["ref"]}" '
                    f'--links {item["url"]} --learned "..."',
                    "why": "Notes like this become the evidence in your proposal.",
                },
            )
        for post in reversed([p for p in org_posts if p["status"] == "not_taking_part"]):
            actions.insert(
                0,
                {
                    "title": f"{post['org']} says it will not take part in GSoC {year}. "
                    "Read the post, then consider replacing it on your shortlist",
                    "command": "git-into-gsoc recommend",
                    "why": post["url"],
                },
            )
        return {
            "checked_at": now.isoformat(),
            "last_checked_at": state.last_checked_at.isoformat() if state.last_checked_at else None,
            "program": {
                "year": program["year"],
                "phase": program["phase"],
                "dates_are_official": program["dates_are_official"],
                "source": program["source"],
            },
            "deadlines": upcoming_deadlines(program),
            "time_budget": time_budget(state, program, now=now),
            "hours_note": hours_note((state.profile or {}).get("hours_per_week")),
            "progress": self.progress.summary(),
            "tracked_issues": tracked,
            "open_pull_requests": open_prs,
            "merged_pull_requests": merged_news,
            "first_merge": first_merge and bool(merged_news),
            "changes": changes,
            "new_issues": new_issues,
            "org_posts": org_posts,
            "actions": actions,
            "note": (
                "Actions are suggestions from your saved progress and public data. "
                "Dates for unpublished years are estimates; verify on the official site."
            ),
        }

    # ---------------------------------------------------------- orientation

    def orient_repo(self, full_name: str, *, codetour: bool = False) -> dict[str, Any]:
        """A one-screen orientation sheet: facts and paths only, about 20 API calls."""
        owner, repo = parse_repo(full_name)
        raw = self.github.get_repo(owner, repo)
        owner, repo = (raw.get("full_name") or f"{owner}/{repo}").split("/", 1)
        branch = str(raw.get("default_branch") or "HEAD")
        workers = self.settings.max_concurrency
        with ThreadPoolExecutor(max_workers=workers) as pool:
            tree_f = pool.submit(self.github.git_tree, owner, repo, branch)
            langs_f = pool.submit(self.github.languages, owner, repo)
            profile_f = pool.submit(self.github.community_profile, owner, repo)
            commits_f = pool.submit(self.github.list_commits, owner, repo, since=since_iso(90))
            pulls_f = pool.submit(self.github.list_pulls, owner, repo, state="closed", per_page=30)
            rules_f = pool.submit(self.github.branch_rules, owner, repo, branch)
            tree, langs = tree_f.result(), langs_f.result()
            profile, commits, pulls = profile_f.result(), commits_f.result(), pulls_f.result()
            branch_rules = rules_f.result()
        entries = list(tree.get("tree") or [])
        found = find_paths(entries)
        if not found.get("contributing"):
            html = ((profile.get("files") or {}).get("contributing") or {}).get("html_url")
            if html and "/blob/" in html:
                found["contributing"] = html.split("/blob/", 1)[1].split("/", 1)[1]

        workflow_paths = rank_workflows(found.get("workflows") or [])
        gate_paths = rank_gate_workflows(found.get("workflows") or [], skip=workflow_paths)
        raw_wanted = {
            key: found[key]
            for key in ("contributing", "pr_template", "pyproject", "package_json", "codeowners")
            if found.get(key)
        }
        texts: dict[str, str] = {}
        workflow_texts: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                key: pool.submit(self.github.get_raw_file, owner, repo, path)
                for key, path in raw_wanted.items()
            }
            wf_futures = {
                path: pool.submit(self.github.get_raw_file, owner, repo, path)
                for path in [*workflow_paths, *gate_paths]
            }
            for key, future in futures.items():
                texts[key] = future.result() or ""
            for path, future in wf_futures.items():
                workflow_texts[path] = future.result() or ""
        found["test_dirs"] = ci_test_dirs_first(found.get("test_dirs") or [], workflow_texts)

        merged = [p for p in pulls if p.get("merged_at") and not is_bot(p.get("user"))]
        check_names: list[str] = []
        if merged and (merged[0].get("head") or {}).get("sha"):
            check_names = self.github.check_run_names(owner, repo, str(merged[0]["head"]["sha"]))
        example = self._example_outsider_pr(owner, repo, merged)

        points = entry_points(
            entries, pyproject=texts.get("pyproject"), package_json=texts.get("package_json")
        )
        rules = conventions(
            commits,
            contributing=texts.get("contributing", ""),
            pr_template=texts.get("pr_template", ""),
            check_names=check_names,
            found=found,
        )
        rules["gates"] = branch_gates(branch_rules, branch=branch) + workflow_gates(workflow_texts)
        quotes = policy_quotes(
            {
                str(found.get("contributing") or "CONTRIBUTING"): texts.get("contributing", ""),
                str(found.get("pr_template") or "PR template"): texts.get("pr_template", ""),
            }
        )
        total_bytes = sum(langs.values()) or 1
        languages = [
            {"name": name, "share": round(100 * size / total_bytes)}
            for name, size in sorted(langs.items(), key=lambda kv: -kv[1])[:4]
        ]
        tests = ci_test_commands({p: workflow_texts.get(p, "") for p in workflow_paths})
        environment = ci_environment({p: workflow_texts.get(p, "") for p in workflow_paths})
        result: dict[str, Any]
        fallback_hints = [
            f"{found['makefile']} lists local targets" if found.get("makefile") else "",
            "Dev container present: open in Codespaces or VS Code for a ready environment"
            if found.get("devcontainer")
            else "",
        ]
        result = {
            "repo": f"{owner}/{repo}",
            "url": raw.get("html_url") or f"https://github.com/{owner}/{repo}",
            "description": clean_untrusted(raw.get("description"), limit=300),
            "default_branch": branch,
            "as_of_commit": tree.get("sha"),
            "tree_truncated": bool(tree.get("truncated")),
            "stars": int(raw.get("stargazers_count") or 0),
            "license": _license_label(raw.get("license")),
            "pushed_days_ago": days_since(raw.get("pushed_at")),
            "languages": languages,
            "code_map": code_map(entries, repo_name=repo),
            "entry_points": points,
            "test_commands": tests,
            "ci_environment": environment,
            "setup_hints": [h for h in fallback_hints if h],
            "docs": {
                "readme": found.get("readme"),
                "contributing": found.get("contributing"),
                "architecture": found.get("architecture_docs") or [],
                "governance": found.get("governance"),
                "test_dirs": found.get("test_dirs") or [],
            },
            "maintainers": {
                "active_committers_90d": active_committers(commits),
                "commits_90d": len(commits),
                "codeowners": codeowners_for(texts.get("codeowners", "")),
                "codeowners_path": found.get("codeowners"),
            },
            "conventions": rules,
            "policies": quotes,
            "channels": channels_in(texts.get("contributing", "")),
            "example_pr": example,
            "reading_plan": reading_plan(found=found, points=points, example_pr=example),
            "note": (
                "Purpose labels on the code map are guesses from directory names. Everything "
                "else names a real file, commit, or check. Read the files; do not rely on a summary."
            ),
        }
        if codetour:
            result["codetour"] = codetour_from_orientation(result)
        return result

    def _example_outsider_pr(
        self, owner: str, repo: str, merged: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """A recently merged, small PR by someone without write access (at most 2 lookups).

        GitHub marks anyone whose PR merged as a CONTRIBUTOR, maintainers included, so
        people who can be assigned issues (the public sign of write access) are skipped.
        """
        insiders = {login.lower() for login in self.github.list_assignees(owner, repo) or ()}
        candidates = [
            p
            for p in merged
            if p.get("author_association") in OUTSIDER_ROLES
            and str((p.get("user") or {}).get("login") or "").lower() not in insiders
        ][:2]
        for pull in candidates:
            files = self.github.list_pull_files(owner, repo, int(pull["number"]))
            if files and len(files) <= 6:
                return {
                    "number": int(pull["number"]),
                    "url": pull.get("html_url"),
                    "title": clean_untrusted(pull.get("title"), limit=120),
                    "author": (pull.get("user") or {}).get("login"),
                    "files": len(files),
                    "paths": [str(f.get("filename")) for f in files[:6]],
                    "touches_tests": any(
                        "test" in str(f.get("filename", "")).lower() for f in files
                    ),
                }
        return None

    # ------------------------------------------------------------- pointers

    def issue_pointers(
        self,
        ref: str,
        number: int | None = None,
        *,
        similar: int = 5,
        code_search: bool = True,
    ) -> dict[str, Any]:
        """Where to start reading for one issue: resolved paths, past fixes, fix norms."""
        owner, repo, num = parse_issue_ref(ref, number)
        full = f"{owner}/{repo}"
        issue = self.github.get_issue(owner, repo, num)
        if "pull_request" in issue:
            raise InputError(
                f"{full}#{num} is a pull request, not an issue",
                hint="Pass the issue number the PR addresses.",
            )
        raw = self.github.get_repo(owner, repo)
        branch = str(raw.get("default_branch") or "HEAD")
        tree = self.github.git_tree(owner, repo, branch)
        tree_paths = [str(e.get("path")) for e in tree.get("tree") or [] if e.get("type") == "blob"]
        text = f"{issue.get('title') or ''}\n{issue.get('body') or ''}"
        mentions = extract_mentions(text, repo=full)
        resolved = resolve_paths(mentions, tree_paths)
        resolved_paths = {r["path"] for r in resolved}

        searched: list[dict[str, Any]] = []
        unresolved = [
            m["text"]
            for m in mentions
            if m["kind"] in {"identifier", "backtick"} and m["text"] not in resolved_paths
        ][:4]
        code_search_note = ""
        if code_search and unresolved and self.github.token:
            for ident in unresolved[:2]:
                try:
                    hits = self.github.search_code(f'"{ident}" repo:{full}', per_page=8)
                except HttpError as exc:
                    code_search_note = f"Code search stopped: {exc}"
                    break
                paths = [str(h.get("path")) for h in hits if h.get("path")]
                paths = code_first(
                    [p for p in paths if not p.startswith(("node_modules/", "vendor/"))]
                )
                searched.append({"identifier": ident, "paths": paths[:6]})
                for path in paths[:3]:
                    if path not in resolved_paths:
                        resolved_paths.add(path)
                        resolved.append(
                            {
                                "path": path,
                                "score": 1.0,
                                "lines": [],
                                "reasons": [f"code search: {ident}"],
                                "confidence": "code search",
                            }
                        )
        elif code_search and unresolved and not self.github.token:
            code_search_note = (
                "Code search needs a GitHub token (run `gh auth login`); search links are "
                "given instead."
            )
        words = title_keywords(str(issue.get("title") or ""), exclude=(owner, repo))
        if code_search and not resolved and not unresolved and words and self.github.token:
            # Nothing in the issue names a file: search the code for its title words.
            try:
                hits = self.github.search_code(f"{' '.join(words)} repo:{full}", per_page=8)
                if not hits and len(words) > 1:
                    # Both words together found nothing; the longest one alone may.
                    words = words[:1]
                    hits = self.github.search_code(f"{words[0]} repo:{full}", per_page=8)
            except HttpError as exc:
                hits, code_search_note = [], f"Code search stopped: {exc}"
            paths = [str(h.get("path")) for h in hits if h.get("path")]
            paths = code_first([p for p in paths if not p.startswith(("node_modules/", "vendor/"))])
            if paths:
                searched.append({"identifier": " ".join(words), "paths": paths[:6]})
            for path in paths[:3]:
                resolved_paths.add(path)
                resolved.append(
                    {
                        "path": path,
                        "score": 0.5,
                        "lines": [],
                        "reasons": [f"code search for the title words: {', '.join(words)}"],
                        "confidence": "title words",
                    }
                )

        if not resolved:
            # No file named and no code search result: try title words as a file name.
            resolved = title_file_matches(str(issue.get("title") or ""), tree_paths)
        fixes, label, similar_note, shared = self._similar_fixes(owner, repo, issue, limit=similar)
        norm = fix_norm(fixes)
        search_links = [
            {
                "identifier": ident,
                "url": f"https://github.com/search?type=code&q=repo%3A{owner}%2F{repo}+%22{ident}%22",
            }
            for ident in unresolved
            if not any(s["identifier"] == ident for s in searched)
        ]
        return {
            "issue": {
                "repo": full,
                "number": num,
                "title": clean_untrusted(issue.get("title"), limit=200),
                "url": issue.get("html_url") or f"https://github.com/{full}/issues/{num}",
                "labels": [
                    lab.get("name") for lab in issue.get("labels") or [] if isinstance(lab, dict)
                ],
            },
            "as_of_commit": tree.get("sha"),
            "files_likely_involved": resolved[:8],
            "code_search": searched,
            "search_links": search_links[:4],
            "code_search_note": code_search_note,
            "similar_fixes": fixes,
            "similar_label": label,
            "similar_note": similar_note,
            "similar_shares_title_words": shared,
            "fix_norm": norm,
            "next_step": (
                "Open the files above and the fix PRs for similar issues before touching code. "
                "If no file resolved, the issue needs clarification: ask in the thread what "
                "part of the code it concerns."
            ),
            "note": "Pointers are places to read, not a diagnosis. The fix is yours to work out.",
        }

    def _similar_fixes(
        self, owner: str, repo: str, issue: dict[str, Any], *, limit: int
    ) -> tuple[list[dict[str, Any]], str | None, str, bool]:
        """Closed issues with the same beginner label, the PRs that closed them, a note, and
        whether they share title words with this issue (False: just the most recent)."""
        full = f"{owner}/{repo}"
        labels = self.github.list_labels(owner, repo)
        label = pick_beginner_label(labels)
        if not label:
            own = [
                str(lab.get("name"))
                for lab in issue.get("labels") or []
                if isinstance(lab, dict) and lab.get("name")
            ]
            label = own[0] if own else None
        if not label:
            return [], None, "No beginner label found to look up similar closed issues.", False
        query = f"repo:{full} is:issue is:closed label:{_quote_label(label)}"
        try:
            items = self.github.search_issues(query, per_page=30)
        except HttpError as exc:
            return [], label, f"Could not search similar issues: {exc}", False
        items = [
            i for i in items if "pull_request" not in i and i.get("number") != issue.get("number")
        ]
        if not items:
            return [], label, f"No closed issues carry the '{label}' label yet.", False
        # Same label is not the same problem: prefer closed issues sharing title words.
        items, shared = rank_similar(str(issue.get("title") or ""), items, limit=limit)
        basis = (
            ""
            if shared
            else (
                f"None of the closed '{label}' issues share words with this title; "
                "these are the most recent ones."
            )
        )
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            timelines = list(
                pool.map(
                    lambda i: self.github.get_issue_timeline(owner, repo, int(i["number"])), items
                )
            )
        closers = [
            closing_pull_request(i, t or [], repo=full)
            for i, t in zip(items, timelines, strict=True)
        ]
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            files = list(
                pool.map(
                    lambda c: self.github.list_pull_files(owner, repo, c["number"]) if c else [],
                    closers,
                )
            )
        fixes = []
        for item, closer, changed in zip(items, closers, files, strict=True):
            if not closer:
                continue
            fixes.append(
                {
                    "issue": {
                        "number": int(item["number"]),
                        "title": clean_untrusted(item.get("title"), limit=120),
                        "url": item.get("html_url"),
                    },
                    "pull_request": closer,
                    "files": [str(f.get("filename")) for f in changed[:12]],
                    "additions": sum(int(f.get("additions") or 0) for f in changed),
                    "deletions": sum(int(f.get("deletions") or 0) for f in changed),
                    "days_to_merge": days_between(closer.get("opened_at"), closer.get("merged_at")),
                }
            )
        kind = "similar" if shared else "recent"
        note = (
            f"{len(fixes)} of {len(items)} {kind} closed issues had a traceable fix PR."
            if fixes
            else f"{len(items)} {kind} closed issues found, but none closed by a traceable PR."
        )
        return fixes, label, f"{basis} {note}".strip(), shared

    # --------------------------------------------------------------- drafts

    def draft(
        self,
        kind: str,
        *,
        org: str | None = None,
        repo: str | None = None,
        issue: str | None = None,
    ) -> dict[str, Any]:
        """A message skeleton with evidence fields and sourced rules, using real context."""
        if kind not in DRAFT_KINDS:
            raise InputError(
                f"Unknown draft kind: {kind!r}", hint="Choose one of: " + ", ".join(DRAFT_KINDS)
            )
        context: dict[str, Any] = {"year": self.settings.target_year}
        profile = self.progress.profile()
        if profile.get("github"):
            context["handle"] = profile["github"]
        if org:
            found = self.gsoc.get_organization(org)
            if found:
                context["org"] = found.name
                if not found.github_orgs and found.source_code:
                    # "GitLab: <handle>" for GNOME, not a GitHub handle it never uses.
                    host = urlparse(found.source_code).netloc.removeprefix("www.")
                    context["code_host"] = "GitLab" if "gitlab" in host else host or None
                context["channels"], closed = self._open_channels(public_channels(found.channels))
                if closed:
                    context["closed_channels"] = closed
        if issue:
            owner, name, num = parse_issue_ref(issue)
            repo = repo or f"{owner}/{name}"
            context["issue"] = {"repo": f"{owner}/{name}", "number": num}
            try:
                status = self.issue_status(issue)
                context["issue"]["title"] = clean_untrusted(status.get("title"), limit=200)
                context["issue"]["availability"] = status.get("availability")
                context["issue"]["reason"] = status.get("reason")
            except GigError as exc:
                context["issue"]["note"] = str(exc)
        if repo:
            context["repo"] = repo
            if kind == "pr":
                try:
                    owner_name, repo_name = parse_repo(repo)
                    meta = self.github.get_repo(owner_name, repo_name)
                    context["default_branch"] = str(meta.get("default_branch") or "") or None
                    if context["default_branch"]:
                        found_rules = self.github.branch_rules(
                            owner_name, repo_name, context["default_branch"]
                        )
                        context["gates"] = [
                            g["gate"]
                            for g in branch_gates(found_rules, branch=context["default_branch"])
                        ]
                except GigError:
                    pass
                # The commands CI really runs, instead of "<the project's test command>".
                try:
                    ci = self._ci_setup(repo)
                    context["test_commands"] = [c["command"] for c in ci["test_commands"]]
                    context["install_commands"] = [c["command"] for c in ci["install_commands"]]
                    context["commands_source"] = "CI"
                    if not context["test_commands"]:
                        # No test step in CI: use the project's own manifest, and say so.
                        root = self.github.root_listing(owner_name, repo_name)
                        names = {str(e.get("name")) for e in root}
                        package = (
                            self.github.get_raw_file(owner_name, repo_name, "package.json")
                            if "package.json" in names
                            else None
                        )
                        install, check = manifest_commands(names, package_json=package)
                        if install or check:
                            context["install_commands"] = install
                            context["test_commands"] = [check] if check else []
                            context["test_is_build"] = bool(check and "build" in check)
                            context["commands_source"] = next(
                                (n for n in _MANIFESTS if n in names),
                                "the project's files",
                            )
                except GigError:
                    pass
            if kind in {"pr", "claim"}:
                self._add_pr_rules(repo, context)
            guide = self.github.contribution_guide(repo)
            context["channels"] = context.get("channels") or guide.communication_channels
            text = guide.contributing_text or guide.contributing_excerpt
            context["claim_convention"] = claim_convention(text)
            context["dco"] = bool(
                re.search(r"Signed-off-by|git commit -s|Developer Certificate", text)
            )
            context["ai_disclosure"] = context.get("ai_disclosure") or bool(
                re.search(r"\bai\b.*disclos", text, re.I | re.S)
            )
            context["contributing_url"] = guide.contributing_url
        if kind == "status":
            latest = self.progress.recent_logs(limit=1)
            if latest:
                context["log"] = latest[0].model_dump(mode="json")
        draft = render_draft(kind, context=context)
        draft["context"] = {
            k: v
            for k, v in context.items()
            if k in {"org", "channels", "issue", "claim_convention", "contributing_url"}
        }
        warnings: list[str] = []
        if context.get("issue", {}).get("availability") not in (None, "available"):
            issue_info = context["issue"]
            if issue_info["availability"] == "not_open" and kind == "claim":
                # Nothing to copy: a claim here would be turned down.
                ref = f"{issue_info['repo']}#{issue_info['number']}"
                draft["template"] = (
                    f"Do not comment on {ref} to claim it.\n\n"
                    f"Find another issue: git-into-gsoc issues --repo {issue_info['repo']}"
                )
                warnings.append(f"Do not post a claim: {issue_info.get('reason')}.")
            else:
                warnings.append(
                    f"Issue availability is {issue_info['availability']}; check the thread "
                    "before claiming."
                )
        for url in context.get("closed_channels") or []:
            warnings.append(
                f"The organization lists {url}, but GitHub Discussions are turned off there. "
                "Look for the current channel in the project's README or CONTRIBUTING file."
            )
        if warnings:
            draft["warning"] = " ".join(warnings)
        return draft

    def _add_pr_rules(self, repo: str, context: dict[str, Any]) -> None:
        """The repository's own pull request template and workflow gates, into `context`.

        learning-unlimited/ESP-Website's template asks for an AI disclosure, and a
        workflow closes pull requests from anyone not assigned to the issue; the
        generic draft said neither.
        """
        try:
            owner, name = parse_repo(repo)
            branch = str(self.github.get_repo(owner, name).get("default_branch") or "HEAD")
            found = find_paths(list(self.github.git_tree(owner, name, branch).get("tree") or []))
        except GigError:
            return
        template_path = found.get("pr_template")
        gate_paths = rank_gate_workflows(found.get("workflows") or [], skip=[])
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            template_f = (
                pool.submit(self.github.get_raw_file, owner, name, template_path)
                if template_path
                else None
            )
            gate_f = {p: pool.submit(self.github.get_raw_file, owner, name, p) for p in gate_paths}
            template = (template_f.result() if template_f else None) or ""
            gate_texts = {p: f.result() or "" for p, f in gate_f.items()}
        if template_path:
            context["pr_template_path"] = template_path
        if re.search(r"\bai\b.*disclos|disclos.*\bai\b", template, re.I | re.S):
            context["ai_disclosure"] = True
        gates = [g["gate"] for g in workflow_gates(gate_texts)]
        context["gates"] = list(dict.fromkeys([*(context.get("gates") or []), *gates]))

    def _open_channels(self, channels: list[str]) -> tuple[list[str], list[str]]:
        """Split channels into usable ones and GitHub Discussions links that are turned off.

        GSoC records go stale: Learning Unlimited's 2026 entry links Discussions on a
        repository that has them disabled, so the link is a 404.
        """
        usable: list[str] = []
        closed: list[str] = []
        for url in channels:
            match = _DISCUSSIONS_RE.search(url)
            if match:
                try:
                    meta = self.github.get_repo(match.group(1), match.group(2))
                except GigError:
                    meta = {}
                if meta and meta.get("has_discussions") is False:
                    closed.append(url)
                    continue
            usable.append(url)
        return usable, closed

    # ---------------------------------------------------------------- mentors

    def org_mentors(self, name: str, *, years: int = 3, limit: int = 25) -> dict[str, Any]:
        """Who mentored this org's completed projects in recent years, from the archive."""
        org = self.gsoc.get_organization(name)
        if org is None:
            return self._org_not_found(name)
        projects = self.archive.projects_by_year(years=years)
        summary = summarize_mentors(projects, org_slug=org.slug, org_name=org.name, limit=limit)
        return {
            "found": True,
            **summary,
            "source": "Official GSoC archive (completed projects only)",
            "note": (
                "Mentor names come from the public archive of completed projects, so they "
                "show who has mentored before, not who will mentor next year. Contact people "
                "in the organization's public channel, never by private message."
            ),
        }

    # ------------------------------------------------------------ project ideas

    def org_ideas(
        self,
        name: str,
        *,
        year: int | None = None,
        skills: list[str] | None = None,
        size: str | None = None,
        difficulty: str | None = None,
        limit: int = 20,
        follow: bool = True,
    ) -> dict[str, Any]:
        """Structured project ideas from an org's ideas page, ranked for the contributor."""
        org = self.gsoc.get_organization(name, year=year)
        if org is None:
            return self._org_not_found(name, year=year)
        base = {"found": True, "org": org.name, "ideas_url": org.ideas_url}
        catalog, _ = self.gsoc.catalog(year)
        target = year or self.settings.target_year
        stale = (
            f"This is the ideas page from GSoC {catalog.year}. Organizations publish their "
            f"{target} ideas when they apply, usually in January or February. Until then, use "
            f"it to learn what the organization works on, not to choose a {target} project. "
            if catalog.year < target
            else ""
        )
        base["page_year"] = catalog.year
        if not org.ideas_url:
            return {
                **base,
                "layout": "missing",
                "ideas": [],
                "note": "This organization lists no ideas page. Check its contributor guide "
                + (f"at {org.guide_url}." if org.guide_url else "and website."),
            }
        ttl = self.settings.archive_ttl_seconds
        issues_target = issues_page_target(org.ideas_url)
        if issues_target:
            doc = self._ideas_from_issues(org.ideas_url, *issues_target)
        else:
            doc = fetch_ideas_document(self.http, org.ideas_url, ttl)
        if doc is None:
            return {
                **base,
                "layout": "unreachable",
                "ideas": [],
                "note": "The ideas page could not be fetched or read automatically. Open it in "
                "a browser; some wikis block automated readers.",
            }
        followed: list[dict[str, str]] = []
        if follow and doc.layout == "index" and doc.sub_pages:
            for page in [p for p in doc.sub_pages if _looks_like_ideas_page(p)][:8]:
                child = fetch_ideas_document(self.http, page["url"], ttl)
                if child is None or not child.ideas:
                    continue
                for idea in child.ideas:
                    idea.section = page["title"]
                doc.ideas.extend(child.ideas)
                doc.ai_policy = list(dict.fromkeys([*doc.ai_policy, *child.ai_policy]))
                followed.append(page)
        if doc.layout == "index" and not followed and doc.fallback_ideas:
            # The links led to no ideas, so the page's own prose blocks are the ideas.
            doc.ideas = list(doc.fallback_ideas)
            doc.layout = "headings"
        wanted = list(skills or []) or list(self.progress.profile().get("technologies") or [])
        saved = self.progress.profile()
        ranked = rank_ideas(
            doc.ideas,
            skills=wanted or None,
            size=size,
            difficulty=difficulty,
            interests=list(saved.get("interests") or []) or None,
            experience=effective_experience(saved)[0],
            hours_per_week=_int_or_none(saved.get("hours_per_week")),
        )
        idea_dicts = [i.model_dump(mode="json") for i in ranked]
        hours_note = _mark_ideas_too_big(idea_dicts, self.progress.profile().get("hours_per_week"))
        proposals = proposal_folders(
            lambda owner, repo: list(self.github.git_tree(owner, repo, "HEAD").get("tree") or []),
            org.name,
        )
        return {
            **base,
            "past_proposals": proposals,
            "past_proposals_note": (
                "Accepted proposals other people chose to share, in community archives. Read "
                "them to calibrate scope and structure; never copy text, and remember they "
                "contain personal details."
                if proposals
                else "No shared past proposals found for this organization in the known archives."
            ),
            "fetched_url": doc.fetched_url,
            "layout": doc.layout,
            "count": len(ranked),
            "ideas": idea_dicts[: max(1, limit)],
            "hours_note": hours_note,
            "skills_matched_on": wanted,
            "ai_policy": doc.ai_policy,
            "sub_pages": doc.sub_pages[:40] if doc.layout == "index" else [],
            "followed": followed,
            "headings": doc.headings[:30] if not doc.ideas else [],
            "note": stale + _ideas_note(doc, followed),
            "next_step": (
                "Read the full idea on the page before contacting a mentor. Never copy its text "
                "into a proposal; reviewers compare proposals with the ideas page."
            ),
        }

    def _ideas_from_issues(self, url: str, full_name: str, label: str) -> IdeasDocument | None:
        query = f"repo:{full_name} is:issue is:open label:{_quote_label(label)}"
        try:
            items = self.github.search_issues(query, per_page=50, sort="updated")
        except HttpError:
            return None
        doc = IdeasDocument(source_url=url, fetched_url=url, layout="issues")
        for item in items:
            if "pull_request" in item:
                continue
            body = str(item.get("body") or "")
            doc.ideas.append(
                ProjectIdea(
                    title=clean_untrusted(item.get("title") or f"#{item.get('number')}", limit=200),
                    description=clean_untrusted(body, limit=500),
                    links=[str(item.get("html_url") or "")],
                    skills=[],
                    confidence="medium",
                    source_url=str(item.get("html_url") or url),
                )
            )
        return doc

    def _availability_of(self, full_name: str, number: int) -> tuple[str, str]:
        """(status, reason) for one tracked issue; never raises."""
        try:
            _, assessment = self.github.assess(full_name, number)
        except NotFoundError:
            return "unknown", "Issue not found"
        except GigError as exc:
            return "unknown", str(exc)
        # Carry the first caution (an old claim in the thread) so `next` and `issue` agree.
        caveat = f" ({assessment.caveats[0]})" if assessment.caveats else ""
        return assessment.availability.value, assessment.reason + caveat

    def pr_check(self, ref: str, number: int | None = None) -> dict[str, Any]:
        """Check one pull request against the repository's own rules before review.

        Reuses what `orient` reads (contributing guide, pull request template,
        branch rules, gate workflows, recent commit style) and applies it to the
        pull request's description, commits, files, and checks. About ten calls.
        """
        owner, repo, num = parse_issue_ref(ref, number)
        pull = self.github.get_pull(owner, repo, num)
        if not pull:
            raise InputError(
                f"{owner}/{repo}#{num} is not a pull request GitHub can show",
                hint="Pass a pull request reference such as owner/repo#123 or its URL.",
            )
        base = str((pull.get("base") or {}).get("ref") or "HEAD")
        sha = str((pull.get("head") or {}).get("sha") or "")
        workers = self.settings.max_concurrency
        with ThreadPoolExecutor(max_workers=workers) as pool:
            files_f = pool.submit(self.github.list_pull_files, owner, repo, num)
            commits_f = pool.submit(self.github.pull_commits, owner, repo, num)
            checks_f = pool.submit(self.github.check_runs, owner, repo, sha) if sha else None
            tree_f = pool.submit(self.github.git_tree, owner, repo, base)
            rules_f = pool.submit(self.github.branch_rules, owner, repo, base)
            history_f = pool.submit(self.github.list_commits, owner, repo, since=since_iso(90))
            files, commits = files_f.result(), commits_f.result()
            checks = checks_f.result() if checks_f else []
            tree, branch_rules, history = tree_f.result(), rules_f.result(), history_f.result()
        found = find_paths(list(tree.get("tree") or []))
        wanted = {k: found[k] for k in ("contributing", "pr_template") if found.get(k)}
        gate_paths = rank_gate_workflows(found.get("workflows") or [], skip=[])
        with ThreadPoolExecutor(max_workers=workers) as pool:
            text_f = {
                k: pool.submit(self.github.get_raw_file, owner, repo, p) for k, p in wanted.items()
            }
            gate_f = {p: pool.submit(self.github.get_raw_file, owner, repo, p) for p in gate_paths}
            texts = {k: f.result() or "" for k, f in text_f.items()}
            gate_texts = {p: f.result() or "" for p, f in gate_f.items()}
        rules = conventions(
            history,
            contributing=texts.get("contributing", ""),
            pr_template=texts.get("pr_template", ""),
            check_names=[str(c.get("name")) for c in checks if c.get("name")],
            found=found,
        )
        rules["gates"] = branch_gates(branch_rules, branch=base) + workflow_gates(gate_texts)
        report = check_pull_request(
            pull,
            files,
            commits,
            checks,
            rules=rules,
            pr_template=texts.get("pr_template", ""),
            test_dirs=found.get("test_dirs") or [],
            news_dir=found.get("news_fragments"),
        )
        return {
            "ref": f"{owner}/{repo}#{num}",
            "url": pull.get("html_url"),
            "title": clean_untrusted(pull.get("title"), limit=160),
            "author": (pull.get("user") or {}).get("login"),
            **report,
            "note": (
                "Checks what the repository's own files and settings ask for. It cannot judge "
                "whether the change is right; only reviewers can."
            ),
        }

    def _ci_setup(self, repo: str) -> dict[str, Any]:
        """What the repository's CI sets up and runs: environment, install, and test commands."""
        owner, name = parse_repo(repo)
        raw = self.github.get_repo(owner, name)
        branch = str(raw.get("default_branch") or "HEAD")
        found = find_paths(list(self.github.git_tree(owner, name, branch).get("tree") or []))
        paths = rank_workflows(found.get("workflows") or [])
        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            texts = {
                p: f.result() or ""
                for p, f in {
                    p: pool.submit(self.github.get_raw_file, owner, name, p) for p in paths
                }.items()
            }
        return {
            **ci_environment(texts),
            "test_commands": ci_test_commands(texts),
            "install_commands": ci_install_commands(texts),
        }

    def diagnose(self, text: str, *, repo: str | None = None) -> dict[str, Any]:
        """Likely causes for failed setup or test output; with `repo`, what its CI sets up."""
        from git_into_gsoc.diagnose import diagnose_output

        ci = self._ci_setup(repo) if repo else None
        report = diagnose_output(text, ci=ci)
        report["repo"] = repo
        return report

    def check_message(self, kind: str, text: str) -> dict[str, Any]:
        """Check a message the contributor wrote against the rules for its kind."""
        from git_into_gsoc.drafts import check_message

        if kind not in DRAFT_KINDS:
            raise InputError(
                f"Unknown draft kind: {kind!r}", hint="Choose one of: " + ", ".join(DRAFT_KINDS)
            )
        return check_message(kind, text)

    def merged_pull_requests(self, username: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """The contributor's latest merged pull requests in other people's repositories.

        One search. Failures return nothing, so `next` never stops over it.
        """
        login = validate_login(username, kind="GitHub username")
        try:
            items = self.github.search_issues(
                f"is:pr is:merged author:{login} -user:{login}", per_page=limit
            )
        except GigError:
            return []
        found: list[dict[str, Any]] = []
        for item in items:
            parts = str(item.get("repository_url") or "").rstrip("/").split("/")
            merged_at = (item.get("pull_request") or {}).get("merged_at")
            if len(parts) < 2 or not item.get("number") or not merged_at:
                continue
            found.append(
                {
                    "ref": f"{parts[-2]}/{parts[-1]}#{item['number']}",
                    "url": str(item.get("html_url") or ""),
                    "title": clean_untrusted(item.get("title"), limit=160),
                    "merged_at": str(merged_at),
                }
            )
        return found

    def open_pull_requests(
        self, username: str, *, now: datetime | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """The contributor's open pull requests, sorted into "needs you" and "waiting".

        One search plus three calls per pull request (details, timeline, checks),
        for the most recently updated few. Pull requests in the person's own
        repositories are left out: nobody else is there to review them.
        Failures leave that pull request out.
        """
        login = validate_login(username, kind="GitHub username")
        try:
            items = self.github.search_issues(
                f"is:pr is:open author:{login} -user:{login} archived:false", per_page=limit
            )
        except GigError:
            return []

        def one(item: dict[str, Any]) -> dict[str, Any] | None:
            parts = str(item.get("repository_url") or "").rstrip("/").split("/")
            if len(parts) < 2 or not item.get("number"):
                return None
            owner, repo, number = parts[-2], parts[-1], int(item["number"])
            pull = self.github.get_pull(owner, repo, number)
            if not pull:
                return None
            timeline = self.github.get_issue_timeline(owner, repo, number) or []
            sha = str((pull.get("head") or {}).get("sha") or "")
            checks = self.github.check_runs(owner, repo, sha) if sha else []
            status = pull_request_status(pull, timeline, checks, now=now)
            status["title"] = clean_untrusted(status.get("title"), limit=160)
            return status

        with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
            found = [r for r in pool.map(one, items[:limit]) if r]
        found.sort(key=lambda r: (r["status"] != "needs_you", -(r.get("quiet_days") or 0)))
        return found

    def _tracked_gitlab_issue(self, link: str, previous: dict[str, str]) -> dict[str, Any]:
        """A tracked GitLab issue, re-checked through the host's public API when it answers."""
        try:
            found = gitlab_issue_status(
                self.http,
                link,
                token=self.settings.gitlab_token,
                token_host=self.settings.gitlab_host,
            )
        except GigError:
            return _off_github_issue(link)
        before = previous.get(link)
        return {
            "ref": link,
            "url": found["url"],
            "availability": found["availability"],
            "reason": found["reason"],
            "previous": before,
            "changed": bool(before and before != found["availability"]),
            "off_github": True,
        }

    def _skipped_off_github(self, language: str, *, year: int | None) -> str:
        """A note naming organizations that use `language` but keep code outside GitHub.

        `issues --language c` left out GNOME, FFmpeg, and VideoLAN without a word, so a
        C developer never learned they exist. This reads only the embedded list.
        """
        try:
            _, ranked = self.gsoc.search_organizations(technologies=[language], year=year, limit=60)
        except GigError:
            return ""
        names = [org.name for org in ranked if not org.github_orgs]
        if not names:
            return ""
        shown = ", ".join(names[:3]) + (f", and {len(names) - 3} more" if len(names) > 3 else "")
        return (
            f" Not searched, because their code is outside GitHub: {shown}. "
            'See git-into-gsoc org "NAME" for where each one keeps its issues.'
        )

    def _code_elsewhere(self, names: list[str]) -> dict[str, str]:
        """Shortlisted organizations with no GitHub owner, and where their code is."""
        found: dict[str, str] = {}
        for name in names:
            try:
                org = self.gsoc.get_organization(name)
            except GigError:
                continue
            if org and not org.github_orgs:
                found[name] = org.source_code or org.url or "its own site"
        return found

    def _shortlist_posts(self, state: ProgressState, year: int) -> list[dict[str, Any]]:
        """Maintainer posts about `year` in the shortlisted orgs' repositories."""
        owners: dict[str, str] = {}
        for name in state.shortlisted_orgs[:5]:
            try:
                org = self.gsoc.get_organization(name)
            except GigError:
                continue
            # Keep the name as saved on the shortlist, so planning can match it.
            for owner in (org.github_orgs if org else [])[:2]:
                owners.setdefault(owner.lower(), name)
        if not owners:
            return []
        found = self.gsoc_posts_for(list(owners), year=year)["posts"]
        # A wiki statement has no author to check, but it only counts when it says
        # the org will not take part or has not decided.
        posts = [p for p in found if p["by_maintainer"] or p.get("source") == "wiki"]
        for post in posts:
            post["org"] = owners.get(post["repo"].split("/")[0].lower(), post["repo"])
        return posts[:5]

    def _new_beginner_issues(self, state: ProgressState, *, now: datetime) -> list[dict[str, Any]]:
        """Beginner issues created in tracked repos / shortlisted orgs since the last check."""
        since = state.last_checked_at or (now - timedelta(days=14))
        scope: list[str] = []
        for raw in state.tracked_repos[:10]:
            try:
                owner, repo = parse_repo(raw)
            except GigError:
                continue
            scope.append(f"repo:{owner}/{repo}")
        for name in state.shortlisted_orgs[:5]:
            try:
                org = self.gsoc.get_organization(name)
            except GigError:
                org = None
            if org and org.github_orgs:
                scope.append(f"org:{org.github_orgs[0]}")
        scope = list(dict.fromkeys(scope))
        if not scope:
            return []
        repos_scope = [q.split(":", 1)[1] for q in scope if q.startswith("repo:")]
        orgs_scope = [q.split(":", 1)[1] for q in scope if q.startswith("org:")]
        query = build_issue_query(
            base=[
                "is:issue",
                "is:open",
                "no:assignee",
                "-linked:pr",
                "archived:false",
                f"created:>={since.date().isoformat()}",
            ],
            labels=["good first issue"],
            orgs=orgs_scope,
            extra=[or_group("repo", repos_scope)] if repos_scope else None,
        )
        try:
            items = self.github.search_issues(query, per_page=20, sort="created")
        except HttpError:
            return []
        out = []
        for item in items:
            if "pull_request" in item:
                continue
            parts = str(item.get("repository_url") or "").rstrip("/").split("/")
            repo = "/".join(parts[-2:]) if len(parts) >= 2 else ""
            if "/" not in repo or not item.get("number"):
                continue
            out.append(
                {
                    "repo": repo,
                    "number": int(item["number"]),
                    "title": clean_untrusted(item.get("title"), limit=160),
                    "url": str(item.get("html_url") or ""),
                    "created_at": item.get("created_at"),
                    "labels": [
                        lab.get("name") for lab in item.get("labels") or [] if isinstance(lab, dict)
                    ],
                }
            )
        return out[:10]


def _license_label(license_obj: Any) -> str | None:
    if not isinstance(license_obj, dict):
        return None
    spdx = str(license_obj.get("spdx_id") or "")
    if spdx and spdx != "NOASSERTION":
        return spdx
    return str(license_obj.get("name") or "") or None


def _quote_label(label: str) -> str:
    return f'"{label}"' if " " in label else label


def _looks_like_ideas_page(page: dict[str, str]) -> bool:
    text = f"{page.get('title', '')} {page.get('url', '')}".lower()
    return any(word in text for word in ("idea", "gsoc", "summer", "project", "mentor"))


_GITHUB_PROJECT_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)(?:/([A-Za-z0-9_.-]+))?", re.I
)
_NOT_OWNERS = {"orgs", "topics", "search", "features", "apps", "settings", "marketplace"}
_NOT_REPOS = {"wiki", "issues", "blob", "tree", "pulls", "discussions", "projects"}
_DISCUSSIONS_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/discussions\b")
_CHANGE_LINK_RE = re.compile(r"/(?:pull|pulls|commit|commits|compare)\b")


def _github_links(text: str) -> list[dict[str, str]]:
    """Every github.com link in a page's text, shaped like ideas sub-pages."""
    return [{"title": "", "url": m.group(0)} for m in _GITHUB_PROJECT_RE.finditer(text)]


def _linked_github_projects(
    pages: list[dict[str, str]], *, exclude: list[str], limit: int = 8, any_link: bool = False
) -> tuple[list[tuple[str, str]], set[str]]:
    """GitHub owners (with the page title) and repositories an umbrella index links to.

    ``any_link`` keeps links whose title does not mention ideas, for organizations
    that list no GitHub owner at all, where every GitHub link is a lead.
    """
    seen = {o.lower() for o in exclude}
    owners: list[tuple[str, str]] = []
    repos: set[str] = set()
    for page in pages:
        if not any_link and not _looks_like_ideas_page(page):
            continue
        match = _GITHUB_PROJECT_RE.match(str(page.get("url") or ""))
        if not match or match.group(1).lower() in _NOT_OWNERS:
            continue
        owner, repo = match.group(1), match.group(2)
        if repo and repo.lower() not in _NOT_REPOS:
            repos.add(f"{owner}/{repo}".lower())
        if owner.lower() not in seen and len(owners) < limit:
            seen.add(owner.lower())
            owners.append((owner, str(page.get("title") or owner)))
    return owners, repos


def _ideas_note(doc: IdeasDocument, followed: list[dict[str, str]]) -> str:
    if doc.layout == "issues":
        return "This org lists ideas as GitHub issues; each idea links to its issue."
    if doc.layout == "index" and doc.ideas:
        return (
            f"Umbrella page: ideas were read from {len(followed)} linked sub-project page(s). "
            "Other sub-projects may list ideas elsewhere."
        )
    if doc.layout == "index":
        return "This is an index page that links to sub-project pages; open them for ideas."
    if doc.layout == "unstructured":
        return (
            "The page has no recognisable idea blocks (tables or prose). Headings are listed "
            "so you know what it covers; read it directly."
        )
    low = sum(1 for i in doc.ideas if i.confidence == "low")
    return (
        f"Parsed {len(doc.ideas)} idea block(s); {low} had no labelled fields and may be "
        "section headings rather than ideas. Empty fields were not on the page."
        if low
        else f"Parsed {len(doc.ideas)} idea block(s). Empty fields were not on the page."
    )


# Availability values a starter list may show: free, or not checked (timeline unreadable).
_OPEN_TO_NEWCOMERS = frozenset({Availability.AVAILABLE.value, Availability.UNKNOWN.value})


def _after(stamp: object, when: datetime) -> bool:
    """True when an ISO timestamp from GitHub is later than `when`."""
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment > when


def _open(issue: dict[str, Any]) -> bool:
    return issue.get("availability") in _OPEN_TO_NEWCOMERS


def _issue_dict(issue: Any) -> dict[str, Any]:
    if isinstance(issue, dict):
        return issue
    data: dict[str, Any] = issue.model_dump(mode="json", exclude={"signals"})
    return data | {"signals": issue.signals}


def _repo_recommendation(grade: str, warnings: list[str]) -> str:
    # Read from the grade, so the advice can never disagree with it: a B never reads
    # as "go ahead", and a C (where merging under 20% of outside PRs caps a
    # repository) never reads as promising.
    if grade == "A":
        if warnings:
            return "Strong candidate. Read the warnings below, then set it up and pick an issue."
        return "Strong candidate. Go ahead with setup and pick an issue."
    if grade == "B":
        return "Promising, with caveats. Read the warnings and check that maintainers reply."
    if grade in {"C", "D"}:
        return "Risky. Only continue if you have a mentor contact or a strong reason."
    return "Poor fit for a first GSoC contribution. Choose a healthier repository."
