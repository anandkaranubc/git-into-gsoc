"""Per-assistant knowledge: where skills live and how MCP servers are registered.

Each assistant gets a declarative ``Assistant`` record. JSON-based clients are
edited with a merge that keeps every other key; Codex's TOML config is edited
textually and re-parsed to make sure it is still valid. Nothing here runs
network code, and every write is preceded by a ``.bak`` copy.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from git_into_gsoc.programs import find_program

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


# One shared skill folder that most assistants read: Codex, Cursor, Gemini CLI,
# Windsurf (Devin Desktop), VS Code, Copilot CLI, and many tools setup does not
# configure by name (Zed, Goose, OpenCode, Amp, Junie, Cline). One copy there means
# each of them lists the skill once instead of once per folder it scans.
SHARED_SKILLS = ".agents/skills"

EntryStyle = Literal["plain", "vscode", "copilot", "gemini"]


@dataclass(frozen=True)
class McpTarget:
    """How to register our server with one assistant at one scope."""

    user_path: str | None  # relative to home, or None when unsupported
    project_path: str | None  # relative to project root, or None when unsupported
    fmt: Literal["json-mcpServers", "json-servers", "toml-codex"]
    manual_hint: str = ""
    cli: tuple[str, list[str]] | None = None  # (executable, argv prefix) for user scope
    cli_check: tuple[str, list[str]] | None = None  # exits 0 when already registered
    cli_remove: tuple[str, list[str]] | None = None  # removes the registration again
    style: EntryStyle = "plain"
    # Older locations of the user file, used instead when only their folder exists
    # (Windsurf before it became Devin Desktop).
    user_path_fallbacks: tuple[str, ...] = ()
    project_note: str = ""  # shown when the project file was written
    project_fmt: Literal["json-mcpServers", "json-servers", "toml-codex"] | None = None
    # Where the assistant's own CLI stores a user-scope registration. Only `doctor`
    # reads it; setup never writes there itself.
    user_read_path: str | None = None

    def fmt_for(self, scope: Scope) -> Literal["json-mcpServers", "json-servers", "toml-codex"]:
        return (self.project_fmt or self.fmt) if scope == "project" else self.fmt

    def style_for(self, scope: Scope) -> EntryStyle:
        return "plain" if scope == "project" and self.project_fmt else self.style


@dataclass(frozen=True)
class Assistant:
    """One assistant: where it reads skills, how it is detected, and how its MCP
    server is registered."""

    key: str
    label: str
    skill_dir: str  # where it reads skills, relative to home (user scope) or the project
    detect_dirs: tuple[str, ...] = ()
    detect_commands: tuple[str, ...] = ()
    mcp: McpTarget | None = None
    user_scope_skill: bool = True
    project_scope_skill: bool = True
    project_skill_dir: str | None = None  # when the project folder differs from skill_dir
    # Folders older versions of setup copied the skill into. This assistant now reads
    # the skill from skill_dir, so a copy left there would show up twice.
    legacy_skill_dirs: tuple[str, ...] = ()

    def present(self, home: Path) -> bool:
        if any(resolve_home_path(home, d).exists() for d in self.detect_dirs):
            return True
        return any(find_program(c) for c in self.detect_commands)

    def skill_dir_for(self, scope: Scope) -> str:
        return (self.project_skill_dir or self.skill_dir) if scope == "project" else self.skill_dir


ASSISTANTS: dict[str, Assistant] = {
    "agents": Assistant(
        key="agents",
        label="Shared (.agents)",
        skill_dir=SHARED_SKILLS,
        detect_dirs=(".agents",),
    ),
    "claude-code": Assistant(
        key="claude-code",
        label="Claude Code",
        # Claude Code reads only its own folder, not .agents/skills.
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
            cli_remove=("claude", ["mcp", "remove", "--scope", "user", SERVER_NAME]),
            user_read_path=".claude.json",
            manual_hint=(
                "claude mcp add --scope user --transport stdio git-into-gsoc -- {command}"
            ),
        ),
    ),
    "cursor": Assistant(
        key="cursor",
        label="Cursor",
        skill_dir=SHARED_SKILLS,
        legacy_skill_dirs=(".cursor/skills",),
        detect_dirs=(".cursor",),
        detect_commands=("cursor", "cursor-agent"),
        mcp=McpTarget(
            user_path=".cursor/mcp.json", project_path=".cursor/mcp.json", fmt="json-mcpServers"
        ),
    ),
    "codex": Assistant(
        key="codex",
        label="Codex",
        skill_dir=SHARED_SKILLS,
        legacy_skill_dirs=(".codex/skills",),
        detect_dirs=(".codex",),
        detect_commands=("codex",),
        mcp=McpTarget(
            user_path=".codex/config.toml",
            project_path=".codex/config.toml",
            fmt="toml-codex",
            manual_hint="codex mcp add git-into-gsoc -- {command}",
            project_note="Codex reads .codex/config.toml only in projects you have trusted",
        ),
    ),
    "gemini": Assistant(
        key="gemini",
        label="Gemini CLI",
        skill_dir=SHARED_SKILLS,
        legacy_skill_dirs=(".gemini/skills",),
        # Antigravity also creates ~/.gemini, so the folder alone does not mean Gemini CLI.
        detect_dirs=(".gemini/settings.json", ".gemini/extensions"),
        detect_commands=("gemini",),
        mcp=McpTarget(
            user_path=".gemini/settings.json",
            project_path=".gemini/settings.json",
            fmt="json-mcpServers",
            style="gemini",
        ),
    ),
    "antigravity": Assistant(
        key="antigravity",
        label="Antigravity",
        skill_dir=".gemini/config/skills",
        project_skill_dir=SHARED_SKILLS,
        detect_dirs=(".gemini/config", ".gemini/antigravity", ".gemini/antigravity-cli"),
        detect_commands=("agy", "antigravity"),
        mcp=McpTarget(
            user_path=".gemini/config/mcp_config.json",
            project_path=".agents/mcp_config.json",
            fmt="json-mcpServers",
        ),
    ),
    "windsurf": Assistant(
        key="windsurf",
        label="Windsurf (Devin Desktop)",
        skill_dir=SHARED_SKILLS,
        legacy_skill_dirs=(".codeium/windsurf/skills",),
        detect_dirs=(".config/devin", ".codeium/windsurf"),
        detect_commands=("devin", "windsurf"),
        mcp=McpTarget(
            user_path=".config/devin/mcp_config.json",
            user_path_fallbacks=(".codeium/windsurf/mcp_config.json",),
            project_path=".devin/mcp_config.json",
            fmt="json-mcpServers",
        ),
    ),
    "vscode": Assistant(
        key="vscode",
        label="VS Code and Copilot CLI",
        skill_dir=SHARED_SKILLS,
        legacy_skill_dirs=(".github/skills",),
        detect_dirs=(".copilot",),
        detect_commands=("code", "copilot"),
        mcp=McpTarget(
            # VS Code's Copilot sessions and Copilot CLI both read this one user file.
            user_path=".copilot/mcp-config.json",
            project_path=".vscode/mcp.json",
            fmt="json-mcpServers",
            style="copilot",
            project_fmt="json-servers",
        ),
    ),
}

# Where an assistant keeps its own settings when an environment variable moves them.
_HOME_OVERRIDES = {".codex": "CODEX_HOME", ".copilot": "COPILOT_HOME"}


def resolve_home_path(home: Path, rel: str) -> Path:
    """``rel`` under the home folder, following CODEX_HOME, COPILOT_HOME, and the
    platform's config folder for ``.config/...``.

    Those overrides apply only to the real home folder, so a GIG_HOME sandbox never
    writes to the person's actual assistant settings.
    """
    first, _, rest = rel.partition("/")
    try:
        real_home = home.resolve() == Path.home().resolve()
    except RuntimeError:  # no home folder can be determined
        real_home = False
    if real_home:
        env = _HOME_OVERRIDES.get(first)
        if env and os.environ.get(env):
            return Path(os.environ[env]).expanduser() / rest
        if first == ".config":
            base = os.environ.get("APPDATA" if sys.platform == "win32" else "XDG_CONFIG_HOME")
            if base:
                return Path(base) / rest
    return home / rel


def user_config_path(target: McpTarget, home: Path) -> Path | None:
    """The user-scope config file, preferring the current location of the assistant."""
    if target.user_path is None:
        return None
    primary = resolve_home_path(home, target.user_path)
    if primary.parent.exists():
        return primary
    for fallback in target.user_path_fallbacks:
        candidate = resolve_home_path(home, fallback)
        if candidate.parent.exists():
            return candidate
    return primary


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
    on_path = find_program("git-into-gsoc")
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


# Gemini CLI removes variables that look like tokens before it starts a server, but
# expands ones named in `env` from the full environment (to "" when unset).
GEMINI_TOKEN_ENV = {name: f"${name}" for name in ("GIG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")}


def server_entry(command: list[str], fmt: str, style: EntryStyle = "plain") -> dict[str, Any]:
    """The server's entry in the shape this assistant's config file expects."""
    entry: dict[str, Any] = {"command": command[0], "args": command[1:]}
    if fmt == "json-servers":
        return {"type": "stdio", **entry}
    if style == "copilot":
        return {"type": "local", **entry, "tools": ["*"]}
    if style == "gemini":
        return {**entry, "env": dict(GEMINI_TOKEN_ENV)}
    return entry


# ----------------------------------------------------------------- file edits


def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def _read_text(path: Path) -> str:
    # utf-8-sig: Windows editors often save JSON with a byte-order mark.
    return path.read_text(encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = _read_text(path).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Usually comments or trailing commas, which VS Code and Cursor accept.
        # Rewriting would drop the person's comments, so the file is left alone.
        raise ValueError(f"not plain JSON ({exc.msg}, line {exc.lineno}), left as is") from exc
    if not isinstance(data, dict):
        raise ValueError("does not contain a JSON object, left as is")
    return data


# Strings come first in each pattern, so "//" or ",}" inside a string is kept.
_JSONC_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
_JSONC_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')


def _keep_strings(match: re.Match[str]) -> str:
    return match.group(0) if match.group(0).startswith('"') else ""


def _read_jsonc(path: Path) -> dict[str, Any]:
    """Read JSON that may have comments or trailing commas. Only for checking what is
    registered: writing it back would lose the comments."""
    text = _JSONC_COMMENT.sub(_keep_strings, _read_text(path))
    text = _JSONC_TRAILING_COMMA.sub(_keep_strings, text).strip()
    data = json.loads(text) if text else {}
    return data if isinstance(data, dict) else {}


def _write_config(path: Path, text: str) -> None:
    """Replace a config file in one step, keeping its permissions and any symlink.

    A crash or Ctrl+C mid-write must never leave a person's assistant settings
    half written, and a dotfiles symlink must keep pointing at its target.
    """
    target = path.resolve() if path.is_symlink() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        mode = target.stat().st_mode & 0o777
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def register_json(
    path: Path, key: str, entry: dict[str, Any], *, dry_run: bool = False
) -> tuple[str, str]:
    """Merge ``{key: {SERVER_NAME: entry}}`` into a JSON file. Returns (action, note)."""
    try:
        data = _read_json(path)
    except (ValueError, OSError) as exc:
        return "skipped", f"{path.name} is {exc}"
    servers = data.get(key)
    if servers is not None and not isinstance(servers, dict):
        return "skipped", f"{path.name} has a non-object {key!r}, left as is"
    servers = dict(servers or {})
    if servers.get(SERVER_NAME) == entry:
        return "unchanged", ""
    action = "updated" if path.exists() else "created"
    if dry_run:
        return action, ""
    servers[SERVER_NAME] = entry
    data[key] = servers
    _backup(path)
    _write_config(path, json.dumps(data, indent=2) + "\n")
    return action, ""


# Codex hands a server only a short list of variables (HOME, PATH, and a few more),
# so the token and proxy settings must be forwarded by name. A first start may also
# download dependencies, which can take longer than Codex's default 10 seconds.
CODEX_ENV_VARS = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GIG_GITHUB_TOKEN",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
)
CODEX_STARTUP_TIMEOUT_SEC = 60

# Our server's table or one of its subtables, such as [mcp_servers.git-into-gsoc.env]
# written by `codex mcp add --env`. A subtable left behind without its table stops
# Codex from starting ("invalid transport"), so removal must take every one of them.
_NAME = rf'(?:"{re.escape(SERVER_NAME)}"|{re.escape(SERVER_NAME)})'
_TOML_OUR_TABLE = re.compile(rf"^\s*\[\s*mcp_servers\s*\.\s*{_NAME}\s*\](?:\s*#.*)?\s*$")
_TOML_OUR_SUBTABLE = re.compile(rf"^\s*\[\s*mcp_servers\s*\.\s*{_NAME}\s*\.[^\]]*\](?:\s*#.*)?\s*$")
_TOML_ANY_TABLE = re.compile(r"^\s*\[")


def _drop_codex_sections(text: str, *, subtables: bool) -> tuple[list[str], int | None]:
    """Remove our table (and, if asked, its subtables). Returns the remaining lines and
    the line index where the first removed section started, or None."""
    kept: list[str] = []
    first: int | None = None
    skipping = False
    for line in text.splitlines(keepends=True):
        if _TOML_ANY_TABLE.match(line):
            skipping = bool(
                _TOML_OUR_TABLE.match(line) or (subtables and _TOML_OUR_SUBTABLE.match(line))
            )
            if skipping and first is None:
                first = len(kept)
        if not skipping:
            kept.append(line)
    return kept, first


def _codex_block(command: list[str]) -> str:
    args = ", ".join(json.dumps(a) for a in command[1:])
    env_vars = ", ".join(json.dumps(v) for v in CODEX_ENV_VARS)
    return (
        f'[mcp_servers."{SERVER_NAME}"]\n'
        f"command = {json.dumps(command[0])}\n"
        f"args = [{args}]\n"
        f"env_vars = [{env_vars}]\n"
        f"startup_timeout_sec = {CODEX_STARTUP_TIMEOUT_SEC}\n"
    )


def _codex_entry_current(entry: object, command: list[str]) -> bool:
    if not isinstance(entry, dict):
        return False
    timeout = entry.get("startup_timeout_sec")
    if timeout is None and isinstance(entry.get("startup_timeout_ms"), int | float):
        timeout = entry["startup_timeout_ms"] / 1000
    forwarded = entry.get("env_vars") or []
    return (
        entry.get("command") == command[0]
        and entry.get("args") == command[1:]
        and isinstance(forwarded, list)
        and set(CODEX_ENV_VARS) <= {v for v in forwarded if isinstance(v, str)}
        and isinstance(timeout, int | float)
        and timeout >= CODEX_STARTUP_TIMEOUT_SEC
    )


def register_codex_toml(
    path: Path, command: list[str], *, dry_run: bool = False
) -> tuple[str, str]:
    """Add or replace ``[mcp_servers.git-into-gsoc]`` in Codex's config.toml.

    Subtables the person added (``.env``, ``.tools``) stay attached to the new table.
    """
    existing = _read_text(path) if path.exists() else ""
    try:
        current = tomllib.loads(existing).get("mcp_servers", {}).get(SERVER_NAME)
    except tomllib.TOMLDecodeError as exc:
        return "skipped", f"{path.name} is not valid TOML ({exc}), left as is"
    if _codex_entry_current(current, command):
        return "unchanged", ""
    kept, at = _drop_codex_sections(existing, subtables=False)
    block = _codex_block(command)
    if at is not None:
        kept.insert(at, block + ("\n" if at < len(kept) else ""))
        new_text = "".join(kept)
    else:
        rest = "".join(kept)
        sep = "" if not rest or rest.endswith("\n\n") else ("\n" if rest.endswith("\n") else "\n\n")
        new_text = rest + sep + block
    try:
        written = tomllib.loads(new_text).get("mcp_servers", {}).get(SERVER_NAME)
    except tomllib.TOMLDecodeError as exc:
        # For example an inline `git-into-gsoc = {...}` under [mcp_servers]: editing
        # that safely needs a person, so say what to change instead.
        return "skipped", f"{path.name} could not be updated safely ({exc}), left as is"
    if not _codex_entry_current(written, command):
        return (
            "skipped",
            f"{path.name} defines {SERVER_NAME} in a way setup cannot edit, left as is",
        )
    action = "updated" if path.exists() else "created"
    if dry_run:
        return action, ""
    _backup(path)
    _write_config(path, new_text)
    return action, ""


def unregister_json(path: Path, key: str, *, dry_run: bool = False) -> tuple[str, str]:
    """Drop our server entry from a JSON config, leaving everything else untouched."""
    if not path.exists():
        return "unchanged", ""
    try:
        data = _read_json(path)
    except (ValueError, OSError) as exc:
        return "skipped", f"{path.name} is {exc}"
    servers = data.get(key)
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        return "unchanged", ""
    if dry_run:
        return "removed", ""
    servers = dict(servers)
    del servers[SERVER_NAME]
    data[key] = servers
    _backup(path)
    _write_config(path, json.dumps(data, indent=2) + "\n")
    return "removed", ""


def unregister_codex_toml(path: Path, *, dry_run: bool = False) -> tuple[str, str]:
    """Drop ``[mcp_servers.git-into-gsoc]`` and every subtable from Codex's config.toml."""
    if not path.exists():
        return "unchanged", ""
    existing = _read_text(path)
    try:
        before = tomllib.loads(existing)
    except tomllib.TOMLDecodeError as exc:
        return "skipped", f"{path.name} is not valid TOML ({exc}), left as is"
    if SERVER_NAME not in (before.get("mcp_servers") or {}):
        return "unchanged", ""
    kept, at = _drop_codex_sections(existing, subtables=True)
    new_text = "".join(kept).rstrip("\n") + "\n"
    try:
        after = tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:
        return "skipped", f"{path.name} could not be updated safely ({exc}), left as is"
    if at is None or SERVER_NAME in (after.get("mcp_servers") or {}):
        return (
            "skipped",
            f"{path.name} defines {SERVER_NAME} in a way setup cannot edit, left as is",
        )
    if dry_run:
        return "removed", ""
    _backup(path)
    _write_config(path, new_text)
    return "removed", ""


def _config_key(fmt: str) -> str:
    return "servers" if fmt == "json-servers" else "mcpServers"


def registered_entry(path: Path, fmt: str) -> dict[str, Any] | None:
    """Our server's entry in one config file, or None (also when unreadable)."""
    if not path.is_file():
        return None
    try:
        if fmt == "toml-codex":
            entry = (tomllib.loads(_read_text(path)).get("mcp_servers") or {}).get(SERVER_NAME)
        else:
            entry = (_read_jsonc(path).get(_config_key(fmt)) or {}).get(SERVER_NAME)
    except (ValueError, OSError, tomllib.TOMLDecodeError):
        return None
    return entry if isinstance(entry, dict) else None


def registered_servers(home: Path, project: Path | None = None) -> list[tuple[str, Path]]:
    """Where our MCP server is already registered (for ``doctor``)."""
    return [(label, path) for label, path, _ in registrations(home, project)]


def registrations(
    home: Path, project: Path | None = None
) -> list[tuple[str, Path, dict[str, Any]]]:
    """(assistant label, config file, our entry) for every place we are registered."""
    found: dict[Path, tuple[str, dict[str, Any]]] = {}
    for assistant in ASSISTANTS.values():
        target = assistant.mcp
        if not target:
            continue
        candidates: list[tuple[Path, str]] = []
        if target.user_path:
            for rel in (target.user_path, *target.user_path_fallbacks):
                candidates.append((resolve_home_path(home, rel), target.fmt_for("user")))
        elif target.user_read_path:
            candidates.append((home / target.user_read_path, target.fmt_for("user")))
        if project and target.project_path:
            candidates.append((project / target.project_path, target.fmt_for("project")))
        for path, fmt in candidates:
            entry = registered_entry(path, fmt)
            if entry is not None:
                found.setdefault(path.resolve(), (assistant.label, entry))
    return [(label, path, entry) for path, (label, entry) in found.items()]


def skill_locations(assistant: Assistant, scope: Scope, root: Path) -> tuple[Path, list[Path]]:
    """(where the skill goes now, older locations to clean up) for one scope."""

    def place(rel: str) -> Path:
        base = resolve_home_path(root, rel) if scope == "user" else root / rel
        return base / SERVER_NAME

    return place(assistant.skill_dir_for(scope)), [place(d) for d in assistant.legacy_skill_dirs]


def installed_skills(home: Path, project: Path | None = None) -> list[tuple[str, Path]]:
    """Every copy of the skill in current and older locations, as (assistant label,
    folder), for `doctor`."""
    found: dict[Path, str] = {}
    for assistant in ASSISTANTS.values():
        scopes: list[tuple[Scope, Path]] = [("user", home)]
        if project:
            scopes.append(("project", project))
        for scope, root in scopes:
            current, legacy = skill_locations(assistant, scope, root)
            for path in (current, *legacy):
                if (path / "SKILL.md").is_file():
                    found.setdefault(path.resolve(), assistant.label)
    return [(label, path) for path, label in found.items()]


def is_our_skill(folder: Path) -> bool:
    """True for a git-into-gsoc skill folder (so cleanup never removes anything else)."""
    try:
        head = (folder / "SKILL.md").read_text(encoding="utf-8-sig")[:2000]
    except OSError:
        return False
    return bool(re.search(rf"^name:\s*['\"]?{re.escape(SERVER_NAME)}['\"]?\s*$", head, re.M))


# ------------------------------------------------------------ installed plugins


def _json_or_empty(path: Path) -> dict[str, Any]:
    try:
        data = _read_jsonc(path) if path.is_file() else {}
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _ours(plugin_id: object) -> bool:
    return isinstance(plugin_id, str) and plugin_id.split("@", 1)[0] == SERVER_NAME


def installed_plugin(assistant: Assistant, home: Path) -> str | None:
    """How the git-into-gsoc plugin or extension is installed for this assistant, if it is.

    The plugin brings its own skill and server, so setup leaves that assistant alone
    rather than adding a second copy of each.
    """
    key = assistant.key
    if key == "claude-code":
        records = _json_or_empty(resolve_home_path(home, ".claude/plugins/installed_plugins.json"))
        if any(_ours(name) for name in (records.get("plugins") or {})):
            return "the Claude Code plugin"
    elif key == "codex":
        path = resolve_home_path(home, ".codex/config.toml")
        try:
            plugins = tomllib.loads(_read_text(path)).get("plugins", {}) if path.is_file() else {}
        except (OSError, tomllib.TOMLDecodeError):
            plugins = {}
        if any(_ours(n) and (v or {}).get("enabled", True) for n, v in plugins.items()):
            return "the Codex plugin"
    elif key == "gemini":
        if resolve_home_path(home, f".gemini/extensions/{SERVER_NAME}").is_dir():
            return "the Gemini CLI extension"
    elif key == "antigravity":
        if resolve_home_path(home, f".gemini/config/plugins/{SERVER_NAME}").is_dir():
            return "the Antigravity plugin"
    elif key == "vscode":
        settings = _json_or_empty(resolve_home_path(home, ".copilot/settings.json"))
        enabled = settings.get("enabledPlugins") or {}
        if isinstance(enabled, dict) and any(_ours(n) and v for n, v in enabled.items()):
            return "the Copilot plugin"
    return None


PLUGIN_REMOVAL = {
    "claude-code": "claude plugin uninstall git-into-gsoc@git-into-gsoc",
    "codex": "codex plugin remove git-into-gsoc@git-into-gsoc",
    "gemini": "gemini extensions uninstall git-into-gsoc",
    "antigravity": "agy plugin uninstall git-into-gsoc",
    "vscode": "copilot plugin uninstall git-into-gsoc@git-into-gsoc",
}


def env_home() -> Path:
    """Honour HOME/USERPROFILE overrides so tests and CI can redirect writes."""
    override = os.environ.get("GIG_HOME")
    return Path(override).expanduser() if override else Path.home()
