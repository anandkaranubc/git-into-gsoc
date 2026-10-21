"""The installers must never install an unverified upload under our PyPI name."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OURS = "anandkaranubc/git-into-gsoc"
RELEASE = '{\n  "url": "x",\n  "tag_name": "v1.2.3",\n  "name": "v1.2.3"\n}\n'


def _provenance(repository: str) -> str:
    return (
        '{"attestation_bundles":[{"attestations":[],"publisher":{"environment":"release",'
        f'"kind":"GitHub","repository":"{repository}","workflow":"release.yml"}}}}],"version":1}}'
    )


def _check(tmp_path: Path, *, provenance: str | None, env: dict[str, str] | None = None) -> str:
    """Run install.sh's verified_pypi_spec with a stub curl that serves canned replies."""
    function = re.search(
        r"^verified_pypi_spec\(\) \{\n.*?^\}\n", (ROOT / "install.sh").read_text(), re.M | re.S
    )
    assert function, "verified_pypi_spec not found in install.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "release.json").write_text(RELEASE)
    if provenance is not None:
        (tmp_path / "provenance.json").write_text(provenance)
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{tmp_path}/calls"\n'
        'url="${@: -1}"\n'
        f'case "$url" in *releases/latest) cat "{tmp_path}/release.json" ;;\n'
        f'  *git_into_gsoc-1.2.3-py3-none-any.whl/provenance) cat "{tmp_path}/provenance.json" '
        "2>/dev/null || exit 22 ;;\n"
        "  *) exit 22 ;;\nesac\n"
    )
    curl.chmod(0o755)
    script = f'set -euo pipefail\nOWN_REPO="{OURS}"\n{function.group(0)}verified_pypi_spec\n'
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", **(env or {})},
        timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


posix_only = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash"), reason="needs bash"
)


@posix_only
def test_a_release_published_by_this_repository_is_installed_from_pypi(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=_provenance(OURS)) == "git-into-gsoc==1.2.3"


@posix_only
def test_an_upload_by_anyone_else_is_ignored(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=_provenance("squatter/git-into-gsoc")) == ""


@posix_only
def test_no_provenance_or_no_network_means_github(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=None) == ""


@posix_only
def test_an_explicit_source_skips_pypi_without_asking(tmp_path: Path) -> None:
    out = _check(tmp_path, provenance=_provenance(OURS), env={"GIG_REPO_URL": "/tmp/checkout"})
    assert out == ""
    assert not (tmp_path / "calls").exists()


@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_no_installer_installs_the_bare_package_name(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "pypi.org/integrity/git-into-gsoc/" in text
    # A bare `install ... git-into-gsoc` would take whatever is on PyPI under that name.
    assert not re.search(r'install[^\n]*["\s]git-into-gsoc["\s]*(?:2>|\||$)', text, re.M), name
