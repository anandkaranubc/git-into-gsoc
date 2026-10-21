"""Typer CLI for git-into-gsoc."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typer.core import TyperGroup

from git_into_gsoc import __version__
from git_into_gsoc.errors import GigError, InputError
from git_into_gsoc.guidance import ANTI_SPAM_RULES, journey_overview
from git_into_gsoc.models import LogEntry
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


@app.command("program", rich_help_panel="Start here")
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


@app.command("orgs", rich_help_panel="Find an organization")
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


@app.command("org", rich_help_panel="Find an organization")
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
    """Show one organization's ideas page, channels, GitHub organizations, and past projects."""
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


@app.command("projects", rich_help_panel="Find an organization")
def projects_cmd(
    query: str | None = typer.Argument(None, help="Keywords, for example 'graph neural networks'"),
    org: str | None = typer.Option(None, "--org", help="Limit to one organization"),
    since: int | None = typer.Option(None, "--since", help="Earliest program year"),
    limit: int = typer.Option(15, "--limit", "-n", help="How many projects to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Search past accepted GSoC projects to judge scope and find organizations."""
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


@app.command("ideas", rich_help_panel="Find an organization")
def ideas_cmd(
    org: str = typer.Argument(..., help="GSoC organization name, full or partial"),
    skills: str | None = typer.Option(
        None, "--skills", "-s", help="Skills to match, comma-separated (default: your profile)"
    ),
    size: str | None = typer.Option(None, "--size", help="small, medium, or large"),
    difficulty: str | None = typer.Option(None, "--difficulty", help="easy, medium, or hard"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many ideas to show"),
    no_follow: bool = typer.Option(
        False, "--no-follow", help="Do not open linked sub-project pages on umbrella orgs"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Read an org's ideas page into a table: size, difficulty, mentors, skills, links."""
    data = _toolkit().org_ideas(
        org,
        skills=split_csv(skills) or None,
        size=size,
        difficulty=difficulty,
        limit=limit,
        follow=not no_follow,
    )
    if output == Output.json or not data.get("found"):
        _emit(data, Output.json)
        return
    lines = [f"[bold]{escape(data['org'])}[/bold]", f"Ideas page: {data['ideas_url']}"]
    if data.get("fetched_url") and data["fetched_url"] != data["ideas_url"]:
        lines.append(f"[dim]Read as: {data['fetched_url']}[/dim]")
    lines.append(escape(data["note"]))
    for sentence in data.get("ai_policy") or []:
        lines.append(f"[yellow]AI policy:[/yellow] {escape(sentence)}")
    console.print(Panel(Text.from_markup("\n".join(lines)), title=f"Ideas: {data['layout']}"))
    if data["ideas"]:
        table = Table(title="Project ideas", caption="? marks a block with no labelled fields")
        table.add_column("Fit", justify="right")
        table.add_column("Idea", overflow="fold")
        table.add_column("Size", justify="right")
        table.add_column("Level")
        table.add_column("Mentors", overflow="fold", max_width=22)
        table.add_column("Skills", overflow="fold", max_width=26)
        for idea in data["ideas"]:
            title = escape(idea["title"])
            if idea.get("section"):
                title = f"[dim]{escape(idea['section'])} /[/dim] {title}"
            if idea["confidence"] == "low":
                title = f"? {title}"
            hours = f"{idea['hours']}h" if idea.get("hours") else (idea.get("size") or "")
            table.add_row(
                f"{idea['match_score']:.0f}" if idea["match_score"] else "",
                title,
                hours,
                idea.get("difficulty") or "",
                ", ".join(idea.get("mentors") or [])[:60],
                ", ".join(idea.get("skills") or [])[:60],
            )
        console.print(table)
        console.print(f"[dim]{escape(data['next_step'])}[/dim]")
    if data.get("past_proposals"):
        console.print("[bold]Shared past proposals (read to calibrate; never copy)[/bold]")
        for folder in data["past_proposals"][:4]:
            console.print(f"  {folder['files']} file(s): {folder['url']}")
    if data.get("sub_pages") and not data["ideas"]:
        console.print("[bold]Sub-project pages[/bold]")
        for page in data["sub_pages"][:20]:
            console.print(f"  {escape(page['title'])}: {page['url']}")
    if data.get("headings"):
        console.print(
            "[bold]Page sections[/bold]: " + "; ".join(escape(h) for h in data["headings"][:15])
        )


@app.command("mentors", rich_help_panel="Find an organization")
def mentors_cmd(
    org: str = typer.Argument(..., help="GSoC organization name, full or partial"),
    years: int = typer.Option(3, "--years", help="How many archived years to read"),
    limit: int = typer.Option(25, "--limit", "-n", help="How many mentors to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Who has mentored this organization's completed projects, and which repositories they touched."""
    data = _toolkit().org_mentors(org, years=years, limit=limit)
    if output == Output.json or not data.get("found"):
        _emit(data, Output.json)
        return
    per_year = ", ".join(f"{y}: {n}" for y, n in data["mentors_per_year"].items())
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]{escape(data['org'])}[/bold]  {data['projects']} completed projects in "
                f"{', '.join(str(y) for y in data['years_covered']) or 'no archived year'}\n"
                f"Mentors: {data['mentors_total']} named, {data['returning_mentors']} mentored in "
                f"two or more years  [dim]({per_year})[/dim]\n[dim]{escape(data['note'])}[/dim]"
            ),
            title="Mentors from the official archive",
        )
    )
    if data["mentors"]:
        table = Table(title="Mentors")
        table.add_column("Mentor", overflow="fold")
        table.add_column("Years")
        table.add_column("Projects", justify="right")
        table.add_column("Most recent project", overflow="fold")
        for mentor in data["mentors"]:
            recent = mentor["recent_projects"][0] if mentor["recent_projects"] else None
            table.add_row(
                escape(mentor["name"]),
                ", ".join(str(y) for y in mentor["years"]),
                str(mentor["projects"]),
                f"{recent['year']}: {escape(recent['title'])}" if recent else "",
            )
        console.print(table)
    if data["repos_touched"]:
        console.print(
            "[bold]Repositories past projects touched:[/bold] "
            + ", ".join(f"{r['repo']} ({r['projects']})" for r in data["repos_touched"][:8])
        )
    if data["top_tech_tags"]:
        console.print(
            "[bold]Tags on past projects:[/bold] "
            + ", ".join(f"{t['tag']} ({t['projects']})" for t in data["top_tech_tags"][:8])
        )


@app.command("repos", rich_help_panel="Pick a repository and an issue")
def repos_cmd(
    org: str = typer.Argument(
        ..., help="GSoC organization name, for example 'GNU Radio', or its GitHub login"
    ),
    language: str | None = typer.Option(None, "--language", "-l", help="Prefer this language"),
    limit: int = typer.Option(10, "--limit", "-n", help="How many repositories to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Rank an organization's repositories by ideas-page mentions, beginner issues, and activity."""
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


@app.command("repo", rich_help_panel="Pick a repository and an issue")
def repo_cmd(
    full_name: str = typer.Argument(
        ..., help="Repository as owner/name or a GitHub URL, for example sympy/sympy"
    ),
    track: bool = typer.Option(False, "--track", help="Also save this repo to your progress"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Check whether a newcomer's pull request can land here: grade, merge history, setup hints."""
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


@app.command("orient", rich_help_panel="Pick a repository and an issue")
def orient_cmd(
    full_name: str,
    codetour: Path | None = typer.Option(
        None, "--codetour", help="Also write a CodeTour file (VS Code) for the reading plan here"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Get your bearings in a repository: code map, entry points, test command, who merges, rules."""
    data = _toolkit().orient_repo(full_name, codetour=codetour is not None)
    if codetour is not None:
        codetour.parent.mkdir(parents=True, exist_ok=True)
        codetour.write_text(json.dumps(data["codetour"], indent=2) + "\n", encoding="utf-8")
    if output == Output.json:
        _emit(data, output)
        return
    if codetour is not None:
        console.print(f"Wrote the CodeTour file to {codetour}", soft_wrap=True)
    langs = ", ".join(f"{x['name']} {x['share']}%" for x in data["languages"]) or "unknown"
    head = (data.get("as_of_commit") or "")[:10]
    lines = [
        f"[bold]{data['repo']}[/bold]  {escape(data.get('description') or '')}",
        f"Languages: {langs}  |  License: {data.get('license') or 'none detected'}  |  "
        f"Last push: {data.get('pushed_days_ago')}d ago",
        f"[dim]As of commit {head} on {data['default_branch']}[/dim]",
    ]
    console.print(Panel(Text.from_markup("\n".join(lines)), title="Orientation"))

    table = Table(title="Code map (purpose is a guess from the directory name)")
    table.add_column("Directory")
    table.add_column("Files", justify="right")
    table.add_column("Mostly")
    table.add_column("Purpose")
    for row in data["code_map"]:
        table.add_row(row["path"], str(row["files"]), row["main_extension"], row["purpose"])
    console.print(table)

    def section(title: str, items: list[str]) -> None:
        if items:
            console.print(f"\n[bold]{title}[/bold]")
            for item in items:
                console.print(f"  {item}")

    section(
        "Entry points",
        [f"{p['path']}  [dim]{escape(p['reason'])}[/dim]" for p in data["entry_points"]],
    )
    section(
        "How CI runs the tests",
        [f"{escape(t['command'])}  [dim]({t['source']})[/dim]" for t in data["test_commands"]]
        + [escape(h) for h in data["setup_hints"]],
    )
    docs = data["docs"]
    section(
        "Read first",
        [
            p
            for p in (docs.get("readme"), docs.get("contributing"), *docs.get("architecture", []))
            if p
        ],
    )
    people = data["maintainers"]
    section(
        f"Who merges ({people['commits_90d']} commits in 90 days)",
        [f"@{p['login']} ({p['commits']})" for p in people["active_committers_90d"]]
        + [
            f"CODEOWNERS {escape(c['pattern'])}: {escape(c['owners'])}"
            for c in people["codeowners"][:5]
        ],
    )
    rules = data["conventions"]
    rule_lines = []
    if rules["dco"]["required"]:
        rule_lines.append(
            "Sign-off required (git commit -s): " + "; ".join(rules["dco"]["evidence"])
        )
    if rules["cla"]["required"]:
        rule_lines.append("CLA required: " + "; ".join(rules["cla"]["evidence"]))
    if rules["conventional_commits"]["expected"]:
        rule_lines.append(
            "Commit style type(scope): subject expected: "
            + "; ".join(rules["conventional_commits"]["evidence"])
        )
    if rules["pre_commit"]:
        rule_lines.append("pre-commit hooks configured: run `pre-commit install` before committing")
    if rules["pr_checklist_items"]:
        rule_lines.append(
            f"PR template has a {rules['pr_checklist_items']}-item checklist; fill it in"
        )
    if rules["ai_disclosure_in_pr_template"]:
        rule_lines.append("PR template asks for an AI disclosure")
    for gate in rules.get("gates") or []:
        rule_lines.append(f"{gate['gate']}  ({gate['source']})")
    section("Before you open a PR", [escape(line) for line in rule_lines])
    section(
        "Policies, in the project's words",
        [
            f"[{q['kind']}] {escape(q['text'])}  [dim]({q['source']})[/dim]"
            for q in data["policies"]
        ],
    )
    section("Where to talk", [", ".join(data["channels"])] if data["channels"] else [])
    section(
        "Read in this order",
        [
            f"{i}. {escape(step['path'])}  [dim]{escape(step['why'])}[/dim]"
            for i, step in enumerate(data["reading_plan"], 1)
        ],
    )
    console.print(f"\n[dim]{escape(data['note'])}[/dim]")


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


@app.command("issues", rich_help_panel="Pick a repository and an issue")
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
    """Find beginner issues that still look free: no pull request, assignee, or recent claim."""
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
        if issue.get("filed_by_maintainer"):
            ref += "\n[dim]filed by a maintainer[/dim]"
        table.add_row(
            f"{issue['beginner_score']:.0f}",
            f"[{_STATUS_STYLE.get(status, '')}]{status}[/]",
            ref,
            issue["title"],
        )
    console.print(table)
    if data["issues"]:
        console.print("[dim]Next: git-into-gsoc issue owner/repo#N before you comment.[/dim]")


@app.command("issue", rich_help_panel="Pick a repository and an issue")
def issue_cmd(
    ref: str = typer.Argument(..., help="owner/repo#123, an issue URL, or owner/repo"),
    number: int | None = typer.Argument(None, help="Issue number if REF is owner/repo"),
    track: bool = typer.Option(False, "--track", help="Also save this issue to your progress"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Check whether an issue is free to pick up: pull requests, claims, assignees, activity."""
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


@app.command("profile", rich_help_panel="Start here")
def profile_cmd(
    github: str | None = typer.Option(None, "--github", "-g", help="Your GitHub username"),
    tech: str | None = typer.Option(
        None, "--tech", "-t", help="Languages and tools you know, comma-separated"
    ),
    interests: str | None = typer.Option(
        None, "--interests", "-i", help="Topics you care about, comma-separated"
    ),
    hours: int | None = typer.Option(None, "--hours", help="Hours per week you can give"),
    tz: str | None = typer.Option(None, "--tz", help="Your timezone, for example Asia/Kolkata"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Show or save your profile. recommend and next use it when you give no flags."""
    toolkit = _toolkit()
    if any([github, tech, interests, hours is not None, tz]):
        data = toolkit.save_profile(
            github=github,
            technologies=split_csv(tech) or None,
            interests=split_csv(interests) or None,
            hours_per_week=hours,
            timezone=tz,
        )
    else:
        data = toolkit.progress.profile()
    if output == Output.json:
        _emit(data, output)
        return
    if not data:
        console.print(
            "No profile saved yet. Example:\n"
            "  git-into-gsoc profile --github you --tech python --interests science --hours 10"
        )
        return
    lines = []
    for key, label in (
        ("github", "GitHub"),
        ("top_language", "Top language on GitHub"),
        ("technologies", "Technologies"),
        ("interests", "Interests"),
        ("hours_per_week", "Hours per week"),
        ("timezone", "Timezone"),
    ):
        value = data.get(key)
        if value:
            lines.append(f"{label}: {', '.join(value) if isinstance(value, list) else value}")
    console.print(Panel(Text("\n".join(lines)), title="Your profile"))


@app.command("pointers", rich_help_panel="Pick a repository and an issue")
def pointers_cmd(
    ref: str = typer.Argument(..., help="owner/repo#123, an issue URL, or owner/repo"),
    number: int | None = typer.Argument(None, help="Issue number if REF is owner/repo"),
    similar: int = typer.Option(
        5, "--similar", help="How many similar closed issues to learn from"
    ),
    no_search: bool = typer.Option(False, "--no-search", help="Skip GitHub code search"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Where to start reading for an issue: files it names, past fixes of similar issues."""
    data = _toolkit().issue_pointers(ref, number, similar=similar, code_search=not no_search)
    if output == Output.json:
        _emit(data, output)
        return
    issue = data["issue"]
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]{escape(issue['title'])}[/bold]\n{issue['url']}\n"
                f"[dim]As of commit {(data.get('as_of_commit') or '')[:10]}[/dim]"
            ),
            title=f"{issue['repo']}#{issue['number']}",
        )
    )
    if data["files_likely_involved"]:
        table = Table(title="Files the issue points at")
        table.add_column("Confidence")
        table.add_column("Path", overflow="fold")
        table.add_column("Lines")
        table.add_column("Because", overflow="fold")
        for row in data["files_likely_involved"]:
            table.add_row(
                row["confidence"],
                row["path"],
                ", ".join(str(n) for n in row["lines"]),
                "; ".join(escape(r) for r in row["reasons"][:3]),
            )
        console.print(table)
    else:
        console.print(
            "[yellow]The issue text names no file this tool could match in the tree.[/yellow]"
        )
    if data["search_links"]:
        console.print("\n[bold]Search these on GitHub[/bold]")
        for link in data["search_links"]:
            console.print(f"  {escape(link['identifier'])}: {link['url']}")
    if data["code_search_note"]:
        console.print(f"[dim]{escape(data['code_search_note'])}[/dim]")
    if data["similar_fixes"]:
        table = Table(title=f"How similar '{data['similar_label']}' issues were fixed here")
        table.add_column("Issue", overflow="fold")
        table.add_column("Fix PR")
        table.add_column("Files", justify="right")
        table.add_column("Days")
        table.add_column("Touched", overflow="fold")
        for fix in data["similar_fixes"]:
            pr = fix["pull_request"]
            table.add_row(
                f"#{fix['issue']['number']} {escape(fix['issue']['title'][:50])}",
                f"#{pr['number']} ({pr['confidence']})",
                str(len(fix["files"])),
                str(fix["days_to_merge"] if fix["days_to_merge"] is not None else ""),
                ", ".join(escape(p) for p in fix["files"][:4]),
            )
        console.print(table)
    if not data["similar_fixes"] and data.get("similar_note"):
        console.print(f"[dim]{escape(data['similar_note'])}[/dim]")
    norm = data["fix_norm"]
    if norm.get("sample"):
        console.print(
            f"Fix norm here: median {norm['median_files']} file(s) per fix, "
            f"{norm['touches_tests_pct']}% touch tests, {norm['touches_docs_pct']}% touch docs "
            f"(from {norm['sample']} fixes)."
        )
    console.print(f"\n[dim]{escape(data['next_step'])}[/dim]")


@app.command("draft", rich_help_panel="Contribute and apply")
def draft_cmd(
    kind: str = typer.Argument(
        ..., help="intro, question, claim, pr, review-reply, status, or final"
    ),
    org: str | None = typer.Option(None, "--org", help="GSoC org name, for channels"),
    repo: str | None = typer.Option(None, "--repo", help="owner/repo, for its claim and PR rules"),
    issue: str | None = typer.Option(None, "--issue", help="owner/repo#N, for a claim or PR draft"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """A skeleton for an intro, question, claim comment, PR description, review reply, or report."""
    data = _toolkit().draft(kind, org=org, repo=repo, issue=issue)
    if output == Output.json:
        _emit(data, output)
        return
    console.print(Panel(Text(data["template"]), title=f"Draft: {data['kind']}"))
    if data.get("warning"):
        console.print(f"[yellow]![/yellow] {escape(data['warning'])}")
    console.print("[bold]Fill these with real observations before sending[/bold]")
    for field in data["must_fill"]:
        console.print(f"  ☐ {escape(field)}")
    console.print("\n[bold]Rules, with sources[/bold]")
    for rule in data["rules"]:
        console.print(f"  • {escape(rule['rule'])}\n    [dim]{rule['source']}[/dim]")
    console.print(f"\n[dim]{escape(data['note'])}[/dim]")


@app.command("recommend", rich_help_panel="Find an organization")
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
    """Suggest organizations and starter issues from your saved profile or flags."""
    data = _toolkit().recommend_path(
        username=github,
        technologies=split_csv(tech) or None,
        interests=split_csv(interests) or None,
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
    used = ", ".join(data["technologies_used"] + data["interests_used"]) or "none"
    console.print(f"Matching on: {escape(used)} ({data['profile_source']})")
    table = Table(title="Organizations")
    table.add_column("Score", justify="right")
    table.add_column("Organization", overflow="fold", max_width=28)
    table.add_column("Fit", overflow="fold")
    for org in data["recommended_orgs"][:8]:
        fit = [r for r in org.get("match_reasons") or [] if r.startswith(_FIT_PREFIXES)]
        table.add_row(f"{org['match_score']:.0f}", org["name"], "; ".join(fit))
    console.print(table)
    if data["starter_issues"]:
        issues = Table(title="Starter issues (verified availability)")
        issues.add_column("Status")
        issues.add_column("Issue", overflow="fold")
        issues.add_column("Title", overflow="fold")
        for issue in data["starter_issues"]:
            status = issue["availability"]
            issues.add_row(
                f"[{_STATUS_STYLE.get(status, '')}]{status}[/]",
                f"{issue['repo']}#{issue['number']}",
                escape(issue["title"]),
            )
        console.print(issues)
    elif data.get("starter_issue_error"):
        console.print(
            f"[yellow]Starter issues unavailable:[/yellow] {data['starter_issue_error']['error']}"
        )
    console.print("\n[bold]Next steps[/bold]")
    for step in data["next_steps"]:
        console.print(f"  → {step}")


_FINDING_MARK = {"pass": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}
_STRENGTH_STYLE = {"strong": "green", "developing": "cyan", "starting": "yellow", "none": "red"}


@app.command("contributions", rich_help_panel="Contribute and apply")
def contributions_cmd(
    github: str = typer.Option(..., "--github", "-g", help="Your GitHub username"),
    org: str | None = typer.Option(None, "--org", help="GSoC org name or GitHub org"),
    repo: str | None = typer.Option(None, "--repo", help="owner/repo to scope to"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Collect your PRs, issues, and reviews in an org's repos as proposal evidence."""
    if not org and not repo:
        raise typer.BadParameter("Pass --org or --repo")
    data = _toolkit().contribution_evidence(github, org=org, repo=repo)
    if output == Output.json:
        _emit(data, output)
        return
    counts = data["counts"]
    scope = data["scope"]
    where = scope["repo"] or ", ".join(scope["github_owners"]) or scope["org"]
    style = _STRENGTH_STYLE.get(data["strength"], "")
    console.print(
        Panel.fit(
            f"[bold]@{data['username']}[/bold] in {where}\n"
            f"Standing: [{style}]{data['strength']}[/]\n"
            f"PRs merged {counts['prs_merged']} · open {counts['prs_open']} · "
            f"closed {counts['prs_closed_unmerged']} · issues {counts['issues_opened']} · "
            f"threads joined {counts['threads_joined']} · reviews {counts['reviews_given']}",
            title="Contribution evidence",
        )
    )
    if data["evidence_markdown"]:
        console.print("\n[bold]Paste into your proposal[/bold]")
        for line in data["evidence_markdown"]:
            console.print(f"  {escape(line)}")
    if data["gaps"]:
        console.print("\n[bold]Gaps to close[/bold]")
        for gap in data["gaps"]:
            console.print(f"  [yellow]![/yellow] {escape(gap)}")


@app.command("proposal", rich_help_panel="Contribute and apply")
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


@app.command("progress", rich_help_panel="Track your journey")
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


@app.command("journey", rich_help_panel="Start here")
def journey_cmd(output: Output = OUTPUT_OPTION) -> None:
    """Show every phase of the journey with its goal and actions."""
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


@app.command("next", rich_help_panel="Start here")
def next_cmd(
    year: int | None = typer.Option(None, help="Program year (default: the target year)"),
    no_check: bool = typer.Option(
        False, "--no-check", help="Skip live re-checks of tracked issues and new-issue search"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """What should I do right now? Phase, deadlines, tracked-issue changes, new issues, actions."""
    data = _toolkit().next_steps(year=year, recheck=not no_check)
    if output == Output.json:
        _emit(data, output)
        return
    program = data["program"]
    badge = (
        "[green]official[/green]" if program["dates_are_official"] else "[yellow]estimate[/yellow]"
    )
    phase = program["phase"]
    console.print(
        Panel.fit(
            f"[bold]GSoC {program['year']}[/bold]  dates: {badge}\n"
            f"[bold cyan]Now:[/bold cyan] {phase['title']}\n{phase['advice']}",
            title="Where you are",
        )
    )
    if data["deadlines"]:
        console.print("\n[bold]Coming up[/bold]")
        for item in data["deadlines"]:
            mark = "" if item["official"] else " (estimate)"
            console.print(
                f"  {item['at'][:10]}  {item['label']}{mark}  {_relative(item['days_until'])}"
            )
    if data.get("time_budget"):
        budget = data["time_budget"]
        mark = "" if budget["official"] else " (estimate)"
        console.print("\n[bold]Time budget[/bold]")
        console.print(
            f"  {budget['hours_per_week']} h/week for about {budget['weeks']} week(s) until "
            f"{escape(budget['until'])}{mark}: about {budget['hours_available']} hours"
        )
        for part in budget["suggested_split"]:
            console.print(f"  {part['hours']:>4} h  {escape(part['what'])}")
    if data["changes"]:
        console.print("\n[bold]Changed since your last check[/bold]")
        for change in data["changes"]:
            console.print(f"  [yellow]![/yellow] {escape(change)}")
    if data["tracked_issues"]:
        console.print("\n[bold]Tracked issues[/bold]")
        for item in data["tracked_issues"]:
            style = _STATUS_STYLE.get(item["availability"], "")
            console.print(
                f"  [{style}]{item['availability']:<12}[/] {item['ref']}  [dim]{escape(item['reason'])}[/dim]"
            )
    if data["new_issues"]:
        console.print("\n[bold]New beginner issues in places you follow[/bold]")
        for issue in data["new_issues"][:5]:
            console.print(f"  {issue['repo']}#{issue['number']}  {escape(issue['title'])}")
    console.print("\n[bold]Do next[/bold]")
    for index, action in enumerate(data["actions"], 1):
        console.print(f"  {index}. {escape(action['title'])}")
        console.print(f"     [cyan]{escape(action['command'])}[/cyan]")
        console.print(f"     [dim]{escape(action['why'])}[/dim]")
    console.print(f"\n[dim]{data['note']}[/dim]")


@app.command("log", rich_help_panel="Track your journey")
def log_cmd(
    goal: str | None = typer.Option(None, "--goal", help="This week's goal"),
    done: str | None = typer.Option(None, "--done", help="What you tried or finished"),
    links: str | None = typer.Option(None, "--links", help="Links to work, comma-separated"),
    learned: str | None = typer.Option(None, "--learned", help="What you learned"),
    stuck: str | None = typer.Option(None, "--stuck", help="Where you are stuck"),
    next_step: str | None = typer.Option(None, "--next", help="Your next small step"),
    limit: int = typer.Option(5, "--limit", "-n", help="How many past notes to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Write a weekly note, or show recent ones when you give no fields."""
    store = _toolkit().progress
    if any([goal, done, links, learned, stuck, next_step]):
        entry = LogEntry(
            goal=(goal or "").strip(),
            done=(done or "").strip(),
            links=split_csv(links),
            learned=(learned or "").strip(),
            stuck=(stuck or "").strip(),
            next_step=(next_step or "").strip(),
        )
        store.add_log(entry)
        entries = [entry]
        title = "Saved this note"
    else:
        entries = store.recent_logs(limit=limit)
        title = f"Last {len(entries)} note(s)"
    if output == Output.json:
        _emit([e.model_dump(mode="json") for e in entries], output)
        return
    if not entries:
        console.print(
            "No notes yet. Example:\n"
            '  git-into-gsoc log --goal "Reproduce issue 12" --done "Reproduced on main" '
            '--stuck "Flaky test" --next "Ask in the project chat"'
        )
        return
    console.print(f"[bold]{title}[/bold]")
    for entry in entries:
        lines = []
        for label, value in (
            ("Goal", entry.goal),
            ("Done", entry.done),
            ("Links", ", ".join(entry.links)),
            ("Learned", entry.learned),
            ("Stuck", entry.stuck),
            ("Next", entry.next_step),
        ):
            if value:
                lines.append(f"{label}: {escape(value)}")
        console.print(Panel(Text.from_markup("\n".join(lines)), title=f"{entry.at:%Y-%m-%d}"))


@app.command("mcp", rich_help_panel="Maintenance")
def mcp_cmd() -> None:
    """Run the MCP server so AI assistants can use these tools. Press Ctrl+C to stop."""
    from git_into_gsoc.mcp_server import main as mcp_main

    mcp_main()


def _reachable(url: str, user_agent: str) -> str:
    """One quick request per data source so doctor can say which one is down."""
    import time

    import httpx

    started = time.monotonic()
    try:
        with httpx.Client(timeout=6.0, headers={"User-Agent": user_agent}) as client:
            response = client.head(url, follow_redirects=True)
            if response.status_code == 405:
                response = client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        return f"[red]unreachable[/red] ({type(exc).__name__})"
    elapsed = time.monotonic() - started
    if response.status_code < 400:
        return f"[green]ok[/green] ({elapsed:.1f}s)"
    return f"[yellow]HTTP {response.status_code}[/yellow] ({elapsed:.1f}s)"


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


@app.command("setup", rich_help_panel="Start here")
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
    remove: bool = typer.Option(
        False, "--remove", help="Undo: delete the skill copies and the MCP registrations"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Install the Agent Skill and register the MCP server with your AI assistants."""
    from git_into_gsoc.install import plan_setup, run_removal, run_setup
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
    if remove:
        run_removal(plan, dry_run=dry_run)
    else:
        run_setup(plan, dry_run=dry_run)
    if output == Output.json:
        _emit(
            {
                "scope": plan.scope,
                "remove": remove,
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
    done = "Removal complete" if remove else "Setup complete"
    title = ("Plan (dry run)" if dry_run else done) + f" · {plan.scope} scope"
    table = Table(title=title)
    table.add_column("Assistant")
    table.add_column("What")
    table.add_column("Result")
    table.add_column("Path", overflow="fold")
    styles = {
        "created": "green",
        "updated": "green",
        "removed": "green",
        "unchanged": "dim",
        "skipped": "yellow",
    }
    for change in plan.changes:
        result = change.action + (f" ({change.note})" if change.note else "")
        table.add_row(
            change.assistant,
            change.kind,
            f"[{styles.get(change.action, '')}]{result}[/]",
            ""
            if change.action == "skipped" and change.path == plan.root
            else _short_path(change.path, plan.home, plan.project),
        )
    console.print(table)
    if plan.project:
        console.print(f"./ is {plan.project}")
    console.print(f"MCP command: {' '.join(plan.command)}")
    for step in plan.manual:
        console.print(f"  [yellow]manual:[/yellow] {step}")
    if not dry_run and plan.changes and not remove:
        console.print(
            "\nRestart your assistant, then ask it: "
            '"Use the git-into-gsoc skill and call gsoc_program_info."'
        )


@app.command("doctor", rich_help_panel="Maintenance")
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
    for label, url in (
        ("official GSoC site", f"{settings.gsoc_official_api_url.rstrip('/')}/program/2026/"),
        ("organization archive", f"{settings.gsoc_orgs_api_url.rstrip('/')}/2026.json"),
        (
            "commit statistics",
            f"{settings.ecosystems_commits_api_url.rstrip('/')}/hosts/GitHub/repositories/sympy/sympy",
        ),
    ):
        console.print(f"{label}: {_reachable(url, settings.user_agent)}")
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


@app.command("cache", rich_help_panel="Maintenance")
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
