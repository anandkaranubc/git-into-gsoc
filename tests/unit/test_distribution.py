"""Install links and launch commands come from one definition and decode correctly."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from git_into_gsoc.install import distribution as d

ROOT = Path(__file__).resolve().parents[2]


def test_remote_command_runs_the_newest_pypi_release() -> None:
    assert d.remote_command() == ["uvx", "git-into-gsoc@latest", "mcp"]


def test_cursor_link_decodes_to_the_remote_server() -> None:
    link = urlparse(d.cursor_install_link())
    assert (link.scheme, link.netloc, link.path) == ("https", "cursor.com", "/install-mcp")
    query = parse_qs(link.query)
    assert query["name"] == ["git-into-gsoc"]
    config = json.loads(base64.b64decode(query["config"][0]))
    assert config == {"command": "uvx", "args": d.remote_command()[1:]}


def test_vscode_links_decode_to_a_stdio_server_without_inputs() -> None:
    for insiders in (False, True):
        link = urlparse(d.vscode_install_link(insiders=insiders))
        assert (link.netloc, link.path) == ("vscode.dev", "/redirect/mcp/install")
        query = parse_qs(link.query)
        config = json.loads(query["config"][0])
        assert config == {"type": "stdio", "command": "uvx", "args": d.remote_command()[1:]}
        assert "inputs" not in query  # inputs keep a server out of Copilot sessions
        assert (query.get("quality") == ["insiders"]) is insiders


def test_goose_link_repeats_arg_for_each_argument() -> None:
    link = d.goose_install_link()
    assert link.startswith("goose://extension?cmd=uvx&")
    args = [unquote(p[4:]) for p in link.split("?", 1)[1].split("&") if p.startswith("arg=")]
    assert args == d.remote_command()[1:]


def test_the_smoke_check_talks_to_the_real_server(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "mcp_smoke.py"),
            "--json",
            "--",
            sys.executable,
            "-m",
            "git_into_gsoc",
            "mcp",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["server"] == "git-into-gsoc" and summary["tools"] >= 20
    assert summary["instructions"] is True


def test_kiro_link_decodes_to_the_remote_server() -> None:
    link = urlparse(d.kiro_install_link())
    assert (link.netloc, link.path) == ("kiro.dev", "/launch/mcp/add")
    config = json.loads(parse_qs(link.query)["config"][0])
    assert config == {"command": "uvx", "args": d.remote_command()[1:]}


def test_visual_studio_link_decodes_to_the_remote_server() -> None:
    link = urlparse(d.visual_studio_install_link())
    assert (link.scheme, link.netloc, link.path) == ("https", "vs-open.link", "/mcp-install")
    config = json.loads(unquote(link.query))
    assert config == {
        "name": "git-into-gsoc",
        "type": "stdio",
        "command": "uvx",
        "args": d.remote_command()[1:],
    }


def test_claude_desktop_link_downloads_the_newest_bundle() -> None:
    link = d.claude_desktop_bundle_link()
    assert link.endswith("/releases/latest/download/git-into-gsoc.mcpb")
    # The release workflow attaches the bundle under exactly this name.
    workflow = (ROOT / ".github" / "workflows" / "mcp-registry.yml").read_text(encoding="utf-8")
    assert "dist/git-into-gsoc.mcpb --clobber" in workflow


def test_the_readme_buttons_carry_every_link() -> None:
    badges = d.install_badges()
    for link in (
        d.cursor_install_link(),
        d.vscode_install_link(),
        d.vscode_install_link(insiders=True),
        d.kiro_install_link(),
        d.visual_studio_install_link(),
        d.claude_desktop_bundle_link(),
    ):
        assert f"]({link})" in badges
    for page in ("README.md", "docs/assistants.md"):
        assert badges in (ROOT / page).read_text(encoding="utf-8"), page
    # GitHub removes links to app schemes such as cursor:// from rendered Markdown.
    for target in re.findall(r"\]\(([^)]+)\)(?: |$)", badges):
        assert target.startswith("https://"), target
