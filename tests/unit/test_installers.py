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


WHEEL = (
    "https://github.com/anandkaranubc/git-into-gsoc/releases/download/v1.2.3/"
    "git_into_gsoc-1.2.3-py3-none-any.whl"
)
GIT = "git+https://github.com/anandkaranubc/git-into-gsoc"


def _check(
    tmp_path: Path,
    *,
    provenance: str | None,
    wheel: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    """Run install.sh's choose_spec with a stub curl that serves canned replies."""
    text = (ROOT / "install.sh").read_text()
    functions = []
    for name in (
        "latest_release_version",
        "verified_pypi_spec",
        "release_wheel_spec",
        "choose_spec",
    ):
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.M | re.S)
        assert found, f"{name} not found in install.sh"
        functions.append(found.group(0))
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
        f"  {WHEEL}) {'exit 0' if wheel else 'exit 22'} ;;\n"
        "  *) exit 22 ;;\nesac\n"
    )
    curl.chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f'OWN_REPO="{OURS}"\nREPO_URL="${{GIG_REPO_URL:-https://github.com/{OURS}}}"\n'
        'GIT_SPEC="git+${REPO_URL}"\nSPEC=""\n'
        'log() { :; }\ndie() { echo "died: $*" >&2; exit 1; }\n'
        + "".join(functions)
        + 'choose_spec\necho "$SPEC"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", **(env or {})},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


posix_only = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash"), reason="needs bash"
)


@posix_only
def test_a_release_published_by_this_repository_is_installed_from_pypi(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=_provenance(OURS)) == "git-into-gsoc==1.2.3"


@posix_only
def test_an_upload_by_anyone_else_is_ignored_for_the_release_wheel(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=_provenance("squatter/git-into-gsoc")) == WHEEL


@posix_only
def test_without_pypi_the_newest_release_wheel_is_used(tmp_path: Path) -> None:
    # A finished wheel needs neither Git nor a build step on the person's computer.
    assert _check(tmp_path, provenance=None) == WHEEL


@posix_only
def test_no_release_wheel_or_no_network_means_the_git_source(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=None, wheel=False) == GIT


@posix_only
def test_an_explicit_source_skips_pypi_and_releases_without_asking(tmp_path: Path) -> None:
    out = _check(tmp_path, provenance=_provenance(OURS), env={"GIG_REPO_URL": "/tmp/checkout"})
    assert out == "git+/tmp/checkout"
    assert not (tmp_path / "calls").exists()


@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_no_installer_installs_the_bare_package_name(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "pypi.org/integrity/git-into-gsoc/" in text
    # A bare `install ... git-into-gsoc` would take whatever is on PyPI under that name.
    assert not re.search(r'install[^\n]*["\s]git-into-gsoc["\s]*(?:2>|\||$)', text, re.M), name


def _offer_uv(
    tmp_path: Path,
    *,
    flag: bool,
    have_uv: bool = False,
    python: str = "python-that-does-not-exist",
) -> subprocess.CompletedProcess[str]:
    """Run install.sh's offer_uv on a PATH with no uv, pipx, or Python (unless asked)."""
    text = (ROOT / "install.sh").read_text()
    functions = []
    for name in ("python_ok", "python_version", "venv_ok", "python_hint", "ask_yes", "offer_uv"):
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.M | re.S)
        assert found, f"{name} not found in install.sh"
        functions.append(found.group(0))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    for tool in ("sh", "mkdir", "chmod"):
        found = shutil.which(tool)
        assert found
        (bin_dir / tool).symlink_to(found)
    # The stub "uv installer" puts a fake uv where the real one goes.
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{tmp_path}/calls"\n'
        "printf '%s\\n' 'mkdir -p \"$HOME/.local/bin\"' "
        '\'printf "#!/bin/sh\\\\n" > "$HOME/.local/bin/uv"\' '
        "'chmod +x \"$HOME/.local/bin/uv\"'\n"
    )
    curl.chmod(0o755)
    if have_uv:
        (bin_dir / "uv").write_text("#!/bin/sh\n")
        (bin_dir / "uv").chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f'OWN_REPO="{OURS}"\n'
        f"INSTALL_UV={1 if flag else 0}\nPYTHON={python}\n"
        'log() { :; }\ndie() { echo "died: $*" >&2; exit 1; }\n'
        + "".join(functions)
        + "offer_uv\necho uv-ready\n"
    )
    return subprocess.run(
        [shutil.which("bash") or "bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": str(bin_dir), "HOME": str(home)},
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # no terminal, so nothing can be asked
        timeout=30,
    )


@posix_only
def test_without_python_or_uv_and_no_terminal_the_installer_explains_and_stops(
    tmp_path: Path,
) -> None:
    result = _offer_uv(tmp_path, flag=False)
    assert result.returncode == 1
    # The flag is shown in the form that works through a pipe.
    assert "| bash -s -- --install-uv" in result.stderr
    assert "no uv, no pipx, and no Python" in result.stderr
    assert "Python 3.11 or newer" in result.stderr
    assert not (tmp_path / "calls").exists()


@posix_only
def test_install_uv_flag_installs_uv_from_astral_and_continues(tmp_path: Path) -> None:
    result = _offer_uv(tmp_path, flag=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("uv-ready")
    assert "https://astral.sh/uv/install.sh" in (tmp_path / "calls").read_text()


@posix_only
def test_an_existing_uv_is_used_without_offering_anything(tmp_path: Path) -> None:
    result = _offer_uv(tmp_path, flag=False, have_uv=True)
    assert result.returncode == 0 and result.stdout.strip() == "uv-ready"
    assert not (tmp_path / "calls").exists()


def _fake_python(bin_dir: Path, *, version: str = "3.12.3", has_venv: bool = True) -> str:
    """A python3 that reports a version and can or cannot import venv and ensurepip."""
    major, minor = (int(part) for part in version.split(".")[:2])
    script = bin_dir / "python3"
    script.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"import ensurepip, venv"*) exit {0 if has_venv else 1} ;;\n'
        f'  *platform.python_version*) echo "{version}" ;;\n'
        f"  *version_info*) exit {0 if (major, minor) >= (3, 11) else 1} ;;\n"
        "esac\n"
    )
    script.chmod(0o755)
    return str(script)


@posix_only
def test_a_python_without_venv_counts_as_missing_and_says_why(tmp_path: Path) -> None:
    # Ubuntu, Debian, and WSL ship python3 without venv; offering uv is the way through.
    bin_dir = tmp_path / "pybin"
    bin_dir.mkdir()
    python = _fake_python(bin_dir, has_venv=False)
    result = _offer_uv(tmp_path, flag=False, python=python)
    assert result.returncode == 1
    assert "Python 3.12.3, but without its venv module" in result.stderr


@posix_only
def test_install_uv_works_when_python_has_no_venv(tmp_path: Path) -> None:
    bin_dir = tmp_path / "pybin"
    bin_dir.mkdir()
    result = _offer_uv(tmp_path, flag=True, python=_fake_python(bin_dir, has_venv=False))
    assert result.returncode == 0, result.stderr
    assert "https://astral.sh/uv/install.sh" in (tmp_path / "calls").read_text()


@posix_only
def test_an_old_python_is_named(tmp_path: Path) -> None:
    bin_dir = tmp_path / "pybin"
    bin_dir.mkdir()
    result = _offer_uv(tmp_path, flag=False, python=_fake_python(bin_dir, version="3.10.12"))
    assert result.returncode == 1
    assert "Python 3.10.12, which is older than 3.11" in result.stderr
    assert "too old to update in place" in result.stderr


def _function(name: str) -> str:
    found = re.search(
        rf"^{name}\(\) \{{\n.*?^\}}\n", (ROOT / "install.sh").read_text(), re.M | re.S
    )
    assert found, f"{name} not found in install.sh"
    return found.group(0)


@posix_only
def test_release_version_comes_from_the_release_page_when_the_api_is_blocked(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        'url="${@: -1}"\n'
        'case "$url" in\n'
        "  https://api.github.com/*) exit 22 ;;\n"
        "  https://github.com/*/releases/latest)\n"
        f'    printf "%s" "https://github.com/{OURS}/releases/tag/v1.2.3" ;;\n'
        "  *) exit 22 ;;\nesac\n"
    )
    curl.chmod(0o755)
    script = (
        f'set -euo pipefail\nOWN_REPO="{OURS}"\n'
        + _function("latest_release_version")
        + "latest_release_version\n"
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.2.3"


def _path_advice(bin_dir: str, *, path: str, shell: str) -> str:
    script = (
        "set -euo pipefail\n"
        + _function("shell_rc")
        + _function("on_path")
        + _function("path_advice")
        + f'GIG_BIN="{bin_dir}/git-into-gsoc"\npath_advice "{bin_dir}"\n'
    )
    result = subprocess.run(
        [shutil.which("bash") or "bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": path, "HOME": "/home/newbie", "SHELL": shell},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@posix_only
def test_a_folder_missing_from_path_gets_the_exact_line_to_add() -> None:
    out = _path_advice("/home/newbie/.local/bin", path="/usr/bin:/bin", shell="/bin/zsh")
    assert "echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.zshrc" in out
    assert "/home/newbie/.local/bin/git-into-gsoc" in out
    fish = _path_advice("/home/newbie/.local/bin", path="/usr/bin:/bin", shell="/usr/bin/fish")
    assert "fish_add_path $HOME/.local/bin" in fish


@posix_only
def test_a_folder_already_on_path_needs_no_advice() -> None:
    out = _path_advice(
        "/home/newbie/.local/bin", path="/usr/bin:/home/newbie/.local/bin", shell="/bin/bash"
    )
    assert out == ""
