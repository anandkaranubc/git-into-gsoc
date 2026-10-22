"""Keep the reference docs in step with the code.

A command, option, MCP tool, or prompt that the docs never mention is one a
newcomer cannot find. Every option also needs help text, so `--help` explains it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import typer
from typer.core import TyperCommand, TyperGroup, TyperOption

ROOT = Path(__file__).resolve().parents[2]


# Typer ships its own copy of Click, so these checks use Typer's classes, not Click's.
def _commands() -> Iterator[tuple[str, TyperCommand | TyperGroup]]:
    from git_into_gsoc.cli import app

    root = typer.main.get_command(app)
    assert isinstance(root, TyperGroup)
    stack: list[tuple[str, TyperGroup]] = [("", root)]
    while stack:
        prefix, group = stack.pop()
        for name, command in sorted(group.commands.items()):
            if command.hidden:
                continue
            full = f"{prefix}{name}"
            yield full, command
            if isinstance(command, TyperGroup):
                stack.append((f"{full} ", command))


def _options(command: TyperCommand | TyperGroup) -> Iterator[TyperOption]:
    for param in command.params:
        if isinstance(param, TyperOption) and not param.hidden and "--help" not in param.opts:
            yield param


def test_the_checks_below_see_every_option() -> None:
    # Without this, a change to Typer's classes would let both checks pass on nothing.
    assert sum(1 for _, command in _commands() for _ in _options(command)) > 100


def test_every_command_and_option_is_in_the_command_reference() -> None:
    doc = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    missing: list[str] = []
    for name, command in _commands():
        # In backticks, as a command is written ("`projects [KEYWORDS]`" or "`git-into-gsoc
        # projects ...`"): the bare word "projects" is everywhere in prose, so a plain-word
        # match would pass after the command's row was gone.
        if not re.search(rf"`(?:git-into-gsoc |gsoc )?{re.escape(name)}(?=[\s`\[])", doc):
            missing.append(name)
        for option in _options(command):
            flags = [flag for flag in option.opts + option.secondary_opts if flag.startswith("--")]
            if flags and not any(flag in doc for flag in flags):
                missing.append(f"{name} {flags[0]}")
    assert not missing, f"add these to docs/cli.md: {missing}"


def test_every_command_and_option_has_help_text() -> None:
    missing: list[str] = []
    for name, command in _commands():
        if not (command.help or command.short_help):
            missing.append(name)
        for option in _options(command):
            if not (option.help or "").strip():
                missing.append(f"{name} {option.opts[0]}")
    assert not missing, f"give these help text: {missing}"


def test_every_mcp_tool_and_prompt_is_documented() -> None:
    from git_into_gsoc.mcp_server import mcp

    # The sync managers: asyncio.run() opens a socketpair on Windows, which the
    # network block in conftest.py refuses.
    names = [tool.name for tool in mcp._tool_manager.list_tools()]
    names += [prompt.name for prompt in mcp._prompt_manager.list_prompts()]
    mcp_doc = (ROOT / "docs" / "mcp.md").read_text(encoding="utf-8")
    skill = "".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "skills" / "git-into-gsoc").rglob("*.md"))
    )
    assert not [n for n in names if n not in mcp_doc], "add these to docs/mcp.md"
    assert not [n for n in names if n not in skill], "name these in skills/git-into-gsoc/"
