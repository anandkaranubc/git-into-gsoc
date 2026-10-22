"""Setup: skill copies, each assistant's config file, Codex's TOML, installed plugins, removal, and
what `doctor` finds."""

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
    unregister_codex_toml,
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
    entry = data["mcp_servers"][SERVER_NAME]
    assert (entry["command"], entry["args"]) == (CMD[0], ["mcp"])
    # Codex passes the server only HOME, PATH and a few more, and allows 10 s to start.
    assert {"GITHUB_TOKEN", "GH_TOKEN"} <= set(entry["env_vars"])
    assert entry["startup_timeout_sec"] >= 60
    assert register_codex_toml(path, CMD) == ("unchanged", "")
    assert register_codex_toml(path, ["/new/bin", "mcp"]) == ("updated", "")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["mcp_servers"][SERVER_NAME]["command"] == "/new/bin"
    assert path.read_text(encoding="utf-8").count("[mcp_servers.") == 2


# What `codex mcp add git-into-gsoc --env GIG_TARGET_YEAR=2027 -- ...` writes.
CODEX_ADD_WITH_ENV = (
    'model = "o3"\n\n'
    "[mcp_servers.git-into-gsoc]\n"
    'command = "uvx"\n'
    'args = ["git-into-gsoc", "mcp"]\n\n'
    "[mcp_servers.git-into-gsoc.env]\n"
    'GIG_TARGET_YEAR = "2027"\n\n'
    "[mcp_servers.other]\n"
    'command = "y"\n'
)


def test_codex_removal_takes_subtables_so_codex_still_starts(tmp_path: Path) -> None:
    # A leftover [mcp_servers.git-into-gsoc.env] without its table makes every Codex
    # command fail with "invalid transport".
    path = tmp_path / "config.toml"
    path.write_text(CODEX_ADD_WITH_ENV, encoding="utf-8")
    assert unregister_codex_toml(path) == ("removed", "")
    text = path.read_text(encoding="utf-8")
    assert "git-into-gsoc" not in text
    assert tomllib.loads(text) == {"model": "o3", "mcp_servers": {"other": {"command": "y"}}}


def test_codex_update_keeps_the_persons_own_subtables(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(CODEX_ADD_WITH_ENV, encoding="utf-8")
    assert register_codex_toml(path, CMD) == ("updated", "")
    entry = tomllib.loads(path.read_text(encoding="utf-8"))["mcp_servers"][SERVER_NAME]
    assert entry["command"] == CMD[0]
    assert entry["env"] == {"GIG_TARGET_YEAR": "2027"}


def test_codex_extra_keys_the_person_added_count_as_current(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    register_codex_toml(path, CMD)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('\n[mcp_servers.git-into-gsoc.tools.gsoc_log]\napproval_mode = "prompt"\n')
    assert register_codex_toml(path, CMD) == ("unchanged", "")


def test_codex_inline_definition_is_left_for_a_person(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    original = '[mcp_servers]\ngit-into-gsoc = { command = "old", args = ["mcp"] }\n'
    path.write_text(original, encoding="utf-8")
    action, note = register_codex_toml(path, CMD)
    assert action == "skipped" and "left as is" in note
    assert unregister_codex_toml(path)[0] == "skipped"
    assert path.read_text(encoding="utf-8") == original


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
    assert actions[("Shared (.agents)", "skill")] == "created"
    assert actions[("Cursor", "mcp")] == "created"
    assert actions[("Codex", "mcp")] == "created"
    assert actions[("Gemini CLI", "mcp")] == "created"
    assert actions[("Claude Code", "mcp")] == "skipped"  # user scope goes through `claude mcp add`
    assert any("claude mcp add" in step for step in plan.manual)
    # One shared copy serves Cursor, Codex, and Gemini CLI; Claude Code reads only its own.
    assert (home / ".agents/skills/git-into-gsoc/SKILL.md").is_file()
    assert (home / ".claude/skills/git-into-gsoc/SKILL.md").is_file()
    for folder in (".cursor/skills", ".codex/skills", ".gemini/skills"):
        assert not (home / folder).exists(), folder
    skill_rows = [c for c in plan.changes if c.kind == "skill"]
    assert len(skill_rows) == 2
    assert (home / ".cursor/mcp.json").is_file()
    assert {label for label, _ in installed_skills(home)} == {"Shared (.agents)", "Claude Code"}
    # doctor run from the home directory must not list every location twice
    assert len(installed_skills(home, home)) == len(installed_skills(home))
    assert len(registered_servers(home, home)) == len(registered_servers(home))
    assert {label for label, _ in registered_servers(home)} == {"Cursor", "Codex", "Gemini CLI"}
    # second run changes nothing
    run_setup(plan)
    assert {c.action for c in plan.changes if c.action != "skipped"} == {"unchanged"}


def _old_copy(folder: Path, name: str = SERVER_NAME) -> Path:
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8")
    return folder


def test_setup_removes_copies_older_versions_left_where_they_now_duplicate(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    old_cursor = _old_copy(home / ".cursor/skills/git-into-gsoc")
    old_codex = _old_copy(home / ".codex/skills/git-into-gsoc")
    someone_elses = _old_copy(home / ".gemini/skills/git-into-gsoc", name="another-skill")
    plan = plan_setup(
        scope="user",
        assistants=["cursor", "codex", "gemini"],
        home=home,
        project=None,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan, dry_run=True)
    assert old_cursor.exists() and old_codex.exists()  # a dry run touches nothing
    removed = {c.path for c in plan.changes if c.action == "removed"}
    assert removed == {old_cursor, old_codex}
    run_setup(plan)
    assert not old_cursor.exists() and not old_codex.exists()
    assert someone_elses.exists()  # not ours, so never touched
    notes = [c.note for c in plan.changes if c.action == "removed"]
    assert all("old location" in n and "~/.agents/skills" in n for n in notes)


def test_assistants_with_the_plugin_installed_are_left_to_the_plugin(tmp_path: Path) -> None:
    home = tmp_path / "home"
    plugins = home / ".claude/plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"git-into-gsoc@git-into-gsoc": [{"scope": "user"}]}}),
        encoding="utf-8",
    )
    (home / ".codex").mkdir()
    (home / ".codex/config.toml").write_text(
        '[plugins."git-into-gsoc@git-into-gsoc"]\nenabled = true\n', encoding="utf-8"
    )
    plan = plan_setup(
        scope="user",
        assistants=["claude-code", "codex", "cursor"],
        home=home,
        project=None,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan)
    rows = {(c.assistant, c.kind): c for c in plan.changes}
    assert rows[("Claude Code", "skill")].action == "skipped"
    assert "plugin" in rows[("Claude Code", "mcp")].note
    assert rows[("Codex", "mcp")].action == "skipped"
    assert rows[("Cursor", "mcp")].action == "created"
    assert not (home / ".claude/skills").exists()
    assert "mcp_servers" not in tomllib.loads((home / ".codex/config.toml").read_text())
    run_removal(plan)
    assert any("claude plugin uninstall" in step for step in plan.manual)
    assert any("codex plugin remove" in step for step in plan.manual)


def test_each_assistant_gets_the_entry_shape_it_reads(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".config/devin").mkdir(parents=True)
    plan = plan_setup(
        scope="user",
        assistants=["vscode", "gemini", "antigravity", "windsurf"],
        home=home,
        project=None,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan)
    copilot = json.loads((home / ".copilot/mcp-config.json").read_text())["mcpServers"]
    assert copilot[SERVER_NAME] == {
        "type": "local",
        "command": CMD[0],
        "args": ["mcp"],
        "tools": ["*"],
    }
    gemini = json.loads((home / ".gemini/settings.json").read_text())["mcpServers"][SERVER_NAME]
    # Gemini CLI hides token variables from servers unless they are named in env.
    assert gemini["env"]["GITHUB_TOKEN"] == "$GITHUB_TOKEN"
    antigravity = json.loads((home / ".gemini/config/mcp_config.json").read_text())
    assert antigravity["mcpServers"][SERVER_NAME]["command"] == CMD[0]
    assert (home / ".gemini/config/skills/git-into-gsoc/SKILL.md").is_file()
    # Windsurf is Devin Desktop now; its folder exists, so its file is used.
    assert (home / ".config/devin/mcp_config.json").is_file()
    assert not (home / ".codeium").exists()


def test_windsurf_before_the_rename_keeps_its_old_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".codeium/windsurf").mkdir(parents=True)
    plan = plan_setup(
        scope="user", assistants=["windsurf"], home=home, project=None, command=CMD, use_cli=False
    )
    run_setup(plan)
    assert (home / ".codeium/windsurf/mcp_config.json").is_file()
    assert {label for label, _ in registered_servers(home)} == {"Windsurf (Devin Desktop)"}


def test_project_scope_uses_each_assistants_project_file(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "repo"
    home.mkdir()
    project.mkdir()
    plan = plan_setup(
        scope="project",
        assistants=["vscode", "codex", "claude-code"],
        home=home,
        project=project,
        command=CMD,
        use_cli=False,
    )
    run_setup(plan)
    vscode = json.loads((project / ".vscode/mcp.json").read_text())
    assert vscode["servers"][SERVER_NAME]["type"] == "stdio"
    codex = tomllib.loads((project / ".codex/config.toml").read_text())
    assert codex["mcp_servers"][SERVER_NAME]["command"] == CMD[0]
    codex_row = next(c for c in plan.changes if c.assistant == "Codex" and c.kind == "mcp")
    assert "trusted" in codex_row.note
    assert (project / ".agents/skills/git-into-gsoc/SKILL.md").is_file()
    assert (project / ".claude/skills/git-into-gsoc/SKILL.md").is_file()
    assert not (project / ".github/skills").exists()


def test_codex_home_and_copilot_home_are_followed_only_for_the_real_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from git_into_gsoc.install.clients import resolve_home_path

    real = tmp_path / "real"
    real.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: real))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot-home"))
    assert resolve_home_path(real, ".codex/config.toml") == tmp_path / "codex-home/config.toml"
    assert resolve_home_path(real, ".copilot/mcp-config.json") == (
        tmp_path / "copilot-home/mcp-config.json"
    )
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    assert resolve_home_path(sandbox, ".codex/config.toml") == sandbox / ".codex/config.toml"


def test_a_bare_gemini_folder_from_antigravity_is_not_gemini_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import git_into_gsoc.install.clients as clients

    monkeypatch.setattr(clients, "find_program", lambda name: None)
    home = tmp_path / "home"
    (home / ".gemini/config").mkdir(parents=True)
    keys = {a.key for a in clients.detect_assistants(home)}
    assert "antigravity" in keys and "gemini" not in keys


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
    shared = home / ".agents/skills/git-into-gsoc"
    assert (shared / "SKILL.md").is_file()
    run_removal(plan, dry_run=True)
    assert (shared / "SKILL.md").is_file()  # dry run touches nothing
    run_removal(plan)
    actions = {(c.assistant, c.kind): c.action for c in plan.changes}
    assert actions[("Shared (.agents)", "skill")] == "removed"
    assert actions[("Cursor", "mcp")] == "removed"
    assert actions[("Codex", "mcp")] == "removed"
    assert not shared.exists()
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


def test_doctor_names_a_registered_command_that_cannot_start(tmp_path: Path) -> None:
    import sys

    from git_into_gsoc.cli import _command_problem

    gone = _command_problem({"command": str(tmp_path / "old-venv" / "git-into-gsoc")})
    assert gone and "no longer exists" in gone
    assert _command_problem({"command": sys.executable}) is None
    missing = _command_problem({"command": "surely-not-an-installed-program-xyz"})
    assert missing and "not installed" in missing
    assert _command_problem({}) == "no command is set"


def test_doctor_finds_a_registration_claude_mcp_add_made(tmp_path: Path) -> None:
    # Setup registers Claude Code through `claude mcp add`, which writes ~/.claude.json.
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"userID": "x", "mcpServers": {"git-into-gsoc": {"command": "gig", "args": ["mcp"]}}}
        ),
        encoding="utf-8",
    )
    assert ("Claude Code", tmp_path / ".claude.json") in registered_servers(tmp_path)
