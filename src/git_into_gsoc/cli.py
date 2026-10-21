"""Typer CLI for git-into-gsoc."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typer.core import TyperGroup

from git_into_gsoc import __version__
from git_into_gsoc.errors import GigError
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


app = typer.Typer(
    name="git-into-gsoc",
    help="AI-native toolkit for aspiring Google Summer of Code contributors.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    cls=_FriendlyErrors,
    pretty_exceptions_show_locals=False,
)


class Output(StrEnum):
    rich = "rich"
    json = "json"


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
    """AI-native toolkit for aspiring Google Summer of Code contributors."""
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
    year: int = typer.Option(2027, help="Program year"),
    size: ProjectSize = typer.Option(
        ProjectSize.medium, "--size", help="Project size for evaluation deadlines"
    ),
    output: Output = Output.rich,
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
    query: str | None = typer.Option(None, "--query", "-q", help="Free-text search"),
    tech: str | None = typer.Option(None, "--tech", "-t", help="Comma-separated technologies"),
    topics: str | None = typer.Option(None, "--topics", help="Comma-separated topics/interests"),
    category: str | None = typer.Option(None, "--category", "-c"),
    year: int | None = typer.Option(
        None, help="Program year (default: target year; falls back to latest announced)"
    ),
    limit: int = typer.Option(10, "--limit", "-n"),
    output: Output = Output.rich,
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
            "; ".join(fit) or "—",
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
    name: str,
    year: int | None = typer.Option(None, help="Program year"),
    output: Output = Output.rich,
) -> None:
    """Show ideas page, channels, GitHub orgs, slot history, and past projects."""
    data = _toolkit().org_details(name, year=year)
    if output == Output.json or not data.get("found"):
        _emit(data, Output.json)
        return
    org = data["organization"]
    lines = [f"[bold]{org['name']}[/bold] — {org['description']}"]
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
        table = Table(title="Recent accepted projects (scope reference — never copy)")
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
    limit: int = typer.Option(15, "--limit", "-n"),
    output: Output = Output.rich,
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


@app.command("repo")
def repo_cmd(full_name: str, output: Output = Output.rich) -> None:
    """Evaluate repository health for contributors."""
    data = _toolkit().evaluate_repo(full_name)
    if output == Output.json:
        _emit(data, output)
        return
    health = data["health"]
    console.print(
        Panel.fit(
            f"[bold]{health['full_name']}[/bold]  grade={health['grade']}  "
            f"score={health['health_score']}\n{data['recommendation']}",
            title="Repo health",
        )
    )
    if health.get("signals"):
        console.print("[green]Signals[/green]")
        for s in health["signals"]:
            console.print(f"  ✓ {s}")
    if health.get("warnings"):
        console.print("[yellow]Warnings[/yellow]")
        for w in health["warnings"]:
            console.print(f"  ! {w}")


@app.command("issues")
def issues_cmd(
    language: str | None = typer.Option(None, "--language", "-l"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
    limit: int = typer.Option(10, "--limit", "-n"),
    output: Output = Output.rich,
) -> None:
    """Find beginner-friendly issues with availability checks."""
    issues = _toolkit().find_issues(language=language, org=org, repo=repo, max_results=limit)
    if output == Output.json:
        _emit(issues, output)
        return
    table = Table(title="Beginner-friendly issues")
    table.add_column("Score", justify="right")
    table.add_column("Availability")
    table.add_column("Issue")
    table.add_column("Title")
    for issue in issues:
        table.add_row(
            str(issue["beginner_score"]),
            issue["availability"],
            f"{issue['repo']}#{issue['number']}",
            issue["title"][:70],
        )
    console.print(table)


@app.command("issue")
def issue_cmd(full_name: str, number: int, output: Output = Output.rich) -> None:
    """Check availability of a specific issue."""
    data = _toolkit().issue_status(full_name, number)
    _emit(data if output == Output.json else json.dumps(data, indent=2), output)


@app.command("recommend")
def recommend_cmd(
    github: str | None = typer.Option(None, "--github", "-g"),
    tech: str | None = typer.Option(None, "--tech", "-t"),
    interests: str | None = typer.Option(None, "--interests", "-i"),
    output: Output = Output.rich,
) -> None:
    """Personalized org + issue recommendations."""
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


@app.command("proposal")
def proposal_cmd(output: Output = Output.rich) -> None:
    """Show proposal checklist and structure."""
    data = _toolkit().proposal_help()
    if output == Output.json:
        _emit(data, output)
        return
    console.print("[bold]Checklist[/bold]")
    for item in data["checklist"]:
        console.print(f"☐ {item['title']} — {item['description']}")
    console.print("\n[bold]Suggested structure[/bold]")
    for i, section in enumerate(data["structure"], 1):
        console.print(f"  {i}. {section}")


@app.command("progress")
def progress_cmd(
    action: str = typer.Argument("summary"),
    phase: str | None = typer.Option(None),
    value: str | None = typer.Option(None, "--value", "-v"),
    output: Output = Output.rich,
) -> None:
    """Track journey progress (summary|complete_phase|shortlist_org|track_repo|...)."""
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
def journey_cmd(output: Output = Output.rich) -> None:
    """Print the full contributor journey overview."""
    data = journey_overview()
    if output == Output.json:
        _emit(data, output)
        return
    phases = data["phases"]
    assert isinstance(phases, dict)
    for phase, guide in phases.items():
        assert isinstance(guide, dict)
        console.print(f"\n[bold cyan]{phase}[/bold cyan] — {guide['goal']}")
        for action in guide["actions"]:
            console.print(f"  • {action}")


@app.command("mcp")
def mcp_cmd() -> None:
    """Run the MCP server on stdio (for Cursor, Claude Code, etc.)."""
    from git_into_gsoc.mcp_server import main as mcp_main

    mcp_main()


@app.command("doctor")
def doctor_cmd() -> None:
    """Check environment: Python package, GitHub auth, cache paths."""
    import sys

    from git_into_gsoc.config import cache_dir, data_dir, get_settings

    settings = get_settings()
    source = settings.github_token_source()
    console.print(f"git-into-gsoc {__version__}  (Python {sys.version.split()[0]})")
    console.print(f"cache: {cache_dir()}")
    console.print(f"data:  {data_dir()}")
    if source:
        console.print(f"GitHub token: [green]found[/green] via {source}")
    else:
        console.print(
            "GitHub token: [yellow]missing[/yellow] — 60 req/h limit. "
            "Run `gh auth login` or set GITHUB_TOKEN."
        )
    try:
        rl = _toolkit().rate_limit()
        console.print(f"GitHub rate: {rl.get('remaining')}/{rl.get('limit')} remaining")
    except GigError as exc:
        console.print(f"[red]GitHub check failed:[/red] {exc}")


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
