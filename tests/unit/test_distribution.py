"""Install links and launch commands come from one definition and decode correctly."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from git_into_gsoc.install import distribution as d

ROOT = Path(__file__).resolve().parents[2]


def test_remote_command_follows_the_stable_branch() -> None:
    assert d.remote_command() == [
        "uvx",
        "--from",
        "git+https://github.com/anandkaranubc/git-into-gsoc@stable",
        "git-into-gsoc",
        "mcp",
    ]


def test_cursor_link_decodes_to_the_remote_server() -> None:
    link = urlparse(d.cursor_install_link())
    assert (link.scheme, link.netloc, link.path) == ("https", "cursor.com", "/en/install-mcp")
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
