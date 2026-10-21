"""Typer CLI for git-into-gsoc."""

from __future__ import annotations

import json
from enum import StrEnum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from git_into_gsoc import __version__
from git_into_gsoc.guidance import ANTI_SPAM_RULES, journey_overview
from git_into_gsoc.service import GSoCToolkit

app = typer.Typer(
    name="git-into-gsoc",
    help="AI-native toolkit for aspiring Google Summer of Code contributors.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


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


@app.command("program")
def program_cmd(
    year: int = typer.Option(2027, help="Program year"),
    output: Output = Output.rich,
) -> None:
    """Show program timeline, official links, and anti-spam rules."""
    data = _toolkit().program_info(year)
    if output == Output.json:
        _emit(data, output)
        return
    console.print(
        Panel.fit(
            f"[bold]GSoC {year}[/bold]\n{data['disclaimer']}\n\n"
            f"Official: {data['official_home']}\n"
            f"Program page: {data['program_page']}",
            title="git-into-gsoc",
        )
    )
    table = Table(title="Timeline")
    table.add_column("Date")
    table.add_column("Milestone")
    table.add_column("Status")
    table.add_column("Notes")
    for event in data["timeline"]:
        table.add_row(event["date"], event["name"], event["status"], event.get("notes") or "")
    console.print(table)
    console.print("\n[bold]Anti-spam rules[/bold]")
    for rule in ANTI_SPAM_RULES:
        console.print(f"• {rule}")


@app.command("orgs")
def orgs_cmd(
    query: str | None = typer.Option(None, "--query", "-q"),
    tech: str | None = typer.Option(None, "--tech", "-t", help="Comma-separated technologies"),
    topics: str | None = typer.Option(None, "--topics", help="Comma-separated topics"),
    category: str | None = typer.Option(None, "--category", "-c"),
    year: int = typer.Option(2026, help="Archive year to search"),
    limit: int = typer.Option(10, "--limit", "-n"),
    output: Output = Output.rich,
) -> None:
    """Search mentoring organizations."""
    techs = [x.strip() for x in (tech or "").split(",") if x.strip()]
    tops = [x.strip() for x in (topics or "").split(",") if x.strip()]
    results = _toolkit().match_orgs(
        query=query,
        technologies=techs or None,
        topics=tops or None,
        category=category,
        year=year,
        limit=limit,
    )
    if output == Output.json:
        _emit(results, output)
        return
    table = Table(title=f"GSoC organizations (archive year {year})")
    table.add_column("Score", justify="right")
    table.add_column("Name")
    table.add_column("Tech")
    table.add_column("Years")
    table.add_column("Why")
    for org in results:
        table.add_row(
            str(org["match_score"]),
            org["name"],
            ", ".join(org.get("technologies") or [])[:40],
            ",".join(str(y) for y in (org.get("years_active") or [])[-4:]),
            "; ".join(org.get("match_reasons") or [])[:60],
        )
    console.print(table)


@app.command("org")
def org_cmd(name: str, output: Output = Output.rich) -> None:
    """Show details for one organization."""
    data = _toolkit().org_details(name)
    _emit(data if output == Output.json else json.dumps(data, indent=2, default=str), output)


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
        console.print(f"  • {org['name']} (score {org['match_score']})")
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
    from git_into_gsoc.config import cache_dir, data_dir, get_settings

    settings = get_settings()
    token = settings.resolve_github_token()
    console.print(f"git-into-gsoc {__version__}")
    console.print(f"cache: {cache_dir()}")
    console.print(f"data:  {data_dir()}")
    console.print(
        f"GitHub token: {'set' if token else 'missing (unauthenticated rate limits apply)'}"
    )
    try:
        rl = _toolkit().rate_limit()
        console.print(f"GitHub rate: {rl.get('remaining')}/{rl.get('limit')} remaining")
    except Exception as exc:
        console.print(f"[red]GitHub check failed:[/red] {exc}")


if __name__ == "__main__":
    app()
