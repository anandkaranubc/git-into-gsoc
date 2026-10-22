from __future__ import annotations

import json
from pathlib import Path

from git_into_gsoc import __version__

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


VERSIONED = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "gemini-extension.json")


def test_manifests_match_their_single_definition() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_integrations.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_manifest_versions_match_the_package() -> None:
    for name in VERSIONED:
        assert _load(name)["version"] == __version__, name
    server = _load("server.json")
    assert server["version"] == __version__
    # Committed, it lists the newest PyPI release; the release workflow pins the version
    # and puts that release's bundle first.
    (package,) = server["packages"]
    assert package["registryType"] == "pypi" and "version" not in package
    assert package["identifier"] == "git-into-gsoc"


def test_the_registry_entry_follows_the_official_schema() -> None:
    import jsonschema

    server = _load("server.json")
    schema_file = "mcp-server-" + server["$schema"].split("/")[-2] + ".schema.json"
    schema = _load(f"tests/fixtures/{schema_file}")  # a copy, as tests never use the network
    assert schema["$id"] == server["$schema"]
    jsonschema.validate(server, schema)
    # The registry only takes https icons, and the site must keep serving them.
    for icon in server["icons"]:
        assert icon["src"].startswith("https://anandkaranubc.github.io/git-into-gsoc/brand/")
        assert (ROOT / icon["src"].split("/git-into-gsoc/", 1)[1]).is_file()


def test_release_please_bumps_every_versioned_manifest() -> None:
    config = _load("release-please-config.json")["packages"]["."]["extra-files"]
    bumped = {e["path"] for e in config if e.get("jsonpath") == "$.version"}
    assert {*VERSIONED, "server.json"} <= bumped


def test_each_plugin_runs_the_server_from_its_own_installed_copy() -> None:
    # The server is then the same version as the skill beside it, updates arrive with
    # the plugin, and nothing is fetched from GitHub when the server starts.
    claude = _load(".claude-plugin/plugin.json")["mcpServers"]["git-into-gsoc"]
    codex = _load(".codex-plugin/plugin.json")["mcpServers"]["git-into-gsoc"]
    gemini = _load("gemini-extension.json")["mcpServers"]["git-into-gsoc"]
    assert claude["args"] == ["--from", "${CLAUDE_PLUGIN_ROOT}", "git-into-gsoc", "mcp"]
    assert gemini["args"] == ["--from", "${extensionPath}", "git-into-gsoc", "mcp"]
    assert codex["args"] == ["--from", ".", "git-into-gsoc", "mcp"] and codex["cwd"] == "."
    for entry in (claude, codex, gemini):
        assert entry["command"] == "uvx"
    # Codex passes servers only a few variables and allows 10 s to start by default.
    assert "GITHUB_TOKEN" in codex["env_vars"] and codex["startup_timeout_sec"] >= 60
    # Gemini CLI hides token variables unless they are named in env.
    assert gemini["env"]["GITHUB_TOKEN"] == "$GITHUB_TOKEN"


def test_plugins_find_the_skill_and_their_images() -> None:
    assert (ROOT / "skills" / "git-into-gsoc" / "SKILL.md").is_file()
    plugin = _load(".claude-plugin/plugin.json")
    codex = _load(".codex-plugin/plugin.json")
    assert codex["skills"] == "./skills/"
    for path in (plugin["icon"], codex["interface"]["logo"], codex["interface"]["composerIcon"]):
        assert (ROOT / path).is_file(), path
    marketplace = _load(".claude-plugin/marketplace.json")
    assert marketplace["plugins"][0]["name"] == plugin["name"]
    assert marketplace["plugins"][0]["source"] == "./"
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
    # Claude Desktop shows the icon, and its directory asks for support and privacy links.
    assert manifest["icon"] in names
    assert manifest["support"].endswith("/issues") and manifest["privacy_policies"]
