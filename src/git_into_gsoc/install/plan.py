"""Build and execute a setup plan: which skill copies and MCP registrations to make."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from git_into_gsoc.install.clients import (
    ASSISTANTS,
    SERVER_NAME,
    Assistant,
    Change,
    Scope,
    detect_assistants,
    register_codex_toml,
    register_json,
    register_via_cli,
    server_command,
    server_entry,
)
from git_into_gsoc.install.skill import InstallError, copy_skill, skill_source


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


def run_setup(plan: SetupPlan, *, dry_run: bool = False) -> SetupPlan:
    """Apply (or preview) the plan. Every outcome is recorded in ``plan.changes``."""
    plan.changes = []
    plan.manual = []
    if plan.install_skill:
        source = skill_source()
        targets = [ASSISTANTS["agents"], *plan.assistants]
        for assistant in targets:
            allowed = (
                assistant.project_scope_skill
                if plan.scope == "project"
                else assistant.user_scope_skill
            )
            if not allowed:
                continue
            dest = plan.root / assistant.skill_dir / SERVER_NAME
            action = copy_skill(source, dest, dry_run=dry_run)
            plan.changes.append(Change(assistant.label, "skill", dest, action))
    if plan.install_mcp:
        for assistant in plan.assistants:
            plan.changes.append(_register(plan, assistant, dry_run=dry_run))
    return plan


def _register(plan: SetupPlan, assistant: Assistant, *, dry_run: bool) -> Change:
    target = assistant.mcp
    if target is None:
        return Change(assistant.label, "mcp", plan.root, "skipped", "no MCP support")
    rel = target.project_path if plan.scope == "project" else target.user_path
    if rel is None:
        if plan.scope == "user" and target.cli and plan.use_cli:
            change = _register_via_cli(plan, assistant, target.cli, target.cli_check, dry_run)
            if change is not None:
                return change
        hint = target.manual_hint.format(command=" ".join(plan.command))
        if hint:
            plan.manual.append(f"{assistant.label}: {hint}")
        return Change(assistant.label, "mcp", plan.root, "skipped", "needs the manual step below")
    path = plan.root / rel
    if target.fmt == "toml-codex":
        action, note = register_codex_toml(path, plan.command, dry_run=dry_run)
    else:
        key = "servers" if target.fmt == "json-servers" else "mcpServers"
        action, note = register_json(
            path, key, server_entry(plan.command, target.fmt), dry_run=dry_run
        )
    return Change(assistant.label, "mcp", path, action, note)


def _register_via_cli(
    plan: SetupPlan,
    assistant: Assistant,
    cli: tuple[str, list[str]],
    check: tuple[str, list[str]] | None,
    dry_run: bool,
) -> Change | None:
    """Use the assistant's own CLI (e.g. `claude mcp add`) when it is installed."""
    executable = shutil.which(cli[0])
    if not executable:
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
