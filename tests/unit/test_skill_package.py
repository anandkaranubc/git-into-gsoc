"""The shipped skill: front matter, size, references, and its check script."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "git-into-gsoc"


def test_skill_md_exists_with_frontmatter() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: git-into-gsoc" in text
    assert "description:" in text
    assert "Never fabricate" in text or "never fabricate" in text.lower()


def test_skill_under_500_lines() -> None:
    lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 500


def test_references_present() -> None:
    for name in (
        "official-sources.md",
        "proposal.md",
        "quality-bar.md",
        "install.md",
        "examples.md",
    ):
        path = SKILL / "references" / name
        assert path.is_file(), f"missing {path}"
        assert path.stat().st_size > 100


def test_installer_exists_and_executable_bit_documented() -> None:
    installer = ROOT / "install.sh"
    assert installer.is_file()
    assert "git-into-gsoc" in installer.read_text(encoding="utf-8")
