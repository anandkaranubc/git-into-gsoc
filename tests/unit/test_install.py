from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from git_into_gsoc.errors import GigError
from git_into_gsoc.install import copy_skill, plan_setup, run_removal, run_setup, skill_source
from git_into_gsoc.install.clients import (
    SERVER_NAME,
    installed_skills,
    register_codex_toml,
    register_json,
    registered_servers,
    server_entry,
)

CMD = ["/opt/gig/bin/git-into-gsoc", "mcp"]


def test_skill_source_has_frontmatter() -> None:
    text = (skill_source() / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n") and "name: git-into-gsoc" in text


def test_copy_skill_is_idempotent_and_replaces_stale_copies(tmp_path: Path) -> None:
    dest = tmp_path / "skills" / SERVER_NAME
    assert copy_skill(skill_source(), dest) == "created"
    assert (dest / "SKILL.md").is_file()
    assert copy_skill(skill_source(), dest) == "unchanged"
    (dest / "stale.md").write_text("old", encoding="utf-8")
    assert copy_skill(skill_source(), dest) == "updated"
    assert not (dest / "stale.md").exists()
    assert copy_skill(skill_source(), tmp_path / "other", dry_run=True) == "created"
    assert not (tmp_path / "other").exists()


def test_register_json_merges_and_backs_up(tmp_path: Path) -> None:
    path = tmp_path / ".cursor" / "mcp.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}), encoding="utf-8"
    )
    entry = server_entry(CMD, "json-mcpServers")
    assert register_json(path, "mcpServers", entry) == ("updated", "")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"][SERVER_NAME] == {"command": CMD[0], "args": ["mcp"]}
    assert path.with_name("mcp.json.bak").is_file()
    assert register_json(path, "mcpServers", entry) == ("unchanged", "")


def test_register_json_creates_missing_file_and_vscode_shape(tmp_path: Path) -> None:
    path = tmp_path / ".vscode" / "mcp.json"
    entry = server_entry(CMD, "json-servers")
    assert entry["type"] == "stdio"
    assert register_json(path, "servers", entry, dry_run=True) == ("created", "")
    assert not path.exists()
    assert register_json(path, "servers", entry) == ("created", "")
    assert json.loads(path.read_text(encoding="utf-8"))["servers"][SERVER_NAME]["type"] == "stdio"


def test_register_json_refuses_to_clobber_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text("{not json", encoding="utf-8")
    action, note = register_json(path, "mcpServers", server_entry(CMD, "json-mcpServers"))
    assert action == "skipped" and "not plain JSON" in note and "left as is" in note
    assert path.read_text(encoding="utf-8") == "{not json"


def test_register_codex_toml_appends_then_replaces(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "o3"\n\n[mcp_servers.other]\ncommand = "y"\n', encoding="utf-8")
    assert register_codex_toml(path, CMD) == ("updated", "")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["model"] == "o3"
    assert data["mcp_servers"]["other"]["command"] == "y"
    assert data["mcp_servers"][SERVER_NAME] == {"command": CMD[0], "args": ["mcp"]}
    assert register_codex_toml(path, CMD) == ("unchanged", "")
    assert register_codex_toml(path, ["/new/bin", "mcp"]) == ("updated", "")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["mcp_servers"][SERVER_NAME]["command"] == "/new/bin"
    assert path.read_text(encoding="utf-8").count("[mcp_servers.") == 2


def test_plan_rejects_unknown_assistant(tmp_path: Path) -> None:
    with pytest.raises(GigError, match="Unknown assistant"):
        plan_setup(scope="user", assistants=["emacs"], home=tmp_path, project=None, command=CMD)


def test_run_setup_user_scope_end_to_end(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    plan = plan_setup(
        scope="user",
        assistants=["cursor", "codex", "claude-code", "gemini"],
        home=home,
        project=None,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan)
    actions = {(c.assistant, c.kind): c.action for c in plan.changes}
    assert actions[("Portable (.agents)", "skill")] == "created"
    assert actions[("Cursor", "mcp")] == "created"
    assert actions[("Codex CLI", "mcp")] == "created"
    assert actions[("Gemini CLI", "mcp")] == "created"
    assert actions[("Claude Code", "mcp")] == "skipped"  # user scope goes through `claude mcp add`
    assert any("claude mcp add" in step for step in plan.manual)
    assert (home / ".claude/skills/git-into-gsoc/SKILL.md").is_file()
    assert (home / ".cursor/mcp.json").is_file()
    assert {label for label, _ in installed_skills(home)} >= {"Cursor", "Claude Code"}
    # doctor run from the home directory must not list every location twice
    assert len(installed_skills(home, home)) == len(installed_skills(home))
    assert len(registered_servers(home, home)) == len(registered_servers(home))
    assert {label for label, _ in registered_servers(home)} == {"Cursor", "Codex CLI", "Gemini CLI"}
    # second run changes nothing
    run_setup(plan)
    assert {c.action for c in plan.changes if c.action != "skipped"} == {"unchanged"}


def test_cli_registration_is_skipped_for_a_redirected_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GIG_HOME redirects file-based clients; `claude mcp add` would still hit the real home."""
    import git_into_gsoc.install.plan as plan_module

    calls: list[list[str]] = []
    monkeypatch.setattr(plan_module, "find_program", lambda name: f"/fake/bin/{name}")
    monkeypatch.setattr(
        plan_module, "register_via_cli", lambda exe, argv, **kw: calls.append(argv) or (True, "")
    )
    home = tmp_path / "home"
    home.mkdir()
    plan = plan_setup(
        scope="user", assistants=["claude-code"], home=home, project=None, command=CMD
    )
    run_setup(plan)
    assert calls == []
    assert any("claude mcp add" in step for step in plan.manual)


def test_run_setup_project_scope_writes_into_project(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    plan = plan_setup(
        scope="project",
        assistants=["claude-code", "vscode", "windsurf"],
        home=home,
        project=project,
        command=CMD,
    )
    run_setup(plan, dry_run=True)
    assert not (project / ".mcp.json").exists()
    run_setup(plan)
    assert json.loads((project / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"][
        SERVER_NAME
    ]["args"] == ["mcp"]
    assert (
        json.loads((project / ".vscode/mcp.json").read_text(encoding="utf-8"))["servers"][
            SERVER_NAME
        ]["type"]
        == "stdio"
    )
    assert (project / ".claude/skills/git-into-gsoc/SKILL.md").is_file()
    assert not (project / ".codeium").exists()  # windsurf has no project scope
    assert not any(home.iterdir())


def test_removal_undoes_setup_and_keeps_other_entries(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".cursor").mkdir()
    (home / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8"
    )
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_text('model = "o3"\n', encoding="utf-8")
    plan = plan_setup(
        scope="user",
        assistants=["cursor", "codex", "gemini"],
        home=home,
        project=None,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan)
    assert (home / ".cursor/skills/git-into-gsoc/SKILL.md").is_file()
    run_removal(plan, dry_run=True)
    assert (home / ".cursor/skills/git-into-gsoc/SKILL.md").is_file()  # dry run touches nothing
    run_removal(plan)
    actions = {(c.assistant, c.kind): c.action for c in plan.changes}
    assert actions[("Cursor", "skill")] == "removed" and actions[("Cursor", "mcp")] == "removed"
    assert actions[("Codex CLI", "mcp")] == "removed"
    assert not (home / ".cursor/skills/git-into-gsoc").exists()
    cursor = json.loads((home / ".cursor/mcp.json").read_text(encoding="utf-8"))
    assert cursor["mcpServers"] == {"other": {"command": "x"}}
    codex = tomllib.loads((home / ".codex/config.toml").read_text(encoding="utf-8"))
    assert codex == {"model": "o3"}
    assert registered_servers(home) == []
    run_removal(plan)
    assert {c.action for c in plan.changes} == {"unchanged"}


JSONC = '{\n  // my servers\n  "mcpServers": {\n    "other": {"command": "x"},\n  }\n}\n'


def test_register_json_reads_a_file_with_a_byte_order_mark(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b'\xef\xbb\xbf{"theme": "dark"}\n')
    entry = server_entry(CMD, "json-mcpServers")
    assert register_json(path, "mcpServers", entry) == ("updated", "")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"][SERVER_NAME] == entry


def test_a_config_with_comments_is_left_alone_with_a_manual_step(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    config = home / ".cursor/mcp.json"
    config.write_text(JSONC, encoding="utf-8")
    plan = plan_setup(
        scope="user", assistants=["cursor"], home=home, project=None, command=CMD, use_cli=False
    )
    run_setup(plan)
    change = next(c for c in plan.changes if c.kind == "mcp")
    assert change.action == "skipped" and "left as is" in change.note
    assert config.read_text(encoding="utf-8") == JSONC
    assert not (home / ".cursor/mcp.json.bak").exists()
    step = next(s for s in plan.manual if s.startswith("Cursor"))
    assert SERVER_NAME in step and json.dumps(CMD[0]) in step


def test_doctor_finds_a_server_added_by_hand_to_a_config_with_comments(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/mcp.json").write_text(
        JSONC.replace('"other"', f'"{SERVER_NAME}": {{"command": "a//b"}},\n    "other"'),
        encoding="utf-8",
    )
    assert [label for label, _ in registered_servers(tmp_path)] == ["Cursor"]


def test_config_writes_keep_symlinks_and_permissions(tmp_path: Path) -> None:
    import os
    import stat

    real = tmp_path / "dotfiles" / "mcp.json"
    real.parent.mkdir()
    real.write_text('{"mcpServers": {}}\n', encoding="utf-8")
    link = tmp_path / "mcp.json"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks need extra rights on this system")
    if os.name == "posix":
        real.chmod(0o600)
    assert register_json(link, "mcpServers", server_entry(CMD, "json-mcpServers"))[0] == "updated"
    assert link.is_symlink(), "the dotfiles link was replaced by a plain file"
    assert SERVER_NAME in json.loads(real.read_text(encoding="utf-8"))["mcpServers"]
    if os.name == "posix":
        assert stat.S_IMODE(real.stat().st_mode) == 0o600
    assert not list(real.parent.glob("*.tmp")), "a temporary file was left behind"
