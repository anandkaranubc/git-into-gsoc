"""High-level facade used by CLI and MCP tools."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.coach import plan_actions, upcoming_deadlines
from git_into_gsoc.config import DEFAULT_TARGET_YEAR, LATEST_ARCHIVED_YEAR, get_settings
from git_into_gsoc.errors import GigError, InputError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.orientation import (
    active_committers,
    ci_test_commands,
    code_map,
    codeowners_for,
    conventions,
    days_since,
    entry_points,
    find_paths,
    policy_quotes,
    rank_workflows,
    reading_plan,
    since_iso,
)
from git_into_gsoc.github.pointers import (
    closing_pull_request,
    days_between,
    extract_mentions,
    fix_norm,
    resolve_paths,
)
from git_into_gsoc.github.repos import (
    OUTSIDER_ROLES,
    channels_in,
    is_bot,
    mentioned_repos,
    pick_beginner_label,
    repo_lead_score,
)
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
from git_into_gsoc.models import IdeasDocument, ProgressState, ProjectIdea, RepoLead
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.validation import parse_issue_ref, parse_repo, validate_login


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
        owners = list((gsoc_org.github_orgs if gsoc_org else [])[:3])
        if not owners:
            owners = [validate_login(org, kind="GitHub org/user or GSoC org name")]
        ideas_url = gsoc_org.ideas_url if gsoc_org else None
        ideas = fetch_ideas_text(self.http, ideas_url, self.settings.archive_ttl_seconds)

        cutoff = datetime.now(UTC) - timedelta(days=365)
        leads: list[RepoLead] = []
        for owner in owners:
            repos = [
                r
                for r in self.github.list_owner_repos(owner)
                if not r.get("archived")
                and not r.get("fork")
                and r.get("has_issues", True)
                and (_parse_iso(r.get("pushed_at")) or cutoff) >= cutoff
            ]
            counts = self.github.beginner_issue_counts(owner) if repos else {}
            mentioned = mentioned_repos(ideas, [owner], repos) if ideas else set()
            for repo in repos:
                full = str(repo.get("full_name"))
                beginner = counts.get(full.lower(), 0)
                in_ideas = full.lower() in mentioned
                score, reasons = repo_lead_score(
                    repo, beginner_issues=beginner, ideas_mention=in_ideas, language=language
                )
                leads.append(
                    RepoLead(
                        full_name=full,
                        url=str(repo.get("html_url")),
                        description=repo.get("description"),
                        language=repo.get("language"),
                        stars=int(repo.get("stargazers_count") or 0),
                        pushed_at=_parse_iso(repo.get("pushed_at")),
                        open_beginner_issues=beginner,
                        ideas_mention=in_ideas,
                        score=score,
                        reasons=reasons,
                    )
                )
        leads.sort(key=lambda lead: (-lead.score, -lead.stars))
        return {
            "org": gsoc_org.name if gsoc_org else owners[0],
            "github_owners": owners,
            "ideas_url": ideas_url,
            "ideas_page_read": bool(ideas),
            "count": min(limit, len(leads)),
            "repos": [lead.model_dump(mode="json") for lead in leads[:limit]],
            "next_step": "Run `repo owner/name` on your top pick, then `issues --repo owner/name`.",
        }

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
        self.progress.set_profile(
            github=username, **{k: profile.get(k) for k in ("top_language", "languages", "bio")}
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
    ) -> dict[str, Any]:
        """Save the self-profile that personalises recommendations and `next`."""
        if github:
            self.profile_from_github(github)
        self.progress.set_profile(
            technologies=technologies or None,
            interests=interests or None,
            hours_per_week=hours_per_week,
            timezone=timezone,
        )
        return self.progress.profile()

    def recommend_path(
        self,
        *,
        username: str | None = None,
        technologies: list[str] | None = None,
        interests: list[str] | None = None,
    ) -> dict[str, Any]:
        saved = self.progress.profile()
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
        if not (techs or wants):
            source = "none"

        orgs = self.match_orgs(technologies=techs or None, topics=wants or None, limit=8)[
            "organizations"
        ]
        issue_language = techs[0] if techs else None
        issues: list[dict[str, Any]] = []
        issue_error: dict[str, str] | None = None
        if issue_language:
            try:
                issues = self.find_issues(language=issue_language, max_results=5)["issues"]
            except GigError as exc:
                issue_error = exc.to_dict()

        note = (
            f"Org rankings use archive data through {LATEST_ARCHIVED_YEAR}. "
            "GSoC 2027 org lists are not final until officially announced."
        )
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
            "recommended_orgs": orgs,
            "starter_issues": issues,
            "starter_issue_error": issue_error,
            "next_steps": [
                "Shortlist three organizations and join their community channels",
                "Check one or two of their main repositories for health and a contributing guide",
                "Make one meaningful contribution before writing a proposal",
                "Read Google's AI guidance and each organization's AI policy",
            ],
            "evidence_note": (
                "Organization rankings use the latest official list plus archive history. "
                "Next year's organizations are not final until Google announces them."
            ),
            "evidence_note": note,
        }

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

        report = check_proposal(
            text,
            github_user=github,
            lookup=lookup if verify else None,
            ideas_text=ideas_text,
        )
        report["links_verified"] = verify
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
        if recheck:
            self.progress.mark_checked(statuses, now)

        actions = plan_actions(
            state, program, tracked_issues=tracked, new_issues=new_issues, now=now
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
            "progress": self.progress.summary(),
            "tracked_issues": tracked,
            "changes": changes,
            "new_issues": new_issues,
            "actions": actions,
            "note": (
                "Actions are suggestions from your saved progress and public data. "
                "Dates for unpublished years are estimates; verify on the official site."
            ),
        }

    # ---------------------------------------------------------- orientation

    def orient_repo(self, full_name: str) -> dict[str, Any]:
        """A one-screen orientation sheet: facts and paths only, about 16 API calls."""
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
            tree, langs = tree_f.result(), langs_f.result()
            profile, commits, pulls = profile_f.result(), commits_f.result(), pulls_f.result()
        entries = list(tree.get("tree") or [])
        found = find_paths(entries)
        if not found.get("contributing"):
            html = ((profile.get("files") or {}).get("contributing") or {}).get("html_url")
            if html and "/blob/" in html:
                found["contributing"] = html.split("/blob/", 1)[1].split("/", 1)[1]

        workflow_paths = rank_workflows(found.get("workflows") or [])
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
                for path in workflow_paths
            }
            for key, future in futures.items():
                texts[key] = future.result() or ""
            for path, future in wf_futures.items():
                workflow_texts[path] = future.result() or ""

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
        tests = ci_test_commands(workflow_texts)
        fallback_hints = [
            f"{found['makefile']} lists local targets" if found.get("makefile") else "",
            "Dev container present: open in Codespaces or VS Code for a ready environment"
            if found.get("devcontainer")
            else "",
        ]
        return {
            "repo": f"{owner}/{repo}",
            "url": raw.get("html_url") or f"https://github.com/{owner}/{repo}",
            "description": raw.get("description"),
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

    def _example_outsider_pr(
        self, owner: str, repo: str, merged: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """A recently merged, small PR by someone without write access (at most 2 lookups)."""
        candidates = [p for p in merged if p.get("author_association") in OUTSIDER_ROLES][:2]
        for pull in candidates:
            files = self.github.list_pull_files(owner, repo, int(pull["number"]))
            if files and len(files) <= 6:
                return {
                    "number": int(pull["number"]),
                    "url": pull.get("html_url"),
                    "title": str(pull.get("title") or "")[:120],
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
                paths = [p for p in paths if not p.startswith(("node_modules/", "vendor/"))]
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

        fixes, label, similar_note = self._similar_fixes(owner, repo, issue, limit=similar)
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
                "title": str(issue.get("title") or ""),
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
    ) -> tuple[list[dict[str, Any]], str | None, str]:
        """Closed issues with the same beginner label, the PRs that closed them, and a note."""
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
            return [], None, "No beginner label found to look up similar closed issues."
        query = f"repo:{full} is:issue is:closed label:{_quote_label(label)}"
        try:
            items = self.github.search_issues(query, per_page=limit + 3)
        except HttpError as exc:
            return [], label, f"Could not search similar issues: {exc}"
        items = [
            i for i in items if "pull_request" not in i and i.get("number") != issue.get("number")
        ][:limit]
        if not items:
            return [], label, f"No closed issues carry the '{label}' label yet."
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
                        "title": str(item.get("title") or "")[:120],
                        "url": item.get("html_url"),
                    },
                    "pull_request": closer,
                    "files": [str(f.get("filename")) for f in changed[:12]],
                    "additions": sum(int(f.get("additions") or 0) for f in changed),
                    "deletions": sum(int(f.get("deletions") or 0) for f in changed),
                    "days_to_merge": days_between(closer.get("opened_at"), closer.get("merged_at")),
                }
            )
        note = (
            f"{len(fixes)} of {len(items)} similar closed issues had a traceable fix PR."
            if fixes
            else f"{len(items)} similar closed issues found, but none closed by a traceable PR."
        )
        return fixes, label, note

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
            return {
                "found": False,
                "error": f"No organization matched '{name}'",
                "hint": "Try a partial name, or search with `orgs --query`.",
            }
        base = {"found": True, "org": org.name, "ideas_url": org.ideas_url}
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
        wanted = list(skills or []) or list(self.progress.profile().get("technologies") or [])
        ranked = rank_ideas(doc.ideas, skills=wanted or None, size=size, difficulty=difficulty)
        return {
            **base,
            "fetched_url": doc.fetched_url,
            "layout": doc.layout,
            "count": len(ranked),
            "ideas": [i.model_dump(mode="json") for i in ranked[: max(1, limit)]],
            "skills_matched_on": wanted,
            "ai_policy": doc.ai_policy,
            "sub_pages": doc.sub_pages[:40] if doc.layout == "index" else [],
            "followed": followed,
            "headings": doc.headings[:30] if not doc.ideas else [],
            "note": _ideas_note(doc, followed),
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
                    title=str(item.get("title") or f"#{item.get('number')}"),
                    description=" ".join(body.split())[:500],
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
        return assessment.availability.value, assessment.reason

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
            except HttpError:
                org = None
            if org and org.github_orgs:
                scope.append(f"org:{org.github_orgs[0]}")
        scope = list(dict.fromkeys(scope))
        if not scope:
            return []
        base = (
            'is:issue is:open no:assignee -linked:pr archived:false label:"good first issue" '
            f"created:>={since.date().isoformat()}"
        )
        query = base
        for qualifier in scope:
            if len(query) + len(qualifier) + 1 > 250:
                break
            query += f" {qualifier}"
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
                    "title": str(item.get("title") or ""),
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


def _repo_recommendation(score: float, warnings: list[str]) -> str:
    if score >= 80:
        return "Strong candidate. Go ahead with setup and pick an issue."
    if score >= 65:
        return "Promising, with caveats. Read the warnings and check that maintainers reply."
    if score >= 45:
        return "Risky. Only continue if you have a mentor contact or a strong reason."
    return "Poor fit for a first GSoC contribution. Choose a healthier repository."
