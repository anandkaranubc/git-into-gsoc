"""Per-assistant knowledge: where skills live and how MCP servers are registered.

Each assistant gets a declarative ``Assistant`` record. JSON-based clients are
edited with a merge that keeps every other key; Codex's TOML config is edited
textually and re-parsed to make sure it is still valid. Nothing here runs
network code, and every write is preceded by a ``.bak`` copy.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

SERVER_NAME = "git-into-gsoc"
Scope = Literal["user", "project"]


@dataclass(frozen=True)
class Change:
    """One file the setup touched (or would touch)."""

    assistant: str
    kind: Literal["skill", "mcp"]
    path: Path
    action: str  # created | updated | unchanged | skipped
    note: str = ""


@dataclass(frozen=True)
class McpTarget:
    """How to register our server with one assistant at one scope."""

    user_path: str | None  # relative to home, or None when unsupported
    project_path: str | None  # relative to project root, or None when unsupported
    fmt: Literal["json-mcpServers", "json-servers", "toml-codex"]
    manual_hint: str = ""
    cli: tuple[str, list[str]] | None = None  # (executable, argv prefix) for user scope
    cli_check: tuple[str, list[str]] | None = None  # exits 0 when already registered


@dataclass(frozen=True)
class Assistant:
    key: str
    label: str
    skill_dir: str  # relative to home or project root
    detect_dirs: tuple[str, ...] = ()
    detect_commands: tuple[str, ...] = ()
    mcp: McpTarget | None = None
    user_scope_skill: bool = True
    project_scope_skill: bool = True

    def present(self, home: Path) -> bool:
        if any((home / d).exists() for d in self.detect_dirs):
            return True
        return any(shutil.which(c) for c in self.detect_commands)


ASSISTANTS: dict[str, Assistant] = {
    "agents": Assistant(
        key="agents",
        label="Portable (.agents)",
        skill_dir=".agents/skills",
        detect_dirs=(".agents",),
    ),
    "claude-code": Assistant(
        key="claude-code",
        label="Claude Code",
        skill_dir=".claude/skills",
        detect_dirs=(".claude",),
        detect_commands=("claude",),
        mcp=McpTarget(
            user_path=None,
            project_path=".mcp.json",
            fmt="json-mcpServers",
            cli=(
                "claude",
                ["mcp", "add", "--scope", "user", "--transport", "stdio", SERVER_NAME, "--"],
            ),
            cli_check=("claude", ["mcp", "get", SERVER_NAME]),
            manual_hint=(
                "claude mcp add --scope user --transport stdio git-into-gsoc -- {command}"
            ),
        ),
    ),
    "cursor": Assistant(
        key="cursor",
        label="Cursor",
        skill_dir=".cursor/skills",
        detect_dirs=(".cursor",),
        detect_commands=("cursor",),
        mcp=McpTarget(
            user_path=".cursor/mcp.json", project_path=".cursor/mcp.json", fmt="json-mcpServers"
        ),
    ),
    "codex": Assistant(
        key="codex",
        label="Codex CLI",
        skill_dir=".codex/skills",
        detect_dirs=(".codex",),
        detect_commands=("codex",),
        mcp=McpTarget(
            user_path=".codex/config.toml",
            project_path=None,
            fmt="toml-codex",
            manual_hint="codex mcp add git-into-gsoc -- {command}",
        ),
    ),
    "gemini": Assistant(
        key="gemini",
        label="Gemini CLI",
        skill_dir=".gemini/skills",
        detect_dirs=(".gemini",),
        detect_commands=("gemini",),
        mcp=McpTarget(
            user_path=".gemini/settings.json",
            project_path=".gemini/settings.json",
            fmt="json-mcpServers",
        ),
    ),
    "windsurf": Assistant(
        key="windsurf",
        label="Windsurf",
        skill_dir=".codeium/windsurf/skills",
        detect_dirs=(".codeium/windsurf",),
        detect_commands=("windsurf",),
        mcp=McpTarget(
            user_path=".codeium/windsurf/mcp_config.json",
            project_path=None,
            fmt="json-mcpServers",
        ),
        project_scope_skill=False,
    ),
    "vscode": Assistant(
        key="vscode",
        label="VS Code (Copilot)",
        skill_dir=".github/skills",
        detect_dirs=(),
        detect_commands=("code",),
        mcp=McpTarget(
            user_path=None,
            project_path=".vscode/mcp.json",
            fmt="json-servers",
            manual_hint="In VS Code run 'MCP: Add Server' and enter: {command}",
        ),
        user_scope_skill=False,
    ),
}


def detect_assistants(home: Path | None = None) -> list[Assistant]:
    """Assistants with a config directory or executable on this machine."""
    home = home or Path.home()
    found = [a for a in ASSISTANTS.values() if a.key != "agents" and a.present(home)]
    return found


def server_command() -> list[str]:
    """Absolute command that launches our MCP server from this installation.

    Prefer the console script next to the running interpreter (venv, uv tool,
    pipx), then one on PATH, then ``python -m`` as a last resort.
    """
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    for bindir in (Path(sys.executable).parent, Path(sys.prefix) / scripts):
        for name in ("git-into-gsoc", "git-into-gsoc.exe"):
            candidate = bindir / name
            if candidate.is_file():
                return [str(candidate), "mcp"]
    on_path = shutil.which("git-into-gsoc")
    if on_path:
        return [str(Path(on_path)), "mcp"]
    return [sys.executable, "-m", "git_into_gsoc", "mcp"]


def register_via_cli(
    executable: str, argv: list[str], *, timeout: float = 60.0
) -> tuple[bool, str]:
    """Run an assistant's own `mcp add` command; returns (ok, trimmed output)."""
    try:
        result = subprocess.run(
            [executable, *argv], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output[-300:]


def server_entry(command: list[str], fmt: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"command": command[0], "args": command[1:]}
    if fmt == "json-servers":
        entry = {"type": "stdio", **entry}
    return entry


# ----------------------------------------------------------------- file edits


def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def register_json(
    path: Path, key: str, entry: dict[str, Any], *, dry_run: bool = False
) -> tuple[str, str]:
    """Merge ``{key: {SERVER_NAME: entry}}`` into a JSON file. Returns (action, note)."""
    try:
        data = _read_json(path)
    except (ValueError, OSError) as exc:
        return "skipped", f"could not parse {path.name}: {exc}"
    servers = data.get(key)
    if servers is not None and not isinstance(servers, dict):
        return "skipped", f"{path.name} has a non-object {key!r}"
    servers = dict(servers or {})
    if servers.get(SERVER_NAME) == entry:
        return "unchanged", ""
    action = "updated" if path.exists() else "created"
    if dry_run:
        return action, ""
    servers[SERVER_NAME] = entry
    data[key] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action, ""


_TOML_SECTION = re.compile(
    rf"^\[mcp_servers\.\"?{re.escape(SERVER_NAME)}\"?\]\n(?:(?!\[).*\n?)*", re.MULTILINE
)


def register_codex_toml(
    path: Path, command: list[str], *, dry_run: bool = False
) -> tuple[str, str]:
    """Add or replace ``[mcp_servers.git-into-gsoc]`` in Codex's config.toml."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    args = ", ".join(json.dumps(a) for a in command[1:])
    block = f'[mcp_servers."{SERVER_NAME}"]\ncommand = {json.dumps(command[0])}\nargs = [{args}]\n'
    try:
        current = tomllib.loads(existing).get("mcp_servers", {}).get(SERVER_NAME)
    except tomllib.TOMLDecodeError as exc:
        return "skipped", f"could not parse {path.name}: {exc}"
    if current == {"command": command[0], "args": command[1:]}:
        return "unchanged", ""
    if _TOML_SECTION.search(existing):
        new_text = _TOML_SECTION.sub(block, existing, count=1)
    else:
        sep = (
            ""
            if not existing or existing.endswith("\n\n")
            else ("\n" if existing.endswith("\n") else "\n\n")
        )
        new_text = existing + sep + block
    tomllib.loads(new_text)  # raise before touching the file if we produced junk
    action = "updated" if path.exists() else "created"
    if dry_run:
        return action, ""
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    path.write_text(new_text, encoding="utf-8")
    return action, ""


def registered_servers(home: Path, project: Path | None = None) -> list[tuple[str, Path]]:
    """Where our MCP server is already registered (for ``doctor``)."""
    found: dict[Path, str] = {}
    for assistant in ASSISTANTS.values():
        if not assistant.mcp:
            continue
        candidates: list[Path] = []
        if assistant.mcp.user_path:
            candidates.append(home / assistant.mcp.user_path)
        if project and assistant.mcp.project_path:
            candidates.append(project / assistant.mcp.project_path)
        for path in candidates:
            if not path.is_file():
                continue
            try:
                if assistant.mcp.fmt == "toml-codex":
                    data = tomllib.loads(path.read_text(encoding="utf-8"))
                    hit = SERVER_NAME in (data.get("mcp_servers") or {})
                else:
                    key = "servers" if assistant.mcp.fmt == "json-servers" else "mcpServers"
                    hit = SERVER_NAME in (_read_json(path).get(key) or {})
            except (ValueError, OSError, tomllib.TOMLDecodeError):
                continue
            if hit:
                found.setdefault(path.resolve(), assistant.label)
    return [(label, path) for path, label in found.items()]


def installed_skills(home: Path, project: Path | None = None) -> list[tuple[str, Path]]:
    found: dict[Path, str] = {}
    for assistant in ASSISTANTS.values():
        roots = [home] + ([project] if project else [])
        for root in roots:
            path = root / assistant.skill_dir / SERVER_NAME / "SKILL.md"
            if path.is_file():
                found.setdefault(path.parent.resolve(), assistant.label)
    return [(label, path) for path, label in found.items()]


def env_home() -> Path:
    """Honour HOME/USERPROFILE overrides so tests and CI can redirect writes."""
    override = os.environ.get("GIG_HOME")
    return Path(override).expanduser() if override else Path.home()
