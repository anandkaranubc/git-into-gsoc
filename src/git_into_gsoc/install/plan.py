"""Build and execute a setup plan: which skill copies and MCP registrations to make."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from git_into_gsoc.install.clients import (
    ASSISTANTS,
    PLUGIN_REMOVAL,
    SERVER_NAME,
    SHARED_SKILLS,
    Assistant,
    Change,
    Scope,
    detect_assistants,
    installed_plugin,
    is_our_skill,
    register_codex_toml,
    register_json,
    register_via_cli,
    server_command,
    server_entry,
    skill_locations,
    unregister_codex_toml,
    unregister_json,
    user_config_path,
)
from git_into_gsoc.install.skill import InstallError, copy_skill, remove_skill, skill_source
from git_into_gsoc.programs import find_program


@dataclass
class SetupPlan:
    scope: Scope
    home: Path
    project: Path | None
    assistants: list[Assistant]
    command: list[str]
    install_skill: bool = True
    install_mcp: bool = True
    use_cli: bool = True  # let assistants with their own `mcp add` register themselves
    changes: list[Change] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)

    @property
    def root(self) -> Path:
        return self.project if self.scope == "project" and self.project else self.home


def plan_setup(
    *,
    scope: Scope,
    assistants: list[str] | None,
    home: Path,
    project: Path | None,
    install_skill: bool = True,
    install_mcp: bool = True,
    command: list[str] | None = None,
    use_cli: bool = True,
) -> SetupPlan:
    """Resolve which assistants to configure. ``assistants`` of None means auto-detect."""
    if scope == "project" and project is None:
        raise InstallError("Project scope needs a project directory.", hint="Pass --project-dir.")
    if assistants:
        unknown = [a for a in assistants if a not in ASSISTANTS and a != "all"]
        if unknown:
            raise InstallError(
                f"Unknown assistant(s): {', '.join(unknown)}",
                hint="Choose from: " + ", ".join(k for k in ASSISTANTS if k != "agents"),
            )
        chosen = (
            [a for k, a in ASSISTANTS.items() if k != "agents"]
            if "all" in assistants
            else [ASSISTANTS[a] for a in dict.fromkeys(assistants)]
        )
    else:
        chosen = detect_assistants(home)
    return SetupPlan(
        scope=scope,
        home=home,
        project=project,
        assistants=chosen,
        command=command or server_command(),
        install_skill=install_skill,
        install_mcp=install_mcp,
        use_cli=use_cli,
    )


def _plugin_for(plan: SetupPlan, assistant: Assistant) -> str | None:
    # Plugins are installed per person, so they only matter for the home-folder setup.
    return installed_plugin(assistant, plan.home) if plan.scope == "user" else None


def run_setup(plan: SetupPlan, *, dry_run: bool = False) -> SetupPlan:
    """Apply (or preview) the plan. Every outcome is recorded in ``plan.changes``."""
    plan.changes = []
    plan.manual = []
    plugins = {a.key: p for a in plan.assistants if (p := _plugin_for(plan, a))}
    if plan.install_skill:
        source = skill_source()
        written: dict[Path, int] = {}  # skill folder -> index of its row in plan.changes
        for assistant in [ASSISTANTS["agents"], *plan.assistants]:
            allowed = (
                assistant.project_scope_skill
                if plan.scope == "project"
                else assistant.user_scope_skill
            )
            dest, legacy = skill_locations(assistant, plan.scope, plan.root)
            for old in legacy:
                if old != dest and old.is_dir() and is_our_skill(old):
                    action = remove_skill(old, dry_run=dry_run)
                    note = f"old location; {assistant.label} reads {_rel(dest, plan)}"
                    plan.changes.append(Change(assistant.label, "skill", old, action, note))
            if not allowed:
                continue
            if assistant.key in plugins:
                plan.changes.append(
                    Change(
                        assistant.label,
                        "skill",
                        dest,
                        "skipped",
                        f"{plugins[assistant.key]} has it",
                    )
                )
                continue
            if dest in written:
                continue  # one shared copy serves every assistant that reads this folder
            action = copy_skill(source, dest, dry_run=dry_run)
            written[dest] = len(plan.changes)
            plan.changes.append(Change(assistant.label, "skill", dest, action))
    if plan.install_mcp:
        for assistant in plan.assistants:
            if assistant.key in plugins:
                note = f"{plugins[assistant.key]} brings its own server"
                plan.changes.append(Change(assistant.label, "mcp", plan.root, "skipped", note))
                continue
            plan.changes.append(_register(plan, assistant, dry_run=dry_run))
    return plan


def _rel(path: Path, plan: SetupPlan) -> str:
    for root, prefix in ((plan.project, "./"), (plan.home, "~/")):
        if root is None:
            continue
        try:
            return prefix + path.relative_to(root).as_posix()
        except ValueError:
            continue
    return str(path)


def _shared_readers(plan: SetupPlan) -> list[str]:
    """Assistants found on this machine, other than the ones being removed, that read
    the shared skill copy.

    `setup --remove -a claude-code` used to delete ~/.agents/skills, which Cursor and
    Codex still read (setup audit, 2026-10-29).
    """
    removing = {a.key for a in plan.assistants}
    return [
        a.label
        for a in detect_assistants(plan.home)
        if a.key not in removing and a.skill_dir_for(plan.scope) == SHARED_SKILLS
    ]


def run_removal(plan: SetupPlan, *, dry_run: bool = False) -> SetupPlan:
    """Undo what run_setup did for the same scope and assistants."""
    plan.changes = []
    plan.manual = []
    if plan.install_skill:
        removed: set[Path] = set()
        shared = skill_locations(ASSISTANTS["agents"], plan.scope, plan.root)[0]
        readers = _shared_readers(plan)
        for assistant in [ASSISTANTS["agents"], *plan.assistants]:
            dest, legacy = skill_locations(assistant, plan.scope, plan.root)
            for path in (dest, *legacy):
                if path in removed or (path != dest and not path.exists()):
                    continue
                removed.add(path)
                if path == shared and readers and path.exists():
                    note = f"still used by {', '.join(readers)}"
                    plan.changes.append(Change(assistant.label, "skill", path, "skipped", note))
                    continue
                plan.changes.append(
                    Change(assistant.label, "skill", path, remove_skill(path, dry_run=dry_run))
                )
    if plan.install_mcp:
        for assistant in plan.assistants:
            plan.changes.append(_unregister(plan, assistant, dry_run=dry_run))
    for assistant in plan.assistants:
        plugin = _plugin_for(plan, assistant)
        if plugin and assistant.key in PLUGIN_REMOVAL:
            plan.manual.append(
                f"{assistant.label}: {plugin} is installed; remove it with "
                f"`{PLUGIN_REMOVAL[assistant.key]}`"
            )
    return plan


def _config_path(plan: SetupPlan, assistant: Assistant) -> Path | None:
    target = assistant.mcp
    if target is None:
        return None
    if plan.scope == "project":
        return plan.root / target.project_path if target.project_path else None
    return user_config_path(target, plan.home)


def _unregister(plan: SetupPlan, assistant: Assistant, *, dry_run: bool) -> Change:
    target = assistant.mcp
    if target is None:
        return Change(assistant.label, "mcp", plan.root, "unchanged", "no MCP support")
    path = _config_path(plan, assistant)
    if path is None:
        if plan.scope == "user" and target.cli_remove and plan.use_cli:
            executable = find_program(target.cli_remove[0])
            if executable and plan.home.resolve() == Path.home().resolve():
                if dry_run:
                    return Change(assistant.label, "mcp", Path(executable), "removed", "via cli")
                ok, output = register_via_cli(executable, target.cli_remove[1])
                note = "via cli" if ok else f"cli reported: {output[-120:]}"
                return Change(
                    assistant.label, "mcp", Path(executable), "removed" if ok else "unchanged", note
                )
        plan.manual.append(f"{assistant.label}: remove the server named {SERVER_NAME} by hand")
        return Change(assistant.label, "mcp", plan.root, "skipped", "needs the manual step below")
    fmt = target.fmt_for(plan.scope)
    if fmt == "toml-codex":
        action, note = unregister_codex_toml(path, dry_run=dry_run)
    else:
        key = "servers" if fmt == "json-servers" else "mcpServers"
        action, note = unregister_json(path, key, dry_run=dry_run)
    return Change(assistant.label, "mcp", path, action, note)


def _register(plan: SetupPlan, assistant: Assistant, *, dry_run: bool) -> Change:
    target = assistant.mcp
    if target is None:
        return Change(assistant.label, "mcp", plan.root, "skipped", "no MCP support")
    path = _config_path(plan, assistant)
    if path is None:
        if plan.scope == "user" and target.cli and plan.use_cli:
            change = _register_via_cli(plan, assistant, target.cli, target.cli_check, dry_run)
            if change is not None:
                return change
        hint = target.manual_hint.format(command=" ".join(plan.command))
        if hint:
            plan.manual.append(f"{assistant.label}: {hint}")
        return Change(assistant.label, "mcp", plan.root, "skipped", "needs the manual step below")
    fmt = target.fmt_for(plan.scope)
    if fmt == "toml-codex":
        action, note = register_codex_toml(path, plan.command, dry_run=dry_run)
        by_hand = (
            f'[mcp_servers."{SERVER_NAME}"] with command = {json.dumps(plan.command[0])} '
            f"and args = {json.dumps(plan.command[1:])}"
        )
    else:
        key = "servers" if fmt == "json-servers" else "mcpServers"
        entry = server_entry(plan.command, fmt, target.style_for(plan.scope))
        action, note = register_json(path, key, entry, dry_run=dry_run)
        by_hand = f'inside "{key}": "{SERVER_NAME}": {json.dumps(entry)}'
    if action == "skipped":
        # The file was left alone (comments, invalid syntax); say exactly what to add.
        plan.manual.append(f"{assistant.label}: add this to {path}, {by_hand}")
    elif plan.scope == "project" and target.project_note:
        note = note or target.project_note
    return Change(assistant.label, "mcp", path, action, note)


def _register_via_cli(
    plan: SetupPlan,
    assistant: Assistant,
    cli: tuple[str, list[str]],
    check: tuple[str, list[str]] | None,
    dry_run: bool,
) -> Change | None:
    """Use the assistant's own CLI (e.g. `claude mcp add`) when it is installed.

    The CLI always writes to the real home directory, so when setup targets a
    different home (GIG_HOME in tests, demos, or sandboxes) it is skipped and
    the manual command is printed instead of mutating the user's real config.
    """
    executable = find_program(cli[0])
    if not executable or plan.home.resolve() != Path.home().resolve():
        return None
    where = Path(executable)
    if check and register_via_cli(executable, check[1])[0]:
        return Change(assistant.label, "mcp", where, "unchanged", "already registered")
    if dry_run:
        return Change(assistant.label, "mcp", where, "created", f"via {cli[0]} {cli[1][0]} add")
    ok, output = register_via_cli(executable, [*cli[1], *plan.command])
    if ok:
        return Change(assistant.label, "mcp", where, "created", f"via {cli[0]} mcp add")
    return Change(assistant.label, "mcp", where, "skipped", f"{cli[0]} mcp add failed: {output}")
