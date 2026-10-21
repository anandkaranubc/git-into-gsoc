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
    assert len(server["description"]) <= 100  # the registry rejects longer descriptions
    package = server["packages"][0]
    assert package["registryType"] == "mcpb"
    assert "mcp" in package["identifier"] and len(package["fileSha256"]) == 64


def test_manifests_start_the_same_server() -> None:
    for name in (".claude-plugin/plugin.json", "gemini-extension.json"):
        entry = _load(name)["mcpServers"]["git-into-gsoc"]
        assert entry["command"] == "uvx"
        assert entry["args"][-2:] == ["git-into-gsoc", "mcp"]
        # Runs from the repository today; switch to the PyPI package at the first release.
        assert entry["args"][:2] == [
            "--from",
            "git+https://github.com/anandkaranubc/git-into-gsoc@main",
        ]
    plugin = _load(".claude-plugin/plugin.json")
    assert plugin["skills"] == ["./skills/git-into-gsoc"]
    assert (ROOT / "skills" / "git-into-gsoc" / "SKILL.md").is_file()
    marketplace = _load(".claude-plugin/marketplace.json")
    assert marketplace["plugins"][0]["name"] == plugin["name"]
    assert "mcp-name: io.github.anandkaranubc/git-into-gsoc" in (ROOT / "README.md").read_text()


def test_mcpb_bundle_builds_with_a_uv_manifest(tmp_path: Path) -> None:
    import subprocess
    import sys
    import zipfile

    out = tmp_path / "git-into-gsoc.mcpb"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_mcpb.py"), "--out", str(out)], check=True
    )
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json"))
    assert {"manifest.json", "pyproject.toml", "src/git_into_gsoc/mcp_server.py"} <= names
    assert "skills/git-into-gsoc/SKILL.md" in names
    assert not any("__pycache__" in n for n in names)
    assert manifest["manifest_version"] == "0.4"
    assert manifest["server"]["type"] == "uv"
    assert manifest["version"] == __version__
    assert manifest["server"]["mcp_config"]["args"][-2:] == ["git-into-gsoc", "mcp"]
