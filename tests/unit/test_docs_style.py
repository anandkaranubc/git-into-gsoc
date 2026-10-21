"""Keep project text readable for first-time contributors.

The style rule is simple: plain punctuation, no em dashes. Use a comma, a
colon, a period, or parentheses instead. Add a directory here once its files
follow the rule so the check protects it from then on.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKED = [
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".env.example",
    ".github",
    "docs",
    "pyproject.toml",
]
SUFFIXES = {".md", ".yml", ".yaml", ".toml", ".example", ".sh", ".json"}


def _text_files() -> list[Path]:
    files: list[Path] = []
    for entry in CHECKED:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.suffix in SUFFIXES)
    return files


def test_no_em_dashes_in_project_text() -> None:
    offenders = []
    for path in _text_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "\u2014" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        "Em dashes found; use a comma, colon, period, or parentheses instead:\n  "
        + "\n  ".join(offenders)
    )
