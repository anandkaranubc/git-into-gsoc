"""Guards for the GitHub Actions workflows: pinned actions, explicit permissions, check names."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
# The main branch ruleset requires these check names; renaming a job blocks every merge.
REQUIRED_CHECKS = {
    "Quality",
    "Test (Python 3.11)",
    "Test (Python 3.13)",
    "Test (Python 3.14)",
    "Test (macOS, Python 3.12)",
    "Test (Windows, Python 3.12)",
    "Installer smoke",
    "Installer smoke (Windows)",
}


def test_workflows_are_found() -> None:
    assert {p.name for p in WORKFLOWS} >= {"ci.yml", "release.yml", "mcp-registry.yml"}


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_to_a_commit_with_a_version_comment(workflow: Path) -> None:
    # A tag or branch can be moved to new code; a commit cannot. The comment lets
    # Dependabot and people see which release the commit is.
    for line in workflow.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*(?:- )?uses:\s*(\S+)(.*)", line)
        if not match or match.group(1).startswith("./"):
            continue
        ref = match.group(1).partition("@")[2]
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{workflow.name}: pin {line.strip()!r}"
        assert re.fullmatch(r"\s+# v\d+(\.\d+)*", match.group(2)), f"{workflow.name}: {line!r}"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_sets_token_permissions(workflow: Path) -> None:
    # Without a top-level block the token gets the repository default, which can be write.
    assert re.search(r"^permissions:", workflow.read_text(encoding="utf-8"), re.M)


def test_required_check_names_still_exist() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    names = set(re.findall(r"^    name: (.+)$", text, re.M))
    names |= {f"Test ({label})" for label in re.findall(r'label: "([^"]+)"', text)}
    assert names >= REQUIRED_CHECKS
