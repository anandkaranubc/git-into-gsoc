from __future__ import annotations

import json
from pathlib import Path

from git_into_gsoc import __version__

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_manifest_versions_match_the_package() -> None:
    assert _load(".claude-plugin/plugin.json")["version"] == __version__
    assert _load("gemini-extension.json")["version"] == __version__
    server = _load("server.json")
    assert server["version"] == __version__
    assert server["packages"][0]["version"] == __version__


def test_manifests_start_the_same_server() -> None:
    for name in (".claude-plugin/plugin.json", "gemini-extension.json"):
        entry = _load(name)["mcpServers"]["git-into-gsoc"]
        assert entry["command"] == "uvx"
        assert entry["args"][-2:] == ["git-into-gsoc", "mcp"]
        # Runs from the repository today; switch to the PyPI package at the first release.
        assert entry["args"][:2] == ["--from", "git+https://github.com/anandkaranubc/git-into-gsoc@main"]
    plugin = _load(".claude-plugin/plugin.json")
    assert plugin["skills"] == ["./skills/git-into-gsoc"]
    assert (ROOT / "skills" / "git-into-gsoc" / "SKILL.md").is_file()
    marketplace = _load(".claude-plugin/marketplace.json")
    assert marketplace["plugins"][0]["name"] == plugin["name"]
    assert "mcp-name: io.github.anandkaranubc/git-into-gsoc" in (ROOT / "README.md").read_text()
