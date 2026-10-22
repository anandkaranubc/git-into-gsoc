"""Install git-into-gsoc into real AI coding agents and check that each one can start it.

Every agent CLI found on PATH gets its own throwaway home folder. The script installs
the plugin or extension with that agent's own commands, from a clean copy of this
checkout (or, with --remote, straight from GitHub). Then it asks the agent what it
registered and checks that the server answers: through the agent's own health check
where it has one, otherwise by starting the exact command the agent resolved.

With --setup it also runs `git-into-gsoc setup` for each agent and checks that the
agent reads what setup wrote.

Nothing here touches your real settings, sends a prompt to a model, or needs a login:
HOME and each agent's own home variable point into a temporary folder, and token
variables are removed from the environment.

Usage:
    python scripts/check_agents.py [--only claude,codex] [--setup] [--remote] [--json]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_smoke import SmokeError, smoke  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
from git_into_gsoc.install import distribution  # noqa: E402

NAME = "git-into-gsoc"
PLUGIN_ID = f"{NAME}@{NAME}"
REPO = "anandkaranubc/git-into-gsoc"
TIMEOUT = 300.0
# The MCP bundle validator. Bump it from time to time, like the agent versions in
# .github/workflows/agents.yml.
MCPB_CLI = "@anthropic-ai/mcpb@2.1.2"
# Never let a check sign in anywhere or reach a paid model.
SECRET_VARS = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GIG_GITHUB_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "CURSOR_API_KEY",
)


@dataclass
class Result:
    """One agent's outcome on one route, printed as a row or as JSON."""

    agent: str
    route: str  # plugin | setup
    status: str  # ok | registered | failed | skipped
    detail: str


class CheckFailed(Exception):
    """A step failed; the message says which and shows the agent's own output."""


class Sandbox:
    """A throwaway home folder for one agent, plus a trusted folder to run in."""

    def __init__(self, base: Path, name: str, cache: Path) -> None:
        self.dir = base / name
        self.home = self.dir / "home"
        self.cwd = self.dir / "work"
        # Codex refuses to start when CODEX_HOME names a folder that does not exist.
        for folder in (self.cwd, *(self.home / d for d in (".claude", ".codex", ".copilot"))):
            folder.mkdir(parents=True, exist_ok=True)
        self.cache = cache

    def env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k not in SECRET_VARS}
        home = str(self.home)
        env.update(
            HOME=home,
            USERPROFILE=home,
            XDG_CONFIG_HOME=str(self.home / ".config"),
            XDG_DATA_HOME=str(self.home / ".local" / "share"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"),
            CODEX_HOME=str(self.home / ".codex"),
            GEMINI_CLI_HOME=home,
            COPILOT_HOME=str(self.home / ".copilot"),
            GIG_HOME=home,
            GIG_DATA_DIR=str(self.dir / "gig-data"),
            GIG_CACHE_DIR=str(self.dir / "gig-cache"),
            UV_CACHE_DIR=str(self.cache),
            DISABLE_TELEMETRY="1",
            DO_NOT_TRACK="1",
            NO_COLOR="1",
        )
        return env

    def run(self, argv: list[str], *, stdin: str = "", ok_codes: tuple[int, ...] = (0,)) -> str:
        try:
            done = subprocess.run(
                argv,
                cwd=self.cwd,
                env=self.env(),
                input=stdin,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise CheckFailed(f"`{' '.join(argv)}` took longer than {TIMEOUT:.0f}s") from exc
        output = (done.stdout or "") + (done.stderr or "")
        if done.returncode not in ok_codes:
            raise CheckFailed(f"`{' '.join(argv)}` exited {done.returncode}:\n{_tail(output)}")
        return output

    def trust_for_gemini(self) -> None:
        # Gemini CLI starts MCP servers only in folders the person trusted.
        level = "TRUST_FOLDER"
        folders = {str(self.cwd): level, str(self.cwd.resolve()): level}
        listing = self.home / ".gemini" / "trustedFolders.json"
        listing.parent.mkdir(parents=True, exist_ok=True)
        listing.write_text(json.dumps(folders), encoding="utf-8")

    def smoke(self, entry: dict[str, Any], cwd: str | None = None) -> str:
        argv = [entry["command"], *entry.get("args", [])]
        env = self.env()
        for key, value in (entry.get("env") or {}).items():
            env[key] = str(value)  # as written, which is what a host that does not expand passes
        try:
            summary = smoke(argv, timeout=TIMEOUT, env=env, cwd=cwd or str(self.cwd))
        except SmokeError as exc:
            raise CheckFailed(f"the server did not answer: {exc}") from exc
        return f"server {summary['version']} answered with {summary['tools']} tools"


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _line_with(output: str, *needles: str) -> str | None:
    for line in output.splitlines():
        if all(n in line for n in needles):
            return line.strip()
    return None


def _json(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise CheckFailed(f"expected JSON, got:\n{_tail(output)}")
    data, _ = json.JSONDecoder().raw_decode(output[start:])
    if not isinstance(data, dict):
        raise CheckFailed("expected a JSON object")
    return data


# ------------------------------------------------------------------ plugin routes


def plugin_claude(box: Sandbox, source: str) -> tuple[str, str]:
    if not source.startswith(("http", REPO)):
        # The directory profile adds the checks Anthropic's plugin directory runs on a
        # submission, such as a README and readable MCP files.
        box.run(["claude", "plugin", "validate", source, "--profile", "directory"])
    box.run(["claude", "plugin", "marketplace", "add", source])
    box.run(["claude", "plugin", "install", PLUGIN_ID])
    line = _line_with(box.run(["claude", "mcp", "list"]), f"plugin:{NAME}")
    if not line or "Connected" not in line:
        raise CheckFailed(f"`claude mcp list` did not show the plugin server connected: {line}")
    return "ok", "plugin installed; `claude mcp list` shows the server connected"


def plugin_codex(box: Sandbox, source: str) -> tuple[str, str]:
    box.run(["codex", "plugin", "marketplace", "add", source])
    box.run(["codex", "plugin", "add", PLUGIN_ID])
    entry = _json(box.run(["codex", "mcp", "get", NAME, "--json"]))
    transport = entry.get("transport") or {}
    if (entry.get("startup_timeout_sec") or 0) < 60:
        raise CheckFailed(
            f"the start timeout is {entry.get('startup_timeout_sec')}, not 60 or more"
        )
    if "GITHUB_TOKEN" not in (transport.get("env_vars") or []):
        raise CheckFailed("GITHUB_TOKEN is not passed on to the server")
    return "ok", box.smoke(transport, cwd=transport.get("cwd"))


def plugin_copilot(box: Sandbox, source: str) -> tuple[str, str]:
    box.run(["copilot", "plugin", "marketplace", "add", source])
    box.run(["copilot", "plugin", "install", PLUGIN_ID])
    output = box.run(["copilot", "mcp", "get", NAME])
    if "Plugin" not in output:
        raise CheckFailed(f"`copilot mcp get` does not show the plugin server:\n{_tail(output)}")
    # Copilot reads .github/plugin/plugin.json before .claude-plugin/, and only the
    # Copilot manifest names the folder ${PLUGIN_ROOT}.
    command = (_line_with(output, "Command:") or "").removeprefix("Command:").split()
    if distribution.COPILOT_PLUGIN_ROOT not in command:
        raise CheckFailed(f"Copilot did not read .github/plugin/plugin.json: {' '.join(command)}")
    # Copilot CLI starts MCP servers only for a signed-in session, so start the same
    # command here, with the folder it would expand ${PLUGIN_ROOT} to.
    if source.startswith(("http", REPO)):
        return "registered", "plugin installed and its server registered (start needs a login)"
    argv = [source if a == distribution.COPILOT_PLUGIN_ROOT else a for a in command]
    return "ok", "plugin installed; " + box.smoke({"command": argv[0], "args": argv[1:]})


def plugin_gemini(box: Sandbox, source: str) -> tuple[str, str]:
    box.trust_for_gemini()
    if not source.startswith(("http", REPO)):
        box.run(["gemini", "extensions", "validate", source])
    box.run(["gemini", "extensions", "install", source, "--consent"], stdin="y\n")
    return "ok", _gemini_connected(box)


def _gemini_connected(box: Sandbox) -> str:
    line = None
    for _ in range(3):  # the list waits 5 s per server; a first start may build first
        line = _line_with(box.run(["gemini", "mcp", "list"]), NAME)
        if line and "Connected" in line:
            return "`gemini mcp list` shows the server connected"
    raise CheckFailed(f"`gemini mcp list` did not show the server connected: {line}")


def plugin_antigravity(box: Sandbox, source: str) -> tuple[str, str]:
    box.run(["agy", "plugin", "install", source], stdin="y\n")
    config = box.home / ".gemini" / "config" / "plugins" / NAME / "mcp_config.json"
    if not config.is_file():
        raise CheckFailed(f"no converted server config at {config}")
    entry = json.loads(config.read_text(encoding="utf-8"))["mcpServers"][NAME]
    return "ok", "plugin converted; " + box.smoke(entry)


# -------------------------------------------------------------------- setup routes


def _setup(box: Sandbox, gig: str, assistant: str) -> dict[str, Any]:
    plan = _json(box.run([gig, "setup", "--assistant", assistant, "--output", "json"]))
    failed = [c for c in plan["changes"] if c["action"] == "skipped" and not c["note"]]
    if failed:
        raise CheckFailed(f"setup skipped: {failed}")
    return plan


def setup_claude(box: Sandbox, gig: str) -> tuple[str, str]:
    plan = _setup(box, gig, "claude-code")
    if not any("claude mcp add" in c["note"] for c in plan["changes"]):
        # Setup prints `claude mcp add` when it cannot run it; check that step works.
        step = next((m for m in plan["manual_steps"] if "claude mcp add" in m), None)
        if not step:
            raise CheckFailed(f"setup neither ran nor printed `claude mcp add`: {plan}")
        box.run(step.split(": ", 1)[1].split())
    line = _line_with(box.run(["claude", "mcp", "list"]), f"{NAME}:")
    if not line or "Connected" not in line:
        raise CheckFailed(f"`claude mcp list` did not show the server connected: {line}")
    if not (box.home / ".claude" / "skills" / NAME / "SKILL.md").is_file():
        raise CheckFailed("the skill is missing from ~/.claude/skills")
    return "ok", "setup registered it with `claude mcp add`; server connected"


def setup_codex(box: Sandbox, gig: str) -> tuple[str, str]:
    _setup(box, gig, "codex")
    entry = _json(box.run(["codex", "mcp", "get", NAME, "--json"]))
    return "ok", box.smoke(entry.get("transport") or {})


def setup_gemini(box: Sandbox, gig: str) -> tuple[str, str]:
    box.trust_for_gemini()
    (box.home / ".gemini").mkdir(exist_ok=True)
    _setup(box, gig, "gemini")
    return "ok", _gemini_connected(box)


def setup_copilot(box: Sandbox, gig: str) -> tuple[str, str]:
    _setup(box, gig, "vscode")
    output = box.run(["copilot", "mcp", "get", NAME])
    if "local" not in output:
        raise CheckFailed(f"`copilot mcp get` does not show the server:\n{_tail(output)}")
    entry = json.loads((box.home / ".copilot" / "mcp-config.json").read_text())["mcpServers"]
    return "registered", "Copilot CLI lists it; " + box.smoke(entry[NAME])


def setup_antigravity(box: Sandbox, gig: str) -> tuple[str, str]:
    _setup(box, gig, "antigravity")
    line = _line_with(box.run(["agy", "mcp", "list"]), NAME)
    if not line or "enabled" not in line:
        raise CheckFailed(f"`agy mcp list` does not show the server enabled: {line}")
    return "ok", "`agy mcp list` shows it enabled"


def _cursor_tools(box: Sandbox) -> str:
    agent = shutil.which("cursor-agent") or shutil.which("agent") or "cursor-agent"
    output = box.run([agent, "mcp", "list-tools", NAME])
    match = re.search(r"Tools for \S+ \((\d+)\)", output)
    if not match or int(match.group(1)) < 20:
        raise CheckFailed(f"Cursor's agent CLI did not list the tools:\n{_tail(output)}")
    return f"Cursor's agent CLI started it and listed {match.group(1)} tools"


def setup_cursor(box: Sandbox, gig: str) -> tuple[str, str]:
    _setup(box, gig, "cursor")
    return "ok", _cursor_tools(box)


# ------------------------------------------------------------- buttons and bundles
# A button cannot be clicked here, so each check writes exactly what the app writes
# after the person confirms, then lets the app (or the same command) start it.


def _button_command(source: str) -> list[str]:
    if source == REPO:
        return distribution.remote_command()
    # Test this checkout's code, not the release on PyPI.
    return ["uvx", "--from", f"git+file://{source}", distribution.SERVER_NAME, "mcp"]


def button_cursor(box: Sandbox, source: str) -> tuple[str, str]:
    link = distribution.cursor_install_link(_button_command(source))
    query = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    config = json.loads(base64.b64decode(query["config"][0]))
    # On confirm, Cursor writes the decoded object as mcpServers[name] in ~/.cursor/mcp.json.
    target = box.home / ".cursor" / "mcp.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"mcpServers": {NAME: config}}), encoding="utf-8")
    return "ok", "the button's config: " + _cursor_tools(box)


def button_vscode(box: Sandbox, source: str) -> tuple[str, str]:
    link = distribution.vscode_install_link(_button_command(source))
    config = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["config"][0])
    profile = box.dir / "vscode-profile"
    box.run(
        [
            "code",
            "--user-data-dir",
            str(profile),
            "--extensions-dir",
            str(box.dir / "vscode-extensions"),
            "--add-mcp",
            json.dumps({"name": NAME, **config}),
        ]
    )
    written = json.loads((profile / "User" / "mcp.json").read_text(encoding="utf-8"))
    entry = written["servers"][NAME]
    return "ok", "VS Code accepted the button's config; " + box.smoke(entry)


def bundle_claude_desktop(box: Sandbox, source: str) -> tuple[str, str]:
    bundle = box.dir / "git-into-gsoc.mcpb"
    if source == REPO:
        url = f"https://github.com/{REPO}/releases/latest/download/git-into-gsoc.mcpb"
        with urllib.request.urlopen(url, timeout=60) as response:
            bundle.write_bytes(response.read())
    else:
        build = ROOT / "scripts" / "build_mcpb.py"
        box.run([sys.executable, str(build), "--root", source, "--out", str(bundle)])
    folder = box.dir / "extension"
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("icon") and not (folder / manifest["icon"]).is_file():
        raise CheckFailed(f"the bundle names the icon {manifest['icon']} but does not contain it")
    if shutil.which("npx"):
        # The bundle format's own validator, as Claude Desktop's directory uses it.
        box.run(["npx", "--yes", MCPB_CLI, "validate", str(folder / "manifest.json")])
    config = manifest["server"]["mcp_config"]

    # Claude Desktop fills ${__dirname} with the unpacked folder and leaves an unset
    # optional setting empty; the server must start either way.
    def fill(value: str) -> str:
        return re.sub(r"\$\{user_config\.[^}]+\}", "", value.replace("${__dirname}", str(folder)))

    entry = {
        "command": config["command"],
        "args": [fill(a) for a in config.get("args", [])],
        "env": {k: fill(v) for k, v in (config.get("env") or {}).items()},
    }
    return (
        "ok",
        f"bundle {manifest['version']} unpacked and started as Desktop runs it; "
        + box.smoke(entry),
    )


Check = Callable[..., tuple[str, str]]
AGENTS: dict[str, tuple[tuple[str, ...], Check | None, Check | None]] = {
    # name: (executables, plugin or button or bundle check, setup check)
    "claude": (("claude",), plugin_claude, setup_claude),
    "codex": (("codex",), plugin_codex, setup_codex),
    "copilot": (("copilot",), plugin_copilot, setup_copilot),
    "gemini": (("gemini",), plugin_gemini, setup_gemini),
    "antigravity": (("agy",), plugin_antigravity, setup_antigravity),
    "cursor": (("cursor-agent", "agent"), button_cursor, setup_cursor),
    "vscode": (("code",), button_vscode, None),
    "claude-desktop": (("uv",), bundle_claude_desktop, None),
}
# What the first check of each agent installs from.
FIRST_ROUTE = {"cursor": "button", "vscode": "button", "claude-desktop": "bundle"}


def clean_copy(dest: Path) -> Path:
    """The checkout's files (tracked and new, not ignored), as a fresh Git repository."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    for raw in filter(None, listed):
        rel = raw.decode()
        source = ROOT / rel
        if source.is_file():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    git = ["git", "-c", "user.name=check", "-c", "user.email=check@example.invalid"]
    for step in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "snapshot"]):
        subprocess.run([*git, *step], cwd=dest, check=True, capture_output=True)
    return dest


def remote_source(agent: str) -> str:
    url = f"https://github.com/{REPO}"
    return url if agent in {"gemini", "antigravity"} else REPO


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check git-into-gsoc in real agent CLIs.")
    parser.add_argument("--only", help="Comma-separated agents: " + ", ".join(AGENTS))
    parser.add_argument("--setup", action="store_true", help="Also check `git-into-gsoc setup`")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Install what people get (plugins from GitHub, buttons from PyPI), not this checkout",
    )
    parser.add_argument("--gig", help="git-into-gsoc executable for --setup (default: this env)")
    parser.add_argument("--require", help="Comma-separated agents that must be installed")
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary folders")
    ns = parser.parse_args(args)
    chosen = ns.only.split(",") if ns.only else list(AGENTS)
    unknown = [a for a in chosen if a not in AGENTS]
    if unknown:
        parser.error(f"unknown agents: {', '.join(unknown)}")
    gig = ns.gig or shutil.which("git-into-gsoc", path=str(Path(sys.executable).parent))
    gig = gig or shutil.which("git-into-gsoc")

    base = Path(tempfile.mkdtemp(prefix="gig-agents-"))
    results: list[Result] = []
    try:
        source = None if ns.remote else str(clean_copy(base / "source"))
        cache = base / "uv-cache"
        for agent in chosen:
            executables, plugin_check, setup_check = AGENTS[agent]
            if not any(shutil.which(e) for e in executables):
                results.append(
                    Result(agent, "-", "skipped", f"`{executables[0]}` is not installed")
                )
                continue
            routes: list[tuple[str, Check | None]] = [
                (FIRST_ROUTE.get(agent, "plugin"), plugin_check)
            ]
            if ns.setup:
                routes.append(("setup", setup_check))
            for route, check in routes:
                if check is None:
                    continue
                if route == "setup" and not gig:
                    results.append(Result(agent, route, "skipped", "git-into-gsoc not found"))
                    continue
                box = Sandbox(base, f"{agent}-{route}", cache)
                try:
                    arg = gig if route == "setup" else (source or remote_source(agent))
                    status, detail = check(box, arg)
                except (CheckFailed, OSError, KeyError, ValueError) as exc:
                    status, detail = "failed", str(exc)
                results.append(Result(agent, route, status, detail))
    finally:
        if ns.keep:
            print(f"kept {base}", file=sys.stderr)
        else:
            shutil.rmtree(base, ignore_errors=True)

    if ns.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            print(f"{r.agent:<12} {r.route:<7} {r.status:<10} {r.detail}")
    required = set(ns.require.split(",")) if ns.require else set()
    missing = [r.agent for r in results if r.status == "skipped" and r.agent in required]
    failed = [r for r in results if r.status == "failed"]
    if missing:
        print(f"required but not installed: {', '.join(missing)}", file=sys.stderr)
    return 1 if failed or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
