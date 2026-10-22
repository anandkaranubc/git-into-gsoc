"""Typer CLI for git-into-gsoc."""

from __future__ import annotations

import codecs
import contextlib
import json
import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typer.core import TyperGroup

from git_into_gsoc import __version__, onboarding
from git_into_gsoc.errors import GigError, InputError
from git_into_gsoc.github.availability import pull_ref
from git_into_gsoc.guidance import journey_overview
from git_into_gsoc.models import LogEntry
from git_into_gsoc.service import GSoCToolkit
from git_into_gsoc.text import strip_hidden, strip_hidden_all
from git_into_gsoc.validation import split_csv

console = Console()
err_console = Console(stderr=True)


def _tolerate_unencodable_output() -> None:
    """Print "?" for characters the output encoding cannot represent, never crash.

    On Windows, output that is piped (an assistant running a command, or `> file`)
    uses a legacy code page such as cp1252, which has no ☐, ✓, or emoji, and issue
    titles are full of emoji. JSON output is plain ASCII and unaffected.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="replace")


def _read_document(path: Path) -> str:
    """Read a text file the way an editor would: UTF-8 (with or without a byte-order
    mark), UTF-16 from Notepad or Word, or the Windows legacy code page."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


class _FriendlyErrors(TyperGroup):
    """Render expected failures as one-line errors with a hint, not tracebacks."""

    def main(self, *args: Any, **kwargs: Any) -> Any:
        _tolerate_unencodable_output()
        return super().main(*args, **kwargs)

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except GigError as exc:
            # Messages quote what was typed ("a/b#[/bold]"), so they print literally.
            err_console.print(f"[bold red]error:[/bold red] {escape(str(exc))}")
            if exc.hint:
                err_console.print(f"[dim]hint:[/dim] {escape(exc.hint)}")
            raise typer.Exit(code=1) from exc


OUTPUT_HELP = "rich for readable tables and panels, json for scripts and assistants"

app = typer.Typer(
    name="git-into-gsoc",
    help=(
        "Prepare for Google Summer of Code with real data: find organizations, "
        "check repositories, find beginner issues, and plan your proposal."
    ),
    invoke_without_command=True,
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


# Rich reads "[...]" as markup. Text from issues, ideas pages, CONTRIBUTING files, labels,
# and the user's own notes must print literally: an unescaped "[x]" vanishes and an
# unescaped "[/]" raises MarkupError. Same pattern as rich.markup.escape, but idempotent,
# so escaping data once up front and again at a call site never shows a backslash.
_MARKUP_TAG = re.compile(r"(?<!\\)(\[[a-z#/@][^\[\]]*\])")


def escape(text: str) -> str:
    """Make text print literally: no markup, no hidden or terminal-control characters."""
    escaped = _MARKUP_TAG.sub(r"\\\1", strip_hidden(text))
    if escaped.endswith("\\") and not escaped.endswith("\\\\"):
        escaped += "\\"  # a trailing backslash would otherwise escape the next tag
    return escaped


def _markup_safe(value: Any) -> Any:
    """Escape every string in command output before rich rendering (never for JSON)."""
    if isinstance(value, str):
        return escape(value)
    if isinstance(value, dict):
        return {k: _markup_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_markup_safe(v) for v in value]
    return value


def _emit_or_fail(data: dict[str, Any], output: Output) -> None:
    """JSON as-is; a not-found result becomes a one-line error with exit code 1."""
    if data.get("found", True):
        _emit(data, Output.json)
        return
    if output == Output.json:
        _emit(data, Output.json)
    else:
        err_console.print(f"[bold red]error:[/bold red] {escape(str(data.get('error')))}")
        if data.get("hint"):
            err_console.print(f"[dim]hint:[/dim] {escape(str(data['hint']))}")
    raise typer.Exit(code=1)


def _emit(data: object, output: Output) -> None:
    data = strip_hidden_all(data)
    if output == Output.json:
        console.print_json(json.dumps(data, default=str))
    else:
        console.print(data, markup=False)


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
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
    if ctx.invoked_subcommand is None:
        _render_home(onboarding.home(_toolkit()))


GUIDE_URL = "https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/README.md"

# The handful of commands a newcomer needs first; `--help` lists every one.
_HOME_COMMANDS = (
    ("start", "Answer four questions, get organizations that fit you"),
    ("next", "What to do right now, from your saved progress"),
    ("orgs", "Rank organizations for your skills and interests"),
    ("issues", "Find beginner issues nobody has claimed"),
    ("program", "The GSoC timeline and where we are in it"),
    ("doctor", "Check your setup if something does not work"),
)


def _when(milestone: dict[str, Any]) -> str:
    days = milestone["days_until"]
    when = {0: "today", 1: "tomorrow"}.get(days, f"in {days} days")
    mark = "" if milestone["official"] else ", an estimate"
    return f"{milestone['label']}, {milestone['at'][:10]} ({when}{mark})"


def _say(*objects: Any) -> None:
    """Print without Rich's number and quote colouring, which is noise in sentences."""
    console.print(*objects, highlight=False)


def _render_program_line(program: dict[str, Any] | None) -> None:
    if program:
        _say(f"\n[bold]GSoC {program['year']}[/bold]: {program['phase']}")
        if program["next_milestone"]:
            _say(f"[dim]Next date: {_when(program['next_milestone'])}[/dim]")


def _render_home(data: dict[str, Any]) -> None:
    """What a bare `git-into-gsoc` shows: a short, personal starting point."""
    data = _markup_safe(data)
    _say(
        f"[bold]git into gsoc[/bold] [dim]{data['version']}[/dim]\n"
        "Find your first open-source contribution and prepare for Google Summer of Code."
    )
    _render_program_line(data["program"])
    if data["new_user"]:
        _say(
            "\n[bold]New here?[/bold] Answer four questions and get organizations that fit "
            "you. It takes about two minutes.\n  [cyan]git-into-gsoc start[/cyan]"
        )
    else:
        who = f", @{data['github']}" if data["github"] else ""
        _say(f"\n[bold]Welcome back{who}.[/bold] Your progress: {data['done']} of {data['total']}")
        for step in data["milestones"]:
            if step["done"]:
                count = f" ({step['count']})" if step["count"] > 1 else ""
                _say(f"  [green]✓[/green] {step['label']}{count}")
            else:
                _say(f"  [dim]○ {step['label']}[/dim]")
        _say(f"What to do now, with live checks:\n  [cyan]{data['next_command']}[/cyan]")
    _say("\n[bold]Commands to start with[/bold]")
    for name, what in _HOME_COMMANDS:
        _say(f"  [cyan]{name:<8}[/cyan] {what}")
    _say(
        f"\n[dim]Every command: git-into-gsoc --help. Step-by-step guide: {GUIDE_URL}\n"
        "Something confusing or broken? git-into-gsoc feedback[/dim]"
    )


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


def _stdin_is_interactive() -> bool:
    return sys.stdin.isatty()


def _ask(question: str, default: str = "") -> str:
    """One question; Enter keeps the default, which may be empty (skip)."""
    answer: str = typer.prompt(
        question, default=default, show_default=bool(default), prompt_suffix="\n  > "
    )
    return strip_hidden(answer).strip()


def _ask_github(toolkit: GSoCToolkit, default: str) -> tuple[str | None, list[str]]:
    """Ask for a username until GitHub knows it or the person skips; return its languages."""
    question = "1 of 4  Your GitHub username? It lets the tool read your public languages."
    while True:
        login = _ask(question, default)
        if not login:
            return None, []
        try:
            profile = toolkit.save_profile(github=login)
        except GigError as exc:
            reason = str(exc).rstrip(".")
            _say(f"  [yellow]![/yellow] {escape(reason)}.")
            _say("  Check the spelling and try again, or press Enter to skip.")
            default = ""
            continue
        languages = [str(lang["name"]) for lang in profile.get("languages") or []][:4]
        if profile.get("warning"):
            console.print(f"  [yellow]![/yellow] {escape(profile['warning'])}")
        elif languages:
            console.print(
                f"  [green]✓[/green] Found @{escape(login)}. Your public code is mostly {escape(', '.join(languages))}."
            )
        else:
            console.print(
                f"  [green]✓[/green] Found @{escape(login)}. No public code yet, which is fine."
            )
        return login, languages


def _ask_hours(default: str) -> int | None:
    while True:
        answer = _ask("4 of 4  About how many hours a week can you give?", default)
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= 80:
            return int(answer)
        console.print("  [yellow]![/yellow] Type a number from 1 to 80, or press Enter to skip.")


def _render_topic_menu() -> None:
    items = [f"{i:>2}  {label}" for i, (_, label) in enumerate(onboarding.TOPIC_CHOICES, 1)]
    half = (len(items) + 1) // 2
    right_column = items[half:] + [""] * (half - len(items[half:]))
    for left, right in zip(items[:half], right_column, strict=True):
        console.print(f"  [dim]{left:<40}{right}[/dim]", highlight=False)


def _numbered(rows: list[str]) -> None:
    """A numbered list whose long lines wrap under their own text, not under the number."""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="right")
    grid.add_column()
    for index, row in enumerate(rows, 1):
        grid.add_row(f"{index}.", Text.from_markup(row))
    _say(Padding(grid, (0, 0, 0, 2)))


def _render_matches(data: dict[str, Any]) -> None:
    orgs = data["organizations"]
    if not orgs:
        _say("\nNo organizations matched those answers yet. Try broader words, or browse by topic.")
        return
    _say("\n[bold]Organizations that fit you[/bold]")
    if data["catalog"].get("note"):
        _say(f"[dim]{data['catalog']['note']}[/dim]")
    rows = []
    for org in orgs:
        reasons = [r for r in org["match_reasons"] if not r.startswith("Accepted in")][:3]
        row = f"[bold]{org['name']}[/bold]"
        if org.get("description"):
            row += f"\n{org['description']}"
        row += f"\n[dim]Why: {'; '.join(reasons)}[/dim]"
        for line in (org.get("readiness") or [])[:1]:
            row += f"\n[green]✓[/green] {line}"
        for line in (org.get("caveats") or [])[:2]:
            row += f"\n[yellow]![/yellow] {line}"
        rows.append(row)
    _numbered(rows)
    for org in data.get("set_aside") or []:
        _say(
            f"[dim]Left out: {org['name']} says it will not take part this year "
            f"({org.get('url')}).[/dim]"
        )
    if data["profile"].get("hours_note"):
        _say(f"[yellow]![/yellow] {data['profile']['hours_note']}")


def _render_next_steps(data: dict[str, Any]) -> None:
    if data["shortlisted"]:
        _say(f"\n[green]✓[/green] Your shortlist: {', '.join(data['shortlisted'])}")
    _say("\n[bold]Your next steps[/bold]")
    _numbered([f"{step['title']}\n[cyan]{step['command']}[/cyan]" for step in data["next_steps"]])
    _say(
        "\n[dim]Change your answers any time: run start again, or git-into-gsoc profile.\n"
        "Prefer an AI assistant? After `git-into-gsoc setup`, ask it in your own words, "
        'such as "Which GSoC issue should I try first?"[/dim]'
    )


def _interview(
    toolkit: GSoCToolkit,
    saved: dict[str, Any],
    *,
    ask_github: bool,
    technologies: list[str] | None,
    topics: list[str] | None,
    hours: int | None,
) -> tuple[list[str] | None, list[str] | None, int | None]:
    """Ask whatever the options did not answer. The username is saved as it is checked."""
    console.print(
        Panel.fit(
            "Four quick questions, then organizations that fit you and what to do next.\n"
            "Press Enter to skip any question. Your answers stay on this computer.",
            title="git into gsoc: start",
        )
    )
    program = onboarding.program_now(toolkit)
    if program:
        _render_program_line(_markup_safe(program))
        _say(f"[dim]{escape(program['advice'])}[/dim]\n")
    known: list[str] = []
    if ask_github:
        default = str(saved.get("github") or onboarding.signed_in_login(toolkit) or "")
        known = [lang.lower() for lang in _ask_github(toolkit, default)[1]]
    if technologies is None:
        answer = _ask(
            "2 of 4  Languages and tools you know? For example: " + onboarding.TECH_EXAMPLES,
            ", ".join(saved.get("technologies") or known),
        )
        technologies = split_csv(answer) or None
    if topics is None:
        console.print(
            "3 of 4  What would you enjoy working on? Pick numbers or type your own words.",
            highlight=False,
        )
        _render_topic_menu()
        answer = _ask("Separate several with commas", ", ".join(saved.get("interests") or []))
        topics = onboarding.parse_topics(answer) or None
    if hours is None:
        hours = _ask_hours(str(saved.get("hours_per_week") or ""))
    return technologies, topics, hours


@app.command("start", rich_help_panel="Start here")
def start_cmd(
    github: str | None = typer.Option(
        None, "--github", "-g", help="Your GitHub username, to read your public languages"
    ),
    tech: str | None = typer.Option(
        None, "--tech", "-t", help="Languages and tools you know, comma-separated"
    ),
    interests: str | None = typer.Option(
        None,
        "--interests",
        "-i",
        help="Topics you care about, comma-separated words or numbers from the start menu",
    ),
    hours: int | None = typer.Option(
        None, "--hours", min=1, max=80, help="Hours per week you can give"
    ),
    no_input: bool = typer.Option(
        False, "--no-input", help="Ask nothing; use the options given and your saved profile"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """New here? Answer four questions and get organizations that fit you, plus next steps."""
    toolkit = _toolkit()
    saved = toolkit.progress.profile()
    technologies = split_csv(tech) or None
    topics = onboarding.parse_topics(interests) if interests else None
    interactive = not no_input and output == Output.rich and _stdin_is_interactive()
    if not interactive and not (github or technologies or topics or hours or saved):
        if output == Output.json:
            _emit({"needs_input": True, "questions": onboarding.questions()}, output)
            return
        console.print(
            "start asks four questions, so run it in a terminal. Or give the answers as "
            "options:\n  [cyan]git-into-gsoc start --github YOUR_USERNAME --tech python "
            "--interests science --hours 10[/cyan]\n"
            "[dim]Replace YOUR_USERNAME with yours. Every option can be left out.[/dim]"
        )
        return
    if interactive:
        technologies, topics, hours = _interview(
            toolkit,
            saved,
            ask_github=github is None,
            technologies=technologies,
            topics=topics,
            hours=hours,
        )
    data = onboarding.first_run(
        toolkit,
        github=github,
        technologies=technologies,
        interests=topics,
        hours_per_week=hours,
    )
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    _render_matches(data)
    if interactive and data["organizations"]:
        answer = _ask("Shortlist any of these now? Type their numbers, or press Enter to skip")
        names = [org["name"] for org in data["organizations"]]
        picks = [
            names[int(p) - 1] for p in split_csv(answer) if p.isdigit() and 0 < int(p) <= len(names)
        ]
        if picks:
            data = _markup_safe(onboarding.shortlist(toolkit, data, picks))
    _render_next_steps(data)


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
    data = _markup_safe(data)
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
    console.print("\n[bold]Good habits[/bold]")
    for habit in data.get("contributor_habits") or []:
        console.print(f"• {habit}")
    if data.get("profile_saved"):
        console.print("\n[dim]Next: git-into-gsoc next[/dim]")
    else:
        console.print(
            "\n[dim]Next: git-into-gsoc start (four quick questions), then git-into-gsoc next[/dim]"
        )


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
    limit: int = typer.Option(10, "--limit", "-n", min=1, help="How many organizations to show"),
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
        check_posts=True,
    )
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    catalog = data["catalog"]
    matched = data.get("matched_on") or {}
    if matched.get("from_profile"):
        console.print(
            "Matching your saved profile: "
            + "; ".join(", ".join(matched[k]) for k in ("technologies", "topics") if matched[k])
            + ". Pass --tech or --topics to search differently."
        )
    for note in data.get("read_as") or []:
        console.print(f"[dim]{note}[/dim]")
    caption = (
        catalog["note"] + " Years: how many years it took part. Projects: contributor "
        "projects accepted per year ('24:5 means 5 in 2024)."
    )
    table = Table(title="GSoC organizations", caption=caption, show_lines=False)
    table.add_column("Fit", no_wrap=True)
    table.add_column("Organization", overflow="fold", max_width=28)
    table.add_column("Why it fits", overflow="fold")
    table.add_column("Years", justify="right")
    table.add_column("Projects", no_wrap=True)
    for org in data["organizations"]:
        why = [r for r in org.get("match_reasons") or [] if r.startswith(_FIT_PREFIXES)]
        status = (org.get("participation") or {}).get("status")
        table.add_row(
            _fit_cell(org.get("fit")),
            org["name"] + (" [red](sitting out)[/red]" if status == "not_taking_part" else ""),
            "; ".join(why) or "(no specific match)",
            str(len(org.get("years_active") or [])),
            _trend(org.get("projects_by_year") or {}),
        )
    console.print(table)
    if not data["organizations"]:
        hint = data.get("hint") or "Try broader --tech or --topics."
        console.print(f"[yellow]No organizations matched.[/yellow] {hint}")
        return
    _print_org_evidence(data["organizations"][:3])
    _print_sharpen(data.get("sharpen") or [])
    for note in data.get("notes") or []:
        console.print(f"[yellow]![/yellow] {note}")
    if data.get("how_ranked"):
        console.print(f"[dim]{data['how_ranked']}[/dim]")
    console.print(
        '[dim]Next: git-into-gsoc org "<name>" for ideas page, channels, and repos.[/dim]'
    )


_FIT_STYLE = {"strong": "green", "good": "cyan", "partial": "yellow"}


def _print_sharpen(tips: list[dict[str, Any]]) -> None:
    """One line per vague word: how broad it is, and narrower words to try."""
    for tip in tips:
        options = ", ".join(f"{s['words']} ({s['organizations']})" for s in tip["suggest"])
        if tip["kind"] == "interest":
            console.print(
                f"[cyan]Tip:[/cyan] '{tip['word']}' matches {tip['matches']} organizations. "
                f"A narrower interest finds closer fits: {options}."
            )
        else:
            console.print(
                f"[cyan]Tip:[/cyan] {tip['matches']} organizations use '{tip['word']}'. "
                f"Adding an interest narrows the list; theirs include: {options}."
            )


def _fit_cell(fit: str | None) -> str:
    return f"[{_FIT_STYLE[fit]}]{fit}[/]" if fit in _FIT_STYLE else ""


def _print_org_evidence(orgs: list[dict[str, Any]]) -> None:
    """Where each claim about the top organizations comes from, and what to watch for."""
    for org in orgs:
        lines = [*(org.get("evidence") or [])[:3], *(org.get("readiness") or [])[:2]]
        cautions = list(org.get("caveats") or [])[:2]
        learn = org.get("skills_to_learn") or []
        if not (lines or cautions):
            continue
        console.print(f"\n[bold]{org['name']}[/bold]")
        for line in lines:
            console.print(f"  • {line}")
        if learn:
            console.print(f"  • Its ideas also ask for: {', '.join(learn)}")
        for line in cautions:
            console.print(f"  [yellow]![/yellow] {line}")


@app.command("org", rich_help_panel="Find an organization")
def org_cmd(
    name: str = typer.Argument(
        ..., help="Organization name or a word of it, for example SymPy or mailman"
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
        _emit_or_fail(data, output)
        return
    data = _markup_safe(data)
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
        lines.append(f"{_channel_label(str(channel['kind']))}: {channel['value']}")
    lines.append(
        f"Tech: {', '.join(org.get('technologies') or [])}  |  "
        f"Topics: {', '.join(org.get('topics') or [])}"
    )
    lines.append(f"Projects per year: {_trend(org.get('projects_by_year') or {})}")
    year = data["catalog"]["year"]
    if org.get("official"):
        title = f"{year} · accepted"
    else:
        last = max(org.get("years_active") or [0]) or "an earlier year"
        title = f"not in the {year} list · last took part in {last}"
        lines.append(
            f"[yellow]Not accepted in {year}. "
            "Check its website to see whether it plans to apply again.[/yellow]"
        )
    console.print(Panel(Text.from_markup("\n".join(lines)), title=title))
    _print_gsoc_posts(data.get("gsoc_posts") or {})
    if org.get("recent_projects"):
        table = Table(title="Recent accepted projects (for scope reference, never copy)")
        table.add_column("Year")
        table.add_column("Title", overflow="fold")
        for project in org["recent_projects"]:
            table.add_row(str(project["year"]), project["title"])
        console.print(table)
    console.print(
        f'[dim]Next: git-into-gsoc ideas "{org["name"]}" to read its project ideas, then '
        f'git-into-gsoc repos "{org["name"]}" to pick a repository.[/dim]'
    )


# The GSoC API's channel kinds, as a person would say them.
_CHANNEL_LABELS = {
    "chat": "Chat",
    "mailingList": "Mailing list",
    "email": "Email",
    "twitter": "X (Twitter)",
    "blog": "Blog",
    "forum": "Forum",
    "irc": "IRC",
}


def _channel_label(kind: str) -> str:
    """'mailingList' reads as 'Mailing list'; an unknown kind is split into words."""
    if kind in _CHANNEL_LABELS:
        return _CHANNEL_LABELS[kind]
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", kind).replace("_", " ").strip()
    return words[:1].upper() + words[1:].lower() if words else "Contact"


_POST_STATUS = {
    "not_taking_part": "[bold red]says it will not take part[/bold red]",
    "undecided": "[yellow]says it has not decided yet[/yellow]",
}


def _print_gsoc_posts(found: dict[str, Any]) -> None:
    posts = found.get("posts") or []
    if not posts:
        return
    console.print(f"\n[bold]Posts about GSoC {found.get('year')} in its repositories[/bold]")
    for post in posts:
        status = _POST_STATUS.get(post["status"], "")
        if post.get("source") == "wiki":
            console.print(f"  Project wiki: {escape(post['title'])}  {status}")
            console.print(f"  [dim]{post['url']}  (wikis can often be edited by anyone)[/dim]")
            continue
        who = "a maintainer" if post.get("by_maintainer") else f"@{post.get('author')}"
        console.print(f"  {post['created_at']}  {escape(post['title'])}  {status}")
        console.print(f"  [dim]{post['url']}  (by {escape(who)}, {post['state']})[/dim]")


@app.command("projects", rich_help_panel="Find an organization")
def projects_cmd(
    query: str | None = typer.Argument(None, help="Keywords, for example 'graph neural networks'"),
    org: str | None = typer.Option(None, "--org", help="Limit to one organization"),
    since: int | None = typer.Option(None, "--since", help="Earliest program year"),
    limit: int = typer.Option(15, "--limit", "-n", min=1, help="How many projects to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Search past accepted GSoC projects to judge scope and find organizations."""
    data = _toolkit().past_projects(query, org=org, since=since, limit=limit)
    if output == Output.json or not data.get("found", True):
        _emit_or_fail(data, output)
        return
    data = _markup_safe(data)
    table = Table(title="Past accepted projects", caption=data["note"])
    table.add_column("Year")
    table.add_column("Organization", overflow="fold", max_width=26)
    table.add_column("Project", overflow="fold")
    for project in data["projects"]:
        table.add_row(str(project["year"]), project["org"], project["title"])
    console.print(table)


@app.command("ideas", rich_help_panel="Find an organization")
def ideas_cmd(
    org: str = typer.Argument(..., help="GSoC organization name, for example SymPy"),
    skills: str | None = typer.Option(
        None, "--skills", "-s", help="Skills to match, comma-separated (default: your profile)"
    ),
    size: str | None = typer.Option(None, "--size", help="small, medium, or large"),
    difficulty: str | None = typer.Option(None, "--difficulty", help="easy, medium, or hard"),
    limit: int = typer.Option(20, "--limit", "-n", min=1, help="How many ideas to show"),
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
        _emit_or_fail(data, output)
        return
    data = _markup_safe(data)
    lines = [f"[bold]{escape(data['org'])}[/bold]", f"Ideas page: {data['ideas_url']}"]
    if data.get("fetched_url") and data["fetched_url"] != data["ideas_url"]:
        lines.append(f"[dim]Read as: {data['fetched_url']}[/dim]")
    lines.append(escape(data["note"]))
    for sentence in data.get("ai_policy") or []:
        lines.append(f"[yellow]AI policy:[/yellow] {escape(sentence)}")
    console.print(Panel(Text.from_markup("\n".join(lines)), title=f"Ideas: {data['layout']}"))
    if data.get("hours_note"):
        console.print(f"[yellow]![/yellow] {escape(data['hours_note'])}")
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
            hours = (
                f"{idea['hours']}h"
                if idea.get("hours")
                else (idea.get("size") or (idea.get("size_raw") or "")[:16])
            )
            if idea.get("too_big_for_your_hours"):
                hours = f"[yellow]{hours} too big[/yellow]"
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
    org: str = typer.Argument(..., help="GSoC organization name, for example SymPy"),
    years: int = typer.Option(3, "--years", help="How many archived years to read"),
    limit: int = typer.Option(25, "--limit", "-n", min=1, help="How many mentors to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Who has mentored this organization's completed projects, and which repositories they touched."""
    data = _toolkit().org_mentors(org, years=years, limit=limit)
    if output == Output.json or not data.get("found"):
        _emit_or_fail(data, output)
        return
    data = _markup_safe(data)
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
    limit: int = typer.Option(10, "--limit", "-n", min=1, help="How many repositories to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Rank an organization's repositories by ideas-page mentions, beginner issues, and activity."""
    data = _toolkit().discover_repos(org, language=language, limit=limit)
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    caption = (
        "Ideas page read: repos it names are boosted."
        if data["ideas_page_read"]
        else "Ideas page not readable; ranking uses activity and beginner issues."
    )
    if data.get("note"):
        console.print(f"[yellow]{data['note']}[/yellow]")
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
        _toolkit().progress.track_repo((data["health"] or data)["full_name"])
        data["tracked"] = True
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    if data.get("mirror_of"):
        console.print(Panel.fit(data["recommendation"], title=f"{data['full_name']}: a mirror"))
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


def _ci_environment_lines(env: dict[str, Any]) -> list[str]:
    """One line per runtime, plus services and runners, as CI sets them up."""
    lines = [
        f"CI uses {r['name']} {', '.join(r['versions'])}"
        + (f"; most jobs use {r['most_used']}" if r.get("most_used") else "")
        + f"  [dim]({r['source']})[/dim]"
        for r in env.get("runtimes") or []
    ]
    services = env.get("services") or []
    if services:
        names = ", ".join(
            f"{s['name']} ({s['image']})" if s.get("image") else s["name"] for s in services
        )
        lines.append(f"CI starts these services for the tests: {escape(names)}")
    if env.get("runners"):
        lines.append("CI runs on these systems: " + escape(", ".join(env["runners"])))
    return lines


@app.command("orient", rich_help_panel="Pick a repository and an issue")
def orient_cmd(
    full_name: str,
    codetour: Path | None = typer.Option(
        None, "--codetour", help="Also write a CodeTour file (VS Code) for the reading plan here"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Get your bearings in a repository: code map, entry points, test command, who writes the code, rules."""
    data = _toolkit().orient_repo(full_name, codetour=codetour is not None)
    if codetour is not None:
        codetour.parent.mkdir(parents=True, exist_ok=True)
        codetour.write_text(json.dumps(data["codetour"], indent=2) + "\n", encoding="utf-8")
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
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
    ci_lines = (
        [f"{escape(t['command'])}  [dim]({t['source']})[/dim]" for t in data["test_commands"]]
        + _ci_environment_lines(data.get("ci_environment") or {})
        + [escape(h) for h in data["setup_hints"]]
    )
    if ci_lines:
        # Terms a first-time contributor may not know, said once where they first appear.
        ci_lines.insert(0, "[dim]CI is the set of checks GitHub runs on every pull request.[/dim]")
        if any("tox" in str(t.get("command")) for t in data["test_commands"]):
            ci_lines.append(
                "[dim]tox runs the tests in fresh, separate Python environments: pip install "
                "tox, then run the same tox command yourself.[/dim]"
            )
    section("How CI runs the tests", ci_lines)
    docs = data["docs"]
    section(
        "Read first",
        list(
            dict.fromkeys(
                p
                for p in (
                    docs.get("readme"),
                    docs.get("contributing"),
                    *docs.get("architecture", []),
                )
                if p
            )
        ),
    )
    people = data["maintainers"]
    section(
        # Commit authors, not mergers: a merge through GitHub records GitHub itself as the
        # committer, so the commits cannot say who pressed the button.
        f"Who writes the code ({people['commits_90d']} commits in 90 days, by author)",
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
            "Sign-off required (git commit -s adds a 'Signed-off-by' line saying you may "
            "submit the change): " + "; ".join(rules["dco"]["evidence"])
        )
    if rules["cla"]["required"]:
        rule_lines.append("CLA required: " + "; ".join(rules["cla"]["evidence"]))
    if rules["conventional_commits"]["expected"]:
        rule_lines.append(
            "Commit style type(scope): subject expected: "
            + "; ".join(rules["conventional_commits"]["evidence"])
        )
    if (rules.get("changelog") or {}).get("expected"):
        rule_lines.append(
            "Add a changelog or news entry: " + "; ".join(rules["changelog"]["evidence"])
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
    "not_open": "red",
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
    org: str | None = typer.Option(
        None,
        "--org",
        help="GSoC organization name (also searches projects its ideas page names) or GitHub login",
    ),
    repo: str | None = typer.Option(None, "--repo", help="One repository as owner/name"),
    label: str | None = typer.Option(
        None, "--label", help="Label to require (default: good first issue, then help wanted)"
    ),
    scope: Scope = typer.Option(
        Scope.gsoc,
        "--scope",
        help="gsoc: only repositories of GSoC organizations; all: any repository",
    ),
    limit: int = typer.Option(10, "--limit", "-n", min=1, help="How many issues to show"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Find beginner issues that still look free: no pull request, assignee, or recent claim."""
    data = _toolkit().find_issues(
        language=language, org=org, repo=repo, label=label, scope=scope.value, max_results=limit
    )
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    if not data["issues"]:
        console.print(f"No free beginner issues found. {data['note']}")
        console.print("[bold]Try next[/bold]")
        for step in data["next_steps"]:
            console.print(f"  • {step}")
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
    data = _markup_safe(data)
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
        gitlab = "/merge_requests/" in str(pr.get("url") or "")
        ref = (
            f"MR !{pr['number']}"
            if gitlab
            else "PR " + pull_ref(pr["number"], pr.get("url"), str(data["repo"]))
        )
        via = ", linked in a comment" if pr.get("via_comment") else ""
        lines.append(f"{ref} ({pr['state']}) by @{pr['author']}{via}")
    for claim in assessment["claims"][:5]:
        granted = ", approved by a maintainer" if claim["granted"] else ""
        lines.append(f"Claim: @{claim['login']}, last active {claim['days_ago']}d ago{granted}")
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
    experience: str | None = typer.Option(
        None,
        "--experience",
        "-e",
        help="Your open source experience: new, some, or experienced. With --github and no "
        "--experience, it is read from your merged pull requests.",
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Show or save your profile. recommend and next use it when you give no flags."""
    toolkit = _toolkit()
    if any([github, tech, interests, hours is not None, tz, experience]):
        data = toolkit.save_profile(
            github=github,
            technologies=split_csv(tech) or None,
            interests=split_csv(interests) or None,
            hours_per_week=hours,
            timezone=tz,
            experience=experience,
        )
    else:
        data = toolkit.progress.profile()
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    if not data:
        console.print(
            "No profile saved yet. The quickest way is four questions:\n"
            "  git-into-gsoc start\n"
            "Or set it directly:\n"
            "  git-into-gsoc profile --github YOUR_USERNAME --tech python --interests science "
            "--hours 10"
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
        ("experience", "Open source experience"),
    ):
        value = data.get(key)
        if value:
            lines.append(f"{label}: {', '.join(value) if isinstance(value, list) else value}")
    inferred = data.get("experience_inferred") or {}
    if inferred.get("level"):
        lines.append(
            f"Open source experience: {inferred['level']} (from {inferred['from']}; "
            "set it with --experience)"
        )
    console.print(Panel(Text.from_markup("\n".join(lines)), title="Your profile"))
    if data.get("warning"):
        console.print(f"[yellow]![/yellow] {data['warning']}")
    if data.get("hours_note"):
        console.print(f"[yellow]![/yellow] {data['hours_note']}")


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
    data = _markup_safe(data)
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
        kind = "similar" if data.get("similar_shares_title_words") else "recent"
        table = Table(title=f"How {kind} '{data['similar_label']}' issues were fixed here")
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


@app.command("diagnose", rich_help_panel="Contribute and apply")
def diagnose_cmd(
    file: str = typer.Argument(
        ..., help="A file holding the failing output, or - to read it from standard input"
    ),
    repo: str | None = typer.Option(
        None, "--repo", help="owner/repo, to compare with the environment its CI sets up"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Name the likely cause of a failed setup or test run, and what to try next."""
    # A file goes through the same reader as proposals: Windows PowerShell 5.1
    # writes `pytest > log.txt` as UTF-16, which plain UTF-8 reading turns to noise.
    text = sys.stdin.read() if file == "-" else _read_document(Path(file))
    data = _toolkit().diagnose(text, repo=repo)
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    console.print(f"[bold]{data['summary']}[/bold]")
    for cause in data["causes"]:
        console.print(
            f"\n[yellow]{cause['id'].replace('_', ' ')}[/yellow]  line {cause['line']}: [dim]{cause['quote']}[/dim]"
        )
        console.print(f"  {cause['means']}")
        for step in cause["try"]:
            console.print(f"  - {step}")
    if data["ci"]:
        console.print("\n[bold]What CI sets up[/bold]")
        for note in data["ci"]:
            console.print(f"  {note}")


@app.command("pr-check", rich_help_panel="Contribute and apply")
def pr_check_cmd(
    ref: str = typer.Argument(..., help="owner/repo#123, a pull request URL, or owner/repo"),
    number: int | None = typer.Argument(None, help="Pull request number if REF is owner/repo"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Check your pull request against the repository's own rules before a reviewer does."""
    data = _toolkit().pr_check(ref, number)
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    table = Table(title=f"Pull request check: {data['ref']} ({data['lines_changed']} lines)")
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", overflow="fold")
    for finding in data["findings"]:
        table.add_row(_FINDING_MARK[finding["status"]], finding["title"], finding["detail"])
    console.print(table)
    console.print(f"\n[bold]{data['verdict']}[/bold]")
    if data["what_happens_next"]:
        console.print("\n[bold]Before it can merge[/bold]")
        for gate in data["what_happens_next"]:
            console.print(f"  - {gate}")
    console.print(f"\n[dim]{data['note']}[/dim]")


@app.command("draft", rich_help_panel="Contribute and apply")
def draft_cmd(
    kind: str = typer.Argument(
        ..., help="intro, question, claim, pr, review-reply, status, or final"
    ),
    org: str | None = typer.Option(None, "--org", help="GSoC org name, for channels"),
    repo: str | None = typer.Option(None, "--repo", help="owner/repo, for its claim and PR rules"),
    issue: str | None = typer.Option(None, "--issue", help="owner/repo#N, for a claim or PR draft"),
    check: Path | None = typer.Option(
        None,
        "--check",
        help="Check a message you wrote (a text file) against this kind's rules instead",
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """A skeleton for an intro, question, claim comment, PR description, review reply, or report."""
    if check is not None:
        report = _toolkit().check_message(kind, _read_document(check))
        if output == Output.json:
            _emit(report, output)
            return
        report = _markup_safe(report)
        table = Table(title=f"Message check: {kind} ({report['words']} words)")
        table.add_column("")
        table.add_column("Check")
        table.add_column("Detail", overflow="fold")
        for finding in report["findings"]:
            detail = finding["detail"] + (
                f"\n[dim]{finding['source']}[/dim]" if finding["source"] else ""
            )
            table.add_row(_FINDING_MARK[finding["status"]], finding["title"], detail)
        if report["findings"]:
            console.print(table)
        console.print(f"[bold]{report['verdict']}[/bold]")
        return
    data = _toolkit().draft(kind, org=org, repo=repo, issue=issue)
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    if data.get("warning"):  # before the draft, so nobody copies it first
        console.print(f"[bold yellow]! {escape(data['warning'])}[/bold yellow]")
    console.print(Panel(Text.from_markup(data["template"]), title=f"Draft: {data['kind']}"))
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
    experience: str | None = typer.Option(
        None,
        "--experience",
        "-e",
        help="Your open source experience: new, some, or experienced (default: your profile)",
    ),
    hours: int | None = typer.Option(
        None, "--hours", min=1, help="Hours a week you can give (default: your profile)"
    ),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Suggest organizations, ideas, starter issues, and a learning path, with evidence."""
    data = _toolkit().recommend_path(
        username=github,
        technologies=split_csv(tech) or None,
        interests=split_csv(interests) or None,
        experience=experience,
        hours_per_week=hours,
    )
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
    console.print(Panel.fit(data["program"]["note"], title="Recommendations"))
    if data.get("profile"):
        console.print(
            f"Profile: [bold]{data['profile'].get('login')}[/bold] "
            f"top={data['profile'].get('top_language')}"
        )
    used = ", ".join(data["technologies_used"] + data["interests_used"]) or "none"
    level = data.get("experience") or {}
    about = [f"Matching on: {used} ({data['profile_source']})"]
    if level.get("level"):
        about.append(f"experience: {level['level']} ({level.get('from') or ''})")
    if data.get("hours_per_week"):
        about.append(f"{data['hours_per_week']} hours a week")
    console.print("; ".join(about))
    for note in data.get("read_as") or []:
        console.print(f"[dim]{note}[/dim]")
    if data.get("hours_note"):
        console.print(f"[yellow]![/yellow] {data['hours_note']}")
    table = Table(title="Organizations")
    table.add_column("Fit", no_wrap=True)
    table.add_column("Organization", overflow="fold", max_width=28)
    table.add_column("Why it fits", overflow="fold")
    for org in data["recommended_orgs"][:8]:
        why = [r for r in org.get("match_reasons") or [] if r.startswith(_FIT_PREFIXES)]
        status = (org.get("participation") or {}).get("status")
        name = org["name"] + (" [red](sitting out)[/red]" if status == "not_taking_part" else "")
        table.add_row(_fit_cell(org.get("fit")), name, "; ".join(why[:4]))
    console.print(table)
    _print_org_evidence(data["recommended_orgs"][:3])
    _print_sharpen(data.get("sharpen") or [])
    for note in data.get("notes") or []:
        console.print(f"[yellow]![/yellow] {note}")
    if data.get("ideas_that_fit"):
        console.print("\n[bold]Ideas that fit you[/bold]")
        for group in data["ideas_that_fit"]:
            console.print(f"[bold]{group['org']}[/bold] [dim]{group['note']}[/dim]")
            for idea in group["ideas"]:
                parts = []
                if idea["you_have"]:
                    parts.append("you know " + ", ".join(idea["you_have"]))
                if idea["matches_interests"]:
                    parts.append("about " + ", ".join(idea["matches_interests"]))
                if idea["you_would_learn"]:
                    parts.append("you would learn " + ", ".join(idea["you_would_learn"]))
                parts += idea["stated"]
                console.print(f"  • {idea['title']} [dim]({'; '.join(parts)})[/dim]")
    if data["starter_issues"]:
        caption = f"From {data['starter_issue_scope']}." if data.get("starter_issue_scope") else ""
        if data.get("starter_issues_hidden"):
            caption += (
                f" Left out {data['starter_issues_hidden']} that someone already claimed or "
                "is working on."
            )
        if data.get("starter_issues_skipped"):
            caption += (
                f" Skipped {data['starter_issues_skipped']} that are announcements, trackers, "
                "years old, in retired repositories, or need skills you did not list."
            )
        issues = Table(title="Starter issues still open to newcomers", caption=caption.strip())
        issues.add_column("Status")
        issues.add_column("Issue", overflow="fold")
        issues.add_column("Title", overflow="fold")
        issues.add_column("Fits you", overflow="fold")
        for issue in data["starter_issues"]:
            status = issue["availability"]
            issues.add_row(
                f"[{_STATUS_STYLE.get(status, '')}]{status}[/]",
                f"{issue['repo']}#{issue['number']}",
                issue["title"],
                "; ".join(issue.get("fits_you") or []),
            )
        console.print(issues)
    elif data.get("starter_issue_error"):
        console.print(
            f"[yellow]Starter issues unavailable:[/yellow] {data['starter_issue_error']['error']}"
        )
    elif data.get("starter_issue_note"):
        console.print(f"[dim]{data['starter_issue_note']}[/dim]")
    if data.get("learning_path"):
        console.print("\n[bold]Your path from here[/bold]")
        for step in data["learning_path"]:
            console.print(f"  {step['n']}. {step['step']}")
            console.print(f"     [dim]{step['why']}[/dim]")
            if step.get("command"):
                console.print(f"     → {step['command']}")
    console.print(f"\n[dim]{data['evidence_note']}[/dim]")


_FINDING_MARK = {"pass": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]✗[/red]"}
_STRENGTH_STYLE = {"strong": "green", "developing": "cyan", "starting": "yellow", "none": "red"}


@app.command("contributions", rich_help_panel="Contribute and apply")
def contributions_cmd(
    github: str | None = typer.Option(
        None, "--github", "-g", help="Your GitHub username (default: the one saved by `profile`)"
    ),
    org: str | None = typer.Option(None, "--org", help="GSoC org name or GitHub org"),
    repo: str | None = typer.Option(None, "--repo", help="owner/repo to scope to"),
    output: Output = OUTPUT_OPTION,
) -> None:
    """Collect your PRs, issues, and reviews in an org's repos as proposal evidence."""
    if not org and not repo:
        raise typer.BadParameter("Pass --org or --repo")
    toolkit = _toolkit()
    username = github or str(toolkit.progress.profile().get("github") or "")
    if not username:
        raise InputError(
            "No GitHub username given.",
            hint="Pass --github YOUR_USERNAME, or save it once with "
            "`git-into-gsoc profile --github YOUR_USERNAME`.",
        )
    data = toolkit.contribution_evidence(username, org=org, repo=repo)
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
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
    second: Path | None = typer.Argument(
        None, hidden=True, help="The draft, when typed as `proposal check FILE`"
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
    # `proposal check draft.md` reads naturally; accept it as `proposal draft.md`.
    if file is not None and str(file) == "check" and not file.exists():
        if second is None:
            raise InputError(
                "No draft given to check",
                hint="Pass its file name: git-into-gsoc proposal draft.md",
            )
        file = second
    elif second is not None:
        raise InputError(
            "Only one draft can be checked at a time",
            hint="Pass one file name: git-into-gsoc proposal draft.md",
        )
    if file is None:
        data = _toolkit().proposal_help()
        if output == Output.json:
            _emit(data, output)
            return
        data = _markup_safe(data)
        console.print("[bold]Checklist[/bold]")
        for item in data["checklist"]:
            console.print(f"☐ {item['title']}: {item['description']}")
        console.print("\n[bold]Suggested structure[/bold]")
        for i, section in enumerate(data["structure"], 1):
            console.print(f"  {i}. {section}")
        console.print("\n[dim]Check a draft: git-into-gsoc proposal draft.md --github you[/dim]")
        return
    text = _read_document(file)
    ideas_text = _read_document(ideas_file) if ideas_file else None
    report = _toolkit().check_proposal(text, github=github, verify=verify, ideas_text=ideas_text)
    if output == Output.json:
        _emit(report, output)
        return
    report = _markup_safe(report)
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
        who = f", opened by @{link['author']}" if link["author"] else ""
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
    if output == Output.json:
        _emit(data, output)
        return
    if action != "summary":
        console.print("[green]Saved.[/green]")
    _render_progress(_markup_safe(store.summary()))


def _render_progress(data: dict[str, Any]) -> None:
    """The saved journey as a person reads it: phases first, then what they follow."""
    console.print(
        f"[bold]GSoC {data['target_year']} progress[/bold]: {data['completion']} phases done"
    )
    for phase, done in data["phases"].items():
        mark = "[green]✓[/green]" if done else "[dim]·[/dim]"
        flag = "  [cyan](next)[/cyan]" if phase == data["next_phase"] else ""
        console.print(f"  {mark} {phase}{flag}")
    for title, key in (
        ("Shortlisted organizations", "shortlisted_orgs"),
        ("Tracked repositories", "tracked_repos"),
        ("Tracked issues", "tracked_issues"),
    ):
        items = data[key]
        console.print(f"\n[bold]{title}[/bold] ({len(items)})")
        for item in items:
            console.print(f"  {item}")
        if not items:
            console.print("  [dim]none yet[/dim]")
    days = data["last_log_days_ago"]
    when = {None: "", 0: ", the last one today", 1: ", the last one yesterday"}.get(
        days, f", the last one {days} days ago"
    )
    console.print(f"\nWeekly notes: {data['log_entries']}{when}")
    if data["next_phase"]:
        console.print(
            f"[dim]When {data['next_phase']} is done: git-into-gsoc progress complete_phase "
            f"--phase {data['next_phase']}. For what to do now: git-into-gsoc next[/dim]"
        )


@app.command("journey", rich_help_panel="Start here")
def journey_cmd(output: Output = OUTPUT_OPTION) -> None:
    """Show every phase of the journey with its goal and actions."""
    data = journey_overview()
    if output == Output.json:
        _emit(data, output)
        return
    data = _markup_safe(data)
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
    data = _markup_safe(data)
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
    if data.get("hours_note"):
        console.print(f"\n[yellow]![/yellow] {escape(data['hours_note'])}")
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
    if data.get("open_pull_requests"):
        console.print("\n[bold]Your open pull requests[/bold]")
        for pr in data["open_pull_requests"]:
            mark = (
                "[yellow]needs you[/yellow]"
                if pr["status"] == "needs_you"
                else "[dim]waiting[/dim]  "
            )
            console.print(f"  {mark} {pr['ref']}  {escape(pr['summary'])}")
            for extra in pr.get("reasons", [])[1:]:
                console.print(f"           [dim]also: {escape(extra)}[/dim]")
    if data.get("merged_pull_requests"):
        console.print("\n[bold]Merged since your last check[/bold]")
        for pr in data["merged_pull_requests"]:
            console.print(f"  [green]✓[/green] {pr['ref']}  {escape(pr['title'])}", highlight=False)
        if data.get("first_merge"):
            console.print(
                "  [bold green]Your first merged pull request in someone else's project.[/] "
                "That is the hardest step, and it is done. Maintainers will remember a "
                "contributor who finished one."
            )
            console.print(
                "  [dim]If git-into-gsoc helped, tell a friend who is starting out, or tell "
                "us what worked: git-into-gsoc feedback[/dim]"
            )
    news = [p for p in data.get("org_posts") or [] if p["status"] != "mentions"] + [
        p for p in data.get("org_posts") or [] if p["status"] == "mentions"
    ]
    if news:
        console.print("\n[bold]News from organizations on your shortlist[/bold]")
        for post in news[:4]:
            status = _POST_STATUS.get(post["status"], "")
            console.print(f"  {escape(post['org'])}: {escape(post['title'])}  {status}")
            console.print(f"  [dim]{post['url']}[/dim]")
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
    limit: int = typer.Option(5, "--limit", "-n", min=1, help="How many past notes to show"),
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
    # The closest root wins, so a home folder inside the current folder still reads ~/.
    roots = [(r, p) for r, p in ((project, "./"), (home, "~/")) if r is not None]
    for root, prefix in sorted(roots, key=lambda rp: len(rp[0].parts), reverse=True):
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
            "antigravity, windsurf, vscode (also Copilot CLI), or all. "
            "Default: every assistant detected on this machine."
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
    copied = [
        c
        for c in plan.changes
        if c.kind == "skill" and c.action in {"created", "updated", "unchanged"}
    ]
    if not plan.assistants and not (dry_run or remove) and not plan.manual and copied:
        # A blind beginner install (2026-10-22) read a yellow "No AI assistant detected",
        # a table of skill folders, and an "MCP command" line as errors. With no
        # assistant there is nothing to connect, so say only what happened.
        where = _short_path(copied[0].path, plan.home, plan.project)
        console.print(
            f"No AI assistant was found, so only the skill was copied to {where}. That is fine: "
            "every feature works in the terminal. Try [cyan]git-into-gsoc start[/cyan]. If you "
            "use an assistant this did not find, name it, for example "
            "[cyan]git-into-gsoc setup --assistant claude-code[/cyan]."
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
    console.print(f"MCP command: {' '.join(plan.command)}", soft_wrap=True)
    for step in plan.manual:
        console.print(f"  [yellow]manual:[/yellow] {step}", soft_wrap=True)
    if dry_run or remove or not plan.changes:
        return
    ready = {"created", "updated", "unchanged"}
    mcp_ready = any(
        c.kind == "mcp" and c.action in ready and c.note != "no MCP support" for c in plan.changes
    )
    skill_ready = any(c.kind == "skill" and c.action in ready for c in plan.changes)
    if not plan.assistants:
        console.print(
            "\nNo AI assistant was found, so only the skill was copied. That is fine: every "
            "feature works in the terminal. Try [cyan]git-into-gsoc start[/cyan]. After you "
            "install an assistant, run [cyan]git-into-gsoc setup[/cyan] again."
        )
    elif mcp_ready:
        console.print(
            "\nRestart your assistant, then ask it in your own words, for example: "
            '"I want to do Google Summer of Code. I know Python and like science. '
            'Where do I start?"'
        )
    elif skill_ready:
        console.print(
            "\nThe skill is ready, but the MCP server still needs the manual step above. "
            "Until then your assistant can run git-into-gsoc commands in a terminal."
        )
    else:
        console.print("\nNothing was set up. Follow the manual steps above, then run `doctor`.")


def _writable(create: Any, location: Any) -> str:
    """A folder the tool writes to, or why it cannot, without stopping `doctor`."""
    try:
        return str(create())
    except OSError as exc:
        return (
            f"{location()} [red]cannot be written[/red] ({exc.strerror or exc}). "
            "Set GIG_CACHE_DIR and GIG_DATA_DIR to folders you can write to."
        )


@app.command("doctor", rich_help_panel="Maintenance")
def doctor_cmd() -> None:
    """Check your setup: version, GitHub token, data locations, API access, skill, and MCP."""
    from git_into_gsoc.config import (
        cache_dir,
        cache_location,
        data_dir,
        data_location,
        get_settings,
    )
    from git_into_gsoc.install.clients import (
        ASSISTANTS,
        env_home,
        installed_plugin,
        installed_skills,
        registrations,
    )
    from git_into_gsoc.install.skill import InstallError, is_current, skill_source

    settings = get_settings()
    source = settings.github_token_source()
    console.print(f"git-into-gsoc {__version__}  (Python {sys.version.split()[0]})")
    console.print(f"cache: {_writable(cache_dir, cache_location)}", soft_wrap=True)
    console.print(f"data:  {_writable(data_dir, data_location)}", soft_wrap=True)
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
    source_dir: Path | None = None
    try:
        source_dir = skill_source()
        console.print(f"skill source: {source_dir}", soft_wrap=True)
    except InstallError as exc:
        console.print(f"[red]skill source:[/red] {exc}")
    home, project = env_home(), Path.cwd()
    skills = installed_skills(home, project)
    servers = registrations(home, project)
    plugins = [p for a in ASSISTANTS.values() if (p := installed_plugin(a, home))]
    if plugins:
        console.print("plugin installed: " + ", ".join(plugins))
    if skills:
        # The shared folder can hold a user copy and a project copy; name it once.
        labels = dict.fromkeys(label for label, _ in skills)
        console.print("skill installed for: " + ", ".join(labels))
        stale = [p for _, p in skills if source_dir and not is_current(source_dir, p)]
        if stale:
            console.print(
                "[yellow]older skill copies:[/yellow] "
                + ", ".join(_short_path(p, home, project) for p in stale)
                + " (run `git-into-gsoc setup` to refresh them)"
            )
    elif not plugins:
        console.print("skill installed for: [yellow]none[/yellow] (run `git-into-gsoc setup`)")
    if servers:
        console.print(
            "MCP registered in: "
            + ", ".join(_short_path(path, home, project) for _, path, _ in servers),
            soft_wrap=True,
        )
        for _, path, entry in servers:
            problem = _command_problem(entry)
            if problem:
                console.print(
                    f"[red]{_short_path(path, home, project)}:[/red] {problem} "
                    "(run `git-into-gsoc setup` to point it at this installation)"
                )
    elif not plugins:
        # Yellow "nowhere yet" reads as an error to someone who only uses the terminal,
        # the same pattern a blind beginner install flagged in `setup` (2026-10-22).
        console.print(
            "AI assistants connected: none yet. That is fine in a terminal; if you use "
            "one, run `git-into-gsoc setup`."
        )


def _command_problem(entry: dict[str, object]) -> str | None:
    """Why a registered server would fail to start, when that can be seen without running it."""
    from git_into_gsoc.programs import find_program

    command = entry.get("command")
    if not isinstance(command, str) or not command:
        return "no command is set"
    if Path(command).is_absolute():
        return None if Path(command).exists() else f"the command {command} no longer exists"
    if not find_program(command):
        return f"`{command}` is not installed or not on PATH"
    return None


@app.command("feedback", rich_help_panel="Maintenance")
def feedback_cmd(
    bug: bool = typer.Option(
        False, "--bug", help="Report something that did not work, instead of general feedback"
    ),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the form in your browser, or only print its link"
    ),
) -> None:
    """Tell us how it went, or report a problem. Opens a GitHub form; nothing is sent for you."""
    import webbrowser

    from git_into_gsoc.feedback import form_url, system_summary

    url = form_url("bug" if bug else "feedback")
    _say(
        "This opens a GitHub form with your versions filled in, so you can tell us what "
        "worked and what did not. Nothing is sent until you read it and press Submit. "
        "Submitting needs a GitHub account."
    )
    _say(f"[dim]Filled in: {escape(system_summary())}[/dim]")
    console.print(url, markup=False, highlight=False, soft_wrap=True)
    if open_browser and sys.stdout.isatty() and not webbrowser.open(url):
        _say("[dim]No browser opened. Copy the link above into one.[/dim]")


@app.command("cache", rich_help_panel="Maintenance")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Delete all cached HTTP responses"),
    prune: bool = typer.Option(
        False, "--prune", help="Delete old entries now instead of at the daily check"
    ),
) -> None:
    """Show, prune, or clear the local HTTP cache."""
    http = _toolkit().github.http
    if clear:
        console.print(f"Removed {http.clear_cache()} cached responses")
        return
    if prune:
        console.print(f"Removed {http.prune_cache()} old cached responses")
    console.print(f"Cache size: {http.cache_size_bytes() / 1_048_576:.1f} MiB")
    settings = http.settings
    limits = []
    if settings.cache_max_age_days > 0:
        limits.append(f"entries not refreshed in {settings.cache_max_age_days} days are deleted")
    if settings.cache_max_mb > 0:
        limits.append(f"above {settings.cache_max_mb} MiB the oldest go first")
    if limits:
        console.print(f"[dim]Once a day, {'; '.join(limits)}.[/dim]")


if __name__ == "__main__":
    app()
