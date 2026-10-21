"""Typer CLI for git-into-gsoc."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typer.core import TyperGroup

from git_into_gsoc import __version__
from git_into_gsoc.errors import GigError, InputError
from git_into_gsoc.guidance import ANTI_SPAM_RULES, journey_overview
from git_into_gsoc.service import GSoCToolkit
from git_into_gsoc.validation import split_csv

console = Console()
err_console = Console(stderr=True)


class _FriendlyErrors(TyperGroup):
    """Render expected failures as one-line errors with a hint, not tracebacks."""

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except GigError as exc:
            err_console.print(f"[bold red]error:[/bold red] {exc}")
            if exc.hint:
                err_console.print(f"[dim]hint:[/dim] {exc.hint}")
            raise typer.Exit(code=1) from exc


OUTPUT_HELP = "rich for readable tables and panels, json for scripts and assistants"

app = typer.Typer(
    name="git-into-gsoc",
    help=(
        "Prepare for Google Summer of Code with real data: find organizations, "
        "check repositories, find beginner issues, and plan your proposal."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    cls=_FriendlyErrors,
    pretty_exceptions_show_locals=False,
)


class Output(StrEnum):
    rich = "rich"
    json = "json"


OUTPUT_OPTION = typer.Option(Output.rich, "--output", help=OUTPUT_HELP)


def _toolkit() -> GSoCToolkit:
    return GSoCToolkit()


def _emit(data: object, output: Output) -> None:
    if output == Output.json:
        console.print_json(json.dumps(data, default=str))
    else:
        console.print(data)


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Prepare for Google Summer of Code with real data."""
    del version


class ProjectSize(StrEnum):
    small = "small"
    medium = "medium"
    large = "large"


def _relative(days: int) -> str:
    if days == 0:
        return "today"
    if days > 0:
        return f"in {days}d"
    return f"{-days}d ago"


@app.command("program")
def program_cmd(
    year: int = typer.Option(2027, help="Program year, for example 2027"),
    size: ProjectSize = typer.Option(
        ProjectSize.medium, "--size", help="Project size; evaluation deadlines differ by size"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Show the program timeline, current phase, and what to do now."""
    data = _toolkit().program_info(year, project_size=size.value)
    if output == Output.json:
        _emit(data, output)
        return
    phase = data["phase"]
    badge = "[green]official[/green]" if data["dates_are_official"] else "[yellow]estimate[/yellow]"
    console.print(
        Panel.fit(
            f"[bold]GSoC {year}[/bold]  dates: {badge}\n"
            f"[bold cyan]Now:[/bold cyan] {phase['title']}\n{phase['advice']}\n\n"
            f"[dim]{data['source']}[/dim]\n"
            f"Verify: {data['official_timeline']}",
            title="git-into-gsoc",
        )
    )
    table = Table(title=f"Timeline ({size.value} projects)")
    table.add_column("Date (UTC)")
    table.add_column("Milestone")
    table.add_column("When", justify="right")
    for event in data["timeline"]:
        date = event["at"][:10]
        if event.get("window_days"):
            date = f"~{date} ±{event['window_days']}d"
        style = "dim" if event["status"] == "past" else ""
        table.add_row(date, event["label"], _relative(event["days_until"]), style=style)
    console.print(table)
    console.print("\n[bold]Anti-spam rules[/bold]")
    for rule in ANTI_SPAM_RULES:
        console.print(f"• {rule}")


_FIT_PREFIXES = (
    "Uses",
    "Topic",
    "Related",
    "Category",
    "Mentions",
    "Name",
    "Matches",
    "Slots growing",
)


def _trend(projects_by_year: dict[str, int]) -> str:
    recent = sorted(projects_by_year.items(), key=lambda kv: int(kv[0]))[-4:]
    return " ".join(f"'{str(year)[2:]}:{count}" for year, count in recent)


@app.command("orgs")
def orgs_cmd(
    query: str | None = typer.Option(
        None, "--query", "-q", help="Words to look for in names and descriptions"
    ),
    tech: str | None = typer.Option(
        None, "--tech", "-t", help="Technologies you know, comma-separated (python,javascript)"
    ),
    topics: str | None = typer.Option(
        None, "--topics", help="Topics you care about, comma-separated (science,education)"
    ),
    category: str | None = typer.Option(
        None, "--category", "-c", help="Organization category, for example 'Science and medicine'"
    ),
    year: int | None = typer.Option(
        None, help="Program year (default: target year; falls back to the latest announced)"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="How many organizations to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Rank mentoring organizations for your skills and interests."""
    data = _toolkit().match_orgs(
        query=query,
        technologies=split_csv(tech) or None,
        topics=split_csv(topics) or None,
        category=category,
        year=year,
        limit=limit,
    )
    if output == Output.json:
        _emit(data, output)
        return
    catalog = data["catalog"]
    table = Table(title="GSoC organizations", caption=catalog["note"], show_lines=False)
    table.add_column("Score", justify="right")
    table.add_column("Organization", overflow="fold", max_width=28)
    table.add_column("Fit", overflow="fold")
    table.add_column("Years", justify="right")
    table.add_column("Slots", no_wrap=True)
    for org in data["organizations"]:
        fit = [r for r in org.get("match_reasons") or [] if r.startswith(_FIT_PREFIXES)]
        table.add_row(
            f"{org['match_score']:.0f}",
            org["name"],
            "; ".join(fit) or "(no specific match)",
            str(len(org.get("years_active") or [])),
            _trend(org.get("projects_by_year") or {}),
        )
    console.print(table)
    if not data["organizations"]:
        console.print("[yellow]No organizations matched.[/yellow] Try broader --tech/--topics.")
    else:
        console.print(
            '[dim]Next: git-into-gsoc org "<name>" for ideas page, channels, and repos.[/dim]'
        )


@app.command("org")
def org_cmd(
    name: str = typer.Argument(
        ..., help="Organization name, part of it, or its slug, for example SymPy"
    ),
    year: int | None = typer.Option(None, help="Program year"),
    shortlist: bool = typer.Option(
        False, "--shortlist", help="Also add this organization to your shortlist"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Show ideas page, channels, GitHub orgs, slot history, and past projects."""
    data = _toolkit().org_details(name, year=year)
    if shortlist and data.get("found"):
        _toolkit().progress.shortlist_org(data["organization"]["name"])
        data["shortlisted"] = True
    if output == Output.json or not data.get("found"):
        _emit(data, Output.json)
        return
    org = data["organization"]
    lines = [f"[bold]{org['name']}[/bold]", org["description"]]
    for label, key in (
        ("Ideas", "ideas_url"),
        ("Contributor guide", "guide_url"),
        ("Source", "source_code"),
        ("Website", "url"),
    ):
        if org.get(key):
            lines.append(f"{label}: {org[key]}")
    if org.get("github_orgs"):
        lines.append("GitHub: " + ", ".join(org["github_orgs"]))
    for channel in org.get("channels") or []:
        lines.append(f"{channel['kind']}: {channel['value']}")
    lines.append(
        f"Tech: {', '.join(org.get('technologies') or [])}  |  "
        f"Topics: {', '.join(org.get('topics') or [])}"
    )
    lines.append(f"Projects per year: {_trend(org.get('projects_by_year') or {})}")
    status = "accepted" if org.get("official") else "archive record"
    console.print(
        Panel(Text.from_markup("\n".join(lines)), title=f"{data['catalog']['year']} · {status}")
    )
    if org.get("recent_projects"):
        table = Table(title="Recent accepted projects (for scope reference, never copy)")
        table.add_column("Year")
        table.add_column("Title", overflow="fold")
        for project in org["recent_projects"]:
            table.add_row(str(project["year"]), project["title"])
        console.print(table)


@app.command("projects")
def projects_cmd(
    query: str | None = typer.Argument(None, help="Keywords, e.g. 'graph neural networks'"),
    org: str | None = typer.Option(None, "--org", help="Limit to one organization"),
    since: int | None = typer.Option(None, "--since", help="Earliest program year"),
    limit: int = typer.Option(15, "--limit", "-n", help="How many projects to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Search past accepted GSoC projects to calibrate scope and find orgs."""
    data = _toolkit().past_projects(query, org=org, since=since, limit=limit)
    if output == Output.json:
        _emit(data, output)
        return
    table = Table(title="Past accepted projects", caption=data["note"])
    table.add_column("Year")
    table.add_column("Organization", overflow="fold", max_width=26)
    table.add_column("Project", overflow="fold")
    for project in data["projects"]:
        table.add_row(str(project["year"]), project["org"], project["title"])
    console.print(table)


@app.command("repos")
def repos_cmd(
    org: str = typer.Argument(..., help="GSoC org name (e.g. 'GNU Radio') or GitHub login"),
    language: str | None = typer.Option(None, "--language", "-l", help="Prefer this language"),
    limit: int = typer.Option(10, "--limit", "-n"),
    output: Output = Output.rich,
) -> None:
    """Rank an org's repositories: ideas-page mentions, open beginner issues, activity."""
    data = _toolkit().discover_repos(org, language=language, limit=limit)
    if output == Output.json:
        _emit(data, output)
        return
    caption = (
        "Ideas page read: repos it names are boosted."
        if data["ideas_page_read"]
        else "Ideas page not readable; ranking uses activity and beginner issues."
    )
    table = Table(
        title=f"{data['org']} repositories ({', '.join(data['github_owners'])})", caption=caption
    )
    table.add_column("Score", justify="right")
    table.add_column("Repository", overflow="fold")
    table.add_column("Why", overflow="fold")
    for repo in data["repos"]:
        table.add_row(
            f"{repo['score']:.0f}",
            repo["full_name"],
            "; ".join(repo["reasons"]) or "(no specific match)",
        )
    console.print(table)
    console.print(f"[dim]{data['next_step']}[/dim]")


@app.command("repo")
def repo_cmd(
    full_name: str = typer.Argument(
        ..., help="Repository as owner/name or a GitHub URL, for example sympy/sympy"
    ),
    track: bool = typer.Option(False, "--track", help="Also save this repo to your progress"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Check whether a newcomer's PR can land here: health grade, merge behaviour, setup path."""
    data = _toolkit().evaluate_repo(full_name)
    if track:
        _toolkit().progress.track_repo(data["health"]["full_name"])
        data["tracked"] = True
    if output == Output.json:
        _emit(data, output)
        return
    health = data["health"]
    guide = data["contribution_guide"]
    console.print(
        Panel.fit(
            f"[bold]{health['full_name']}[/bold]  grade [bold]{health['grade']}[/bold]  "
            f"({health['health_score']:.0f}/100)\n{data['recommendation']}",
            title="Repo health",
        )
    )
    for signal in health.get("signals") or []:
        console.print(f"  [green]✓[/green] {signal}")
    for warning in health.get("warnings") or []:
        console.print(f"  [yellow]![/yellow] {warning}")
    console.print("\n[bold]Getting set up[/bold]")
    for hint in guide.get("setup_hints") or []:
        console.print(f"  • {hint}")
    if guide.get("contributing_url"):
        console.print(f"  • Read first: {guide['contributing_url']}")
    if guide.get("communication_channels"):
        console.print(f"  • Channels mentioned: {', '.join(guide['communication_channels'])}")


class Scope(StrEnum):
    gsoc = "gsoc"
    all = "all"


_STATUS_STYLE = {
    "available": "green",
    "claimed": "yellow",
    "contested": "yellow",
    "likely_taken": "red",
    "assigned": "red",
    "stale": "dim",
    "closed": "dim",
    "unknown": "dim",
}


@app.command("issues")
def issues_cmd(
    language: str | None = typer.Option(
        None, "--language", "-l", help="Programming language, for example python"
    ),
    org: str | None = typer.Option(None, "--org", help="GitHub organization or user to search"),
    repo: str | None = typer.Option(None, "--repo", help="One repository as owner/name"),
    label: str | None = typer.Option(
        None, "--label", help="Label to require (default: good first issue, then help wanted)"
    ),
    scope: Scope = typer.Option(
        Scope.gsoc,
        "--scope",
        help="gsoc: only repositories of GSoC organizations; all: any repository",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="How many issues to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Find beginner issues that still look free: no PR, assignee, or recent claim."""
    data = _toolkit().find_issues(
        language=language, org=org, repo=repo, label=label, scope=scope.value, max_results=limit
    )
    if output == Output.json:
        _emit(data, output)
        return
    table = Table(title="Beginner-friendly issues", caption=data["note"])
    table.add_column("Score", justify="right")
    table.add_column("Status")
    table.add_column("Issue", overflow="fold")
    table.add_column("Title", overflow="fold")
    for issue in data["issues"]:
        status = issue["availability"]
        ref = f"{issue['repo']}#{issue['number']}"
        if issue.get("gsoc_org"):
            ref += f"\n[dim]{issue['gsoc_org']}[/dim]"
        table.add_row(
            f"{issue['beginner_score']:.0f}",
            f"[{_STATUS_STYLE.get(status, '')}]{status}[/]",
            ref,
            issue["title"],
        )
    console.print(table)
    if data["issues"]:
        console.print("[dim]Next: git-into-gsoc issue owner/repo#N before you comment.[/dim]")


@app.command("issue")
def issue_cmd(
    ref: str = typer.Argument(..., help="owner/repo#123, an issue URL, or owner/repo"),
    number: int | None = typer.Argument(None, help="Issue number if REF is owner/repo"),
    track: bool = typer.Option(False, "--track", help="Also save this issue to your progress"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Check whether an issue is free to pick up: PRs, claims, assignees, activity."""
    data = _toolkit().issue_status(ref, number)
    if track:
        _toolkit().progress.track_issue(data["url"])
        data["tracked"] = True
    if output == Output.json:
        _emit(data, output)
        return
    assessment = data["assessment"]
    style = _STATUS_STYLE.get(data["availability"], "")
    lines = [
        f"[bold]{data['title']}[/bold]",
        data["url"],
        f"Status: [{style}]{data['availability']}[/] ({data['reason']})",
    ]
    if assessment["maintainer_engaged"]:
        lines.append("Maintainers have commented in this thread.")
    for pr in assessment["linked_prs"]:
        lines.append(f"PR #{pr['number']} ({pr['state']}) by @{pr['author']}")
    for claim in assessment["claims"][:5]:
        granted = ", approved by a maintainer" if claim["granted"] else ""
        lines.append(f"Claim: @{claim['login']} {claim['days_ago']}d ago{granted}")
    for caveat in assessment["caveats"]:
        lines.append(f"[yellow]![/yellow] {caveat}")
    console.print(
        Panel(Text.from_markup("\n".join(lines)), title=f"{data['repo']}#{data['number']}")
    )
    console.print("[bold]Before you comment[/bold]")
    for step in data["before_you_comment"]:
        console.print(f"  ☐ {step}")


@app.command("recommend")
def recommend_cmd(
    github: str | None = typer.Option(
        None, "--github", "-g", help="Your GitHub username, used to infer your main language"
    ),
    tech: str | None = typer.Option(
        None, "--tech", "-t", help="Technologies you know, comma-separated"
    ),
    interests: str | None = typer.Option(
        None, "--interests", "-i", help="Topics you care about, comma-separated"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Suggest organizations and starter issues based on your skills."""
    techs = [x.strip() for x in (tech or "").split(",") if x.strip()]
    ints = [x.strip() for x in (interests or "").split(",") if x.strip()]
    data = _toolkit().recommend_path(
        username=github, technologies=techs or None, interests=ints or None
    )
    if output == Output.json:
        _emit(data, output)
        return
    console.print(Panel.fit(data["evidence_note"], title="Recommendations"))
    if data.get("profile"):
        console.print(
            f"Profile: [bold]{data['profile'].get('login')}[/bold] "
            f"top={data['profile'].get('top_language')}"
        )
    console.print("\n[bold]Orgs[/bold]")
    for org in data["recommended_orgs"][:5]:
        console.print(f"  • {org['name']} (score {org['match_score']:.0f})")
    console.print("\n[bold]Next steps[/bold]")
    for step in data["next_steps"]:
        console.print(f"  → {step}")


_FINDING_MARK = {"pass": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}


@app.command("proposal")
def proposal_cmd(
    file: Path | None = typer.Argument(
        None, help="Draft proposal to check (Markdown or text). Omit for the checklist."
    ),
    github: str | None = typer.Option(
        None, "--github", "-g", help="Your GitHub login, to confirm linked PRs are yours"
    ),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Look up linked pull requests on GitHub"
    ),
    ideas_file: Path | None = typer.Option(
        None, "--ideas-file", help="The org's ideas page as text, to detect copied passages"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Show the proposal checklist, or check a draft for what organizations reject on."""
    if file is None:
        data = _toolkit().proposal_help()
        if output == Output.json:
            _emit(data, output)
            return
        console.print("[bold]Checklist[/bold]")
        for item in data["checklist"]:
            console.print(f"☐ {item['title']}: {item['description']}")
        console.print("\n[bold]Suggested structure[/bold]")
        for i, section in enumerate(data["structure"], 1):
            console.print(f"  {i}. {section}")
        console.print("\n[dim]Check a draft: git-into-gsoc proposal draft.md --github you[/dim]")
        return
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"Cannot read {file}: {exc.strerror or exc}") from exc
    ideas_text = ideas_file.read_text(encoding="utf-8", errors="replace") if ideas_file else None
    report = _toolkit().check_proposal(text, github=github, verify=verify, ideas_text=ideas_text)
    if output == Output.json:
        _emit(report, output)
        return
    table = Table(title=f"Proposal check: {file.name} ({report['word_count']} words)")
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", overflow="fold")
    for finding in report["findings"]:
        table.add_row(_FINDING_MARK[finding["status"]], finding["title"], finding["detail"])
    console.print(table)
    for link in report["links"]:
        if link["kind"] != "pull":
            continue
        state = link["state"] or ("not verified" if not report["links_verified"] else "unknown")
        who = f" by @{link['author']}" if link["author"] else ""
        note = f"  [yellow]{link['note']}[/yellow]" if link["note"] else ""
        console.print(f"  PR {link['repo']}#{link['number']}: {state}{who}{note}")
    console.print(f"\n[bold]{report['verdict']}[/bold]")
    for check in report["manual_checks"]:
        console.print(f"  ☐ {check}")


@app.command("progress")
def progress_cmd(
    action: str = typer.Argument(
        "summary",
        help="summary, complete_phase, shortlist_org, track_repo, track_issue, or note",
    ),
    phase: str | None = typer.Option(
        None, help="Phase name for complete_phase; run `journey` to see the names"
    ),
    value: str | None = typer.Option(
        None, "--value", "-v", help="Organization name, owner/name, issue link, or note text"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Save and review your progress, shortlist, and notes on this computer."""
    store = _toolkit().progress
    if action == "summary":
        data = store.summary()
    elif action == "complete_phase":
        if not phase:
            raise typer.BadParameter("--phase is required")
        data = store.complete_phase(phase).model_dump(mode="json")
    elif action == "shortlist_org":
        data = store.shortlist_org(value or "").model_dump(mode="json")
    elif action == "track_repo":
        data = store.track_repo(value or "").model_dump(mode="json")
    elif action == "track_issue":
        data = store.track_issue(value or "").model_dump(mode="json")
    elif action == "note":
        data = store.add_note(value or "").model_dump(mode="json")
    else:
        raise typer.BadParameter(f"Unknown action: {action}")
    _emit(data if output == Output.json else json.dumps(data, indent=2, default=str), output)


@app.command("journey")
def journey_cmd(output: Output = OUTPUT_OPTION) -> None:
    """Print the full contributor journey overview."""
    data = journey_overview()
    if output == Output.json:
        _emit(data, output)
        return
    phases = data["phases"]
    assert isinstance(phases, dict)
    for phase, guide in phases.items():
        assert isinstance(guide, dict)
        console.print(f"\n[bold cyan]{phase}[/bold cyan]: {guide['goal']}")
        for action in guide["actions"]:
            console.print(f"  • {action}")


@app.command("mcp")
def mcp_cmd() -> None:
    """Run the MCP server so AI assistants can use these tools. Press Ctrl+C to stop."""
    from git_into_gsoc.mcp_server import main as mcp_main

    mcp_main()


def _short_path(path: Path, home: Path, project: Path | None = None) -> str:
    for root, prefix in ((project, "./"), (home, "~/")):
        if root is None:
            continue
        try:
            return prefix + path.relative_to(root).as_posix()
        except ValueError:
            continue
    return str(path)


class SetupScope(StrEnum):
    user = "user"
    project = "project"


@app.command("setup")
def setup_cmd(
    assistant: list[str] | None = typer.Option(
        None,
        "--assistant",
        "-a",
        help=(
            "Assistant to configure (repeatable): claude-code, cursor, codex, gemini, "
            "windsurf, vscode, or all. Default: every assistant detected on this machine."
        ),
    ),
    scope: SetupScope = typer.Option(
        SetupScope.user,
        "--scope",
        help="user: your home folder; project: the current repository (or --project-dir)",
    ),
    project_dir: Path | None = typer.Option(
        None, "--project-dir", help="Project root for --scope project (default: current dir)"
    ),
    skill: bool = typer.Option(True, "--skill/--no-skill", help="Copy the Agent Skill"),
    mcp: bool = typer.Option(True, "--mcp/--no-mcp", help="Register the MCP server"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without writing"),
    output: Output = Output.rich,
) -> None:
    """Install the Agent Skill and register the MCP server with your AI assistants."""
    from git_into_gsoc.install import plan_setup, run_setup
    from git_into_gsoc.install.clients import env_home

    project = (project_dir or Path.cwd()).resolve() if scope == SetupScope.project else None
    plan = plan_setup(
        scope=scope.value,
        assistants=assistant or None,
        home=env_home(),
        project=project,
        install_skill=skill,
        install_mcp=mcp,
    )
    run_setup(plan, dry_run=dry_run)
    if output == Output.json:
        _emit(
            {
                "scope": plan.scope,
                "root": str(plan.root),
                "command": plan.command,
                "assistants": [a.key for a in plan.assistants],
                "dry_run": dry_run,
                "changes": [
                    {
                        "assistant": c.assistant,
                        "kind": c.kind,
                        "path": str(c.path),
                        "action": c.action,
                        "note": c.note,
                    }
                    for c in plan.changes
                ],
                "manual_steps": plan.manual,
            },
            output,
        )
        return
    if not plan.assistants:
        console.print(
            "[yellow]No AI assistant detected.[/yellow] Use --assistant to pick one, "
            "for example: git-into-gsoc setup --assistant claude-code"
        )
    title = ("Plan (dry run)" if dry_run else "Setup complete") + f" · {plan.scope} scope"
    where = f"./ = {plan.project}   " if plan.project else ""
    table = Table(title=title, caption=f"{where}MCP command: {' '.join(plan.command)}")
    table.add_column("Assistant")
    table.add_column("What")
    table.add_column("Result")
    table.add_column("Path", overflow="fold")
    styles = {"created": "green", "updated": "green", "unchanged": "dim", "skipped": "yellow"}
    for change in plan.changes:
        result = change.action + (f" ({change.note})" if change.note else "")
        table.add_row(
            change.assistant,
            change.kind,
            f"[{styles.get(change.action, '')}]{result}[/]",
            _short_path(change.path, plan.home, plan.project),
        )
    console.print(table)
    for step in plan.manual:
        console.print(f"  [yellow]manual:[/yellow] {step}")
    if not dry_run and plan.changes:
        console.print(
            "\nRestart your assistant, then ask it: "
            '"Use the git-into-gsoc skill and call gsoc_program_info."'
        )


@app.command("doctor")
def doctor_cmd() -> None:
    """Check your setup: version, GitHub token, data locations, API access, skill, and MCP."""
    import sys

    from git_into_gsoc.config import cache_dir, data_dir, get_settings
    from git_into_gsoc.install.clients import env_home, installed_skills, registered_servers
    from git_into_gsoc.install.skill import InstallError, skill_source

    settings = get_settings()
    source = settings.github_token_source()
    console.print(f"git-into-gsoc {__version__}  (Python {sys.version.split()[0]})")
    console.print(f"cache: {cache_dir()}")
    console.print(f"data:  {data_dir()}")
    if source:
        console.print(f"GitHub token: [green]found[/green] via {source}")
    else:
        console.print(
            "GitHub token: [yellow]missing[/yellow] (60 requests per hour without one). "
            "Run `gh auth login` or set GITHUB_TOKEN."
        )
    try:
        rl = _toolkit().rate_limit()
        console.print(f"GitHub rate: {rl.get('remaining')}/{rl.get('limit')} remaining")
    except GigError as exc:
        console.print(f"[red]GitHub check failed:[/red] {exc}")
    try:
        console.print(f"skill source: {skill_source()}")
    except InstallError as exc:
        console.print(f"[red]skill source:[/red] {exc}")
    home, project = env_home(), Path.cwd()
    skills = installed_skills(home, project)
    servers = registered_servers(home, project)
    if skills:
        console.print("skill installed for: " + ", ".join(f"{label}" for label, _ in skills))
    else:
        console.print("skill installed for: [yellow]none[/yellow] (run `git-into-gsoc setup`)")
    if servers:
        console.print(
            "MCP registered in: " + ", ".join(_short_path(path, home) for _, path in servers)
        )
    else:
        console.print("MCP registered in: [yellow]nowhere yet[/yellow] (run `git-into-gsoc setup`)")


@app.command("cache")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Delete all cached HTTP responses"),
) -> None:
    """Show or clear the local HTTP cache."""
    http = _toolkit().github.http
    if clear:
        console.print(f"Removed {http.clear_cache()} cached responses")
        return
    console.print(f"Cache size: {http.cache_size_bytes() / 1_048_576:.1f} MiB")


if __name__ == "__main__":
    app()
