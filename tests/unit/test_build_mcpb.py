"""The MCPB bundle must rebuild byte for byte: the registry pins its checksum."""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_mcpb.py"


def _fake_source(root: Path) -> None:
    (root / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "9.9.9"\n')
    (root / "src" / "git_into_gsoc").mkdir(parents=True)
    (root / "src" / "git_into_gsoc" / "__init__.py").write_text('__version__ = "9.9.9"\n')
    (root / "skills" / "git-into-gsoc" / "scripts").mkdir(parents=True)
    (root / "skills" / "git-into-gsoc" / "SKILL.md").write_text("# skill\n")
    script = root / "skills" / "git-into-gsoc" / "scripts" / "check.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)


def _build(root: Path, out: Path, env: dict[str, str] | None = None) -> bytes:
    subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--out", str(out)],
        check=True,
        env={**os.environ, **(env or {})},
    )
    return out.read_bytes()


def test_bundle_bytes_do_not_depend_on_file_times(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _fake_source(source)
    first = _build(source, tmp_path / "first.mcpb")
    for path in source.rglob("*"):
        os.utime(path, (0, 0))
    second = _build(source, tmp_path / "second.mcpb")
    assert first == second
    with zipfile.ZipFile(tmp_path / "first.mcpb") as zf:
        infos = zf.infolist()
    assert [i.filename for i in infos][:2] == ["manifest.json", "pyproject.toml"]
    assert {i.date_time for i in infos} == {(1980, 1, 1, 0, 0, 0)}
    modes = {i.filename: (i.external_attr >> 16) & 0o777 for i in infos}
    # Windows has no execute bit, so the script is a plain file there.
    assert modes["skills/git-into-gsoc/scripts/check.sh"] == (0o644 if os.name == "nt" else 0o755)
    assert modes["src/git_into_gsoc/__init__.py"] == 0o644


def test_source_date_epoch_sets_the_entry_time(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _fake_source(source)
    _build(source, tmp_path / "dated.mcpb", {"SOURCE_DATE_EPOCH": "1700000000"})
    with zipfile.ZipFile(tmp_path / "dated.mcpb") as zf:
        assert {i.date_time for i in zf.infolist()} == {(2023, 11, 14, 22, 13, 20)}
