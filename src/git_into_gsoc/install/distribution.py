"""How git-into-gsoc is described and launched on every platform, defined once.

The plugin manifests, the Gemini extension, the MCP registry entry, the example
configs, and the one-click install links in the docs are all written from these
values by ``scripts/sync_integrations.py``. A test runs that script in check
mode, so a committed file cannot drift from what is defined here.

Two kinds of launch command exist:

* A plugin or extension runs the server from its own installed copy
  (``uvx --from <plugin folder>``). The server is then always the same version
  as the skill next to it, updates arrive with the plugin, and nothing is
  downloaded from GitHub when the server starts.
* A one-click link or a copied config has no installed copy, so it runs the code
  on GitHub's ``main`` branch, which changes only through reviewed pull requests
  that pass CI. A branch that follows releases would need a token allowed to
  push workflow changes, which the built-in Actions token is not.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote, urlencode

REPO = "anandkaranubc/git-into-gsoc"
REPO_URL = f"https://github.com/{REPO}"
SERVER_NAME = "git-into-gsoc"
REGISTRY_NAME = "io.github.anandkaranubc/git-into-gsoc"
REMOTE_REF = "main"
AUTHOR = {"name": "git-into-gsoc contributors", "url": REPO_URL}
LICENSE = "MIT"
KEYWORDS = ["gsoc", "google-summer-of-code", "open-source", "onboarding", "github", "mcp"]

DESCRIPTION = (
    "Evidence-based preparation for Google Summer of Code: find organizations, repositories "
    "and free beginner issues, get oriented in a codebase, and prepare a proposal, with an "
    "Agent Skill and an MCP server."
)
SHORT_DESCRIPTION = (
    "Evidence-based preparation for Google Summer of Code: organizations, repositories, "
    "free beginner issues, orientation, and proposals."
)
# The MCP registry rejects descriptions over 100 characters.
REGISTRY_DESCRIPTION = (
    "Evidence-based GSoC preparation: organizations, repositories, free beginner issues, proposals."
)

# Token variables the server reads. Some hosts hide them from MCP servers unless they
# are named: Gemini CLI removes anything that looks like a token, and Codex passes on
# only HOME, PATH, and a few more. The server also falls back to `gh auth token`.
TOKEN_VARS = ("GIG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
PROXY_VARS = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")

# How each host names the folder a plugin or extension was installed into.
CLAUDE_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"  # also read by Cursor, Copilot, VS Code, Devin
GEMINI_EXTENSION_PATH = "${extensionPath}"  # also rewritten by Antigravity's converter


def plugin_command(root: str) -> list[str]:
    """Run the server from a plugin's own copy, so it matches the plugin's version."""
    return ["uvx", "--from", root, SERVER_NAME, "mcp"]


def remote_source(ref: str = REMOTE_REF) -> str:
    return f"git+{REPO_URL}@{ref}"


def remote_command(ref: str = REMOTE_REF) -> list[str]:
    """Run the server straight from GitHub. Needs uv and Git, nothing else."""
    return ["uvx", "--from", remote_source(ref), SERVER_NAME, "mcp"]


def stdio_entry(command: list[str], **extra: Any) -> dict[str, Any]:
    return {"command": command[0], "args": command[1:], **extra}


# ------------------------------------------------------------------ install links


def _compact(data: object) -> str:
    return json.dumps(data, separators=(",", ":"))


def cursor_install_link(command: list[str] | None = None) -> str:
    """Cursor's web install link. GitHub strips cursor:// links, so READMEs need this form.

    Cursor decodes ``config`` as base64 JSON, asks the person to confirm, and adds the
    server to ~/.cursor/mcp.json.
    """
    config = base64.b64encode(_compact(stdio_entry(command or remote_command())).encode())
    query = urlencode({"name": SERVER_NAME, "config": config.decode()})
    return f"https://cursor.com/en/install-mcp?{query}"


def vscode_install_link(command: list[str] | None = None, *, insiders: bool = False) -> str:
    """VS Code's web install link; it redirects to vscode:mcp/install and asks to confirm.

    No ``inputs`` are used on purpose: servers that ask for input are not passed on to
    VS Code's Copilot sessions.
    """
    config = {"type": "stdio", **stdio_entry(command or remote_command())}
    query = f"name={SERVER_NAME}&config={quote(_compact(config), safe='')}"
    if insiders:
        query += "&quality=insiders"
    return f"https://vscode.dev/redirect/mcp/install?{query}"


def kiro_install_link(command: list[str] | None = None) -> str:
    """Kiro's web install link; ``config`` is the server as URL-encoded JSON."""
    config = quote(_compact(stdio_entry(command or remote_command())), safe="")
    return f"https://kiro.dev/launch/mcp/add?name={SERVER_NAME}&config={config}"


def install_badges() -> str:
    """The one-click install buttons shown in the README and the assistant guide."""
    shield = "https://img.shields.io/badge/{0}-{1}-{2}?style=flat-square&logo={3}&logoColor=white"
    buttons = [
        (
            "Add to Cursor",
            "https://cursor.com/deeplink/mcp-install-dark.svg",
            cursor_install_link(),
        ),
        (
            "Install in VS Code",
            shield.format("VS_Code", "Install_server", "0098FF", "visualstudiocode"),
            vscode_install_link(),
        ),
        (
            "Install in VS Code Insiders",
            shield.format("VS_Code_Insiders", "Install_server", "24bfa5", "visualstudiocode"),
            vscode_install_link(insiders=True),
        ),
        ("Add to Kiro", shield.format("Kiro", "Add_server", "7138CC", "kiro"), kiro_install_link()),
    ]
    return " ".join(f"[![{alt}]({image})]({link})" for alt, image, link in buttons)


def goose_install_link(command: list[str] | None = None) -> str:
    """Goose's extension install link (goose://extension?cmd=...&arg=...)."""
    cmd = command or remote_command()
    params = [("cmd", cmd[0]), *(("arg", a) for a in cmd[1:])]
    params += [
        ("id", SERVER_NAME),
        ("name", SERVER_NAME),
        ("description", "Google Summer of Code preparation"),
    ]
    return "goose://extension?" + urlencode(params, quote_via=quote)


# ---------------------------------------------------------------------- manifests
#
# Several hosts read another host's manifest, so a few files cover many tools:
#   .claude-plugin/  Claude Code, Cursor, Copilot CLI, VS Code agent plugins, Devin,
#                    Factory Droid, and Antigravity's converter
#   .codex-plugin/   Codex (read before .claude-plugin; only it can carry Codex's
#                    start timeout and the variables to pass on)
#   gemini-extension.json  Gemini CLI, Qwen Code, and Antigravity's converter
# Every one of them finds the skill in the default skills/ folder.

ICON = "./brand/logo/mark-tile-512.png"
BRAND_COLOR = "#7A5AF8"
SUPPORT_URL = f"{REPO_URL}/issues"
DOCS_URL = f"{REPO_URL}/blob/main/docs/assistants.md"
PRIVACY_URL = f"{REPO_URL}/blob/main/docs/privacy.md"


def claude_plugin(version: str) -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "version": version,
        "description": DESCRIPTION,
        "author": AUTHOR,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "documentationUrl": DOCS_URL,
        "supportUrl": SUPPORT_URL,
        "privacyPolicyUrl": PRIVACY_URL,
        "icon": ICON,
        "license": LICENSE,
        "keywords": KEYWORDS,
        "mcpServers": {SERVER_NAME: stdio_entry(plugin_command(CLAUDE_PLUGIN_ROOT))},
    }


def claude_marketplace() -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "description": "The git-into-gsoc plugin: Google Summer of Code preparation with real data.",
        "owner": {"name": AUTHOR["name"], "url": REPO_URL},
        "plugins": [{"name": SERVER_NAME, "source": "./", "description": DESCRIPTION}],
    }


def codex_plugin(version: str) -> dict[str, Any]:
    entry = stdio_entry(
        # Codex starts a plugin's servers in the plugin's own folder when cwd is ".".
        plugin_command("."),
        cwd=".",
        env_vars=[*TOKEN_VARS, *PROXY_VARS],
        # The first start builds the package and may download dependencies.
        startup_timeout_sec=120,
    )
    return {
        "name": SERVER_NAME,
        "version": version,
        "description": DESCRIPTION,
        "author": AUTHOR,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": LICENSE,
        "keywords": KEYWORDS,
        "skills": "./skills/",
        "mcpServers": {SERVER_NAME: entry},
        "interface": {
            "displayName": SERVER_NAME,
            "shortDescription": "Prepare for Google Summer of Code one step at a time",
            "longDescription": (
                "Find mentoring organizations, pick a repository and a free beginner issue, "
                "get oriented in a codebase, and prepare a proposal. Uses live data and "
                "official GSoC pages, and never invents organizations, issues, or deadlines."
            ),
            "developerName": AUTHOR["name"],
            "category": "Developer Tools",
            "capabilities": ["Interactive", "Read", "Write"],
            "websiteURL": REPO_URL,
            "privacyPolicyURL": PRIVACY_URL,
            "defaultPrompt": [
                "Help me get started with Google Summer of Code",
                "Find GSoC organizations that use Python",
                "Find a free beginner issue I could work on",
            ],
            "brandColor": BRAND_COLOR,
            "composerIcon": "./brand/logo/mark-tile.svg",
            "logo": ICON,
        },
    }


def gemini_extension(version: str) -> dict[str, Any]:
    # Gemini CLI removes token variables before starting a server unless they are
    # named here; it fills each from the full environment ("" when unset).
    env = {name: f"${name}" for name in TOKEN_VARS}
    return {
        "name": SERVER_NAME,
        "version": version,
        "description": SHORT_DESCRIPTION,
        "mcpServers": {SERVER_NAME: stdio_entry(plugin_command(GEMINI_EXTENSION_PATH), env=env)},
    }


def manifests(version: str) -> dict[str, dict[str, Any]]:
    """Every generated manifest, by path relative to the repository root."""
    return {
        ".claude-plugin/plugin.json": claude_plugin(version),
        ".claude-plugin/marketplace.json": claude_marketplace(),
        ".codex-plugin/plugin.json": codex_plugin(version),
        "gemini-extension.json": gemini_extension(version),
    }
