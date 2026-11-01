"""The shipped skill: front matter and size. Links to its references are checked with the
docs, and the installer with the installers."""

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
    assert all(p.stat().st_size > 100 for p in (SKILL / "references").glob("*.md"))
