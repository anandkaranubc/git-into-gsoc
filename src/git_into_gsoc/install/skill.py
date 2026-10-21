"""Locate and copy the portable Agent Skill."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

from git_into_gsoc.errors import GigError

SKILL_NAME = "git-into-gsoc"


class InstallError(GigError):
    """Setup could not complete; the message says what to do instead."""


def skill_source() -> Path:
    """The skill shipped inside the wheel, or the repository copy for editable installs."""
    packaged = Path(str(resources.files("git_into_gsoc").joinpath("skill")))
    if (packaged / "SKILL.md").is_file():
        return packaged
    checkout = Path(__file__).resolve().parents[3] / "skills" / SKILL_NAME
    if (checkout / "SKILL.md").is_file():
        return checkout
    raise InstallError(
        "The git-into-gsoc skill files were not found in this installation.",
        hint="Reinstall the package, or run setup from a clone of the repository.",
    )


def skill_files(source: Path) -> list[Path]:
    return sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def copy_skill(source: Path, dest: Path, *, dry_run: bool = False) -> str:
    """Replace ``dest`` with a copy of ``source``. Returns created|updated|unchanged."""
    if dest.exists() and _same_tree(source, dest):
        return "unchanged"
    action = "updated" if dest.exists() else "created"
    if dry_run:
        return action
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return action


def remove_skill(dest: Path, *, dry_run: bool = False) -> str:
    """Delete a copied skill folder. Returns removed|unchanged."""
    if not dest.exists() and not dest.is_symlink():
        return "unchanged"
    if dry_run:
        return "removed"
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    else:
        shutil.rmtree(dest)
    return "removed"


def _same_tree(source: Path, dest: Path) -> bool:
    expected = {p.relative_to(source): p for p in skill_files(source)}
    try:
        actual = {p.relative_to(dest): p for p in skill_files(dest)}
    except OSError:
        return False
    if expected.keys() != actual.keys():
        return False
    return all(expected[k].read_bytes() == actual[k].read_bytes() for k in expected)
