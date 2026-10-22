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
    release: bool = True,
    env: dict[str, str] | None = None,
    every: bool = False,
) -> str:
    """Run install.sh's choose_spec with a stub curl that serves canned replies.

    Returns the first source, or with ``every`` all sources to try, one per line.
    """
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
    if release:
        (tmp_path / "release.json").write_text(RELEASE)
    if provenance is not None:
        (tmp_path / "provenance.json").write_text(provenance)
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{tmp_path}/calls"\n'
        'url="${@: -1}"\n'
        f'case "$url" in *releases/latest) cat "{tmp_path}/release.json" 2>/dev/null || exit 22 ;;\n'
        f'  *git_into_gsoc-1.2.3-py3-none-any.whl/provenance) cat "{tmp_path}/provenance.json" '
        "2>/dev/null || exit 22 ;;\n"
        f"  {WHEEL}) {'exit 0' if wheel else 'exit 22'} ;;\n"
        "  *) exit 22 ;;\nesac\n"
    )
    curl.chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f'OWN_REPO="{OURS}"\nREPO_URL="${{GIG_REPO_URL:-https://github.com/{OURS}}}"\n'
        'GIT_SPEC="git+${REPO_URL}"\nSPEC=""\nSPECS=()\n'
        'log() { :; }\ndie() { echo "died: $*" >&2; exit 1; }\n'
        + "".join(functions)
        + (
            "choose_spec\nprintf '%s\\n' \"${SPECS[@]}\"\n"
            if every
            else 'choose_spec\necho "$SPEC"\n'
        )
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
def test_a_release_without_its_wheel_yet_means_the_source_at_its_tag(tmp_path: Path) -> None:
    # A release appears a little before its wheel is attached. The newest commit could
    # hold changes merged since, which would then run under the release's version number.
    assert _check(tmp_path, provenance=None, wheel=False) == f"{GIT}@v1.2.3"


@posix_only
def test_no_network_means_the_newest_git_source(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=None, wheel=False, release=False) == GIT


@posix_only
def test_each_later_source_is_kept_as_a_fallback(tmp_path: Path) -> None:
    assert _check(tmp_path, provenance=_provenance(OURS), every=True).splitlines() == [
        "git-into-gsoc==1.2.3",
        WHEEL,
        f"{GIT}@v1.2.3",
    ]


def test_the_powershell_installer_pins_the_source_to_the_release() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert '$gitSpec = "git+${RepoUrl}@v$version"' in text
    assert "$specs += $gitSpec" in text


# Loads the source-choosing functions from install.ps1 without running the installer, and
# fakes the web: FAKE_RELEASE, FAKE_PYPI and FAKE_WHEEL say which lookups succeed.
_PS_SPECS = r"""
$ErrorActionPreference = "Stop"
$OwnRepo = "anandkaranubc/git-into-gsoc"
$RepoUrl = if ($env:GIG_REPO_URL) { $env:GIG_REPO_URL } else { "https://github.com/$OwnRepo" }
function Log($msg) { Write-Host "LOG $msg" }
$names = "Get-LatestReleaseVersion", "Get-VerifiedPyPISpec", "Get-ReleaseWheelSpec", "Get-InstallSpecs"
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$null, [ref]$null)
$found = $ast.FindAll({ param($n)
  $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in $names }, $true)
foreach ($f in $found) { . ([scriptblock]::Create($f.Extent.Text)) }
function git { }
function Invoke-RestMethod($Uri, $TimeoutSec) {
  if ($env:FAKE_RELEASE -and $Uri -like "*/releases/latest") { return @{ tag_name = "v1.2.3" } }
  if ($env:FAKE_PYPI -and $Uri -like "*/provenance") {
    return @{ attestation_bundles = @(@{ publisher = @{ kind = "GitHub"; repository = $OwnRepo } }) }
  }
  throw "404"
}
function Invoke-WebRequest($Uri, $Method, [switch]$UseBasicParsing, $TimeoutSec) {
  if ($env:FAKE_WHEEL -and $Uri -like "*/releases/download/*") { return @{} }
  throw "404"
}
foreach ($spec in @(Get-InstallSpecs)) { Write-Output "SPEC $spec" }
"""


def _ps_specs(tmp_path: Path, **fake: str) -> tuple[list[str], list[str]]:
    """Run install.ps1's Get-InstallSpecs in PowerShell; return its sources and log lines."""
    script = tmp_path / "specs.ps1"
    script.write_text(_PS_SPECS, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIG_", "FAKE_"))}
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script), str(ROOT / "install.ps1")],
        capture_output=True,
        text=True,
        env={**env, **fake},
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    return (
        [line[5:] for line in lines if line.startswith("SPEC ")],
        [line[4:] for line in lines if line.startswith("LOG ")],
    )


needs_pwsh = pytest.mark.skipif(not shutil.which("pwsh"), reason="needs PowerShell 7 (pwsh)")


@needs_pwsh
def test_powershell_builds_the_source_at_the_tag_when_the_release_has_no_wheel_yet(
    tmp_path: Path,
) -> None:
    specs, log = _ps_specs(tmp_path, FAKE_RELEASE="1")
    assert specs == [f"{GIT}@v1.2.3"]
    assert f"Using the source on GitHub ({GIT[4:]}, release v1.2.3)" in log
    assert not any("Could not look up" in line for line in log)


@needs_pwsh
def test_powershell_keeps_the_same_order_of_sources_as_install_sh(tmp_path: Path) -> None:
    specs, _ = _ps_specs(tmp_path, FAKE_RELEASE="1", FAKE_PYPI="1", FAKE_WHEEL="1")
    assert specs == ["git-into-gsoc==1.2.3", WHEEL, f"{GIT}@v1.2.3"]


@needs_pwsh
def test_powershell_without_network_builds_the_newest_source(tmp_path: Path) -> None:
    specs, log = _ps_specs(tmp_path)
    assert specs == [GIT]
    assert any("Could not look up the newest release" in line for line in log)


def _install_first(tmp_path: Path, *, failing: str) -> subprocess.CompletedProcess[str]:
    """Run install.sh's install_first with a stub installer that fails on some sources."""
    stub = tmp_path / "stub-install"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$1" >> "{tmp_path}/tried"\n'
        f'case "$1" in {failing}) exit 1 ;; esac\n'
    )
    stub.chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f'SPECS=("git-into-gsoc==1.2.3" "{WHEEL}" "{GIT}")\nSPEC="${{SPECS[0]}}"\n'
        'log() { printf \'==> %s\\n\' "$*"; }\ndie() { echo "died: $*" >&2; exit 1; }\n'
        + _function("install_first")
        + f'install_first "{stub}"\necho "done"\n'
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)


@posix_only
def test_a_pypi_release_not_served_yet_falls_back_to_the_release_wheel(tmp_path: Path) -> None:
    # Right after a release, PyPI can answer the provenance check while the install of
    # that version still fails for a few minutes.
    result = _install_first(tmp_path, failing="git-into-gsoc==*")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "tried").read_text().splitlines() == ["git-into-gsoc==1.2.3", WHEEL]
    assert "can take a few minutes to reach every PyPI server" in result.stdout
    assert f"Installed from {WHEEL} instead" in result.stdout
    assert result.stdout.rstrip().endswith("done")


@posix_only
def test_when_every_source_fails_the_installer_stops_with_advice(tmp_path: Path) -> None:
    result = _install_first(tmp_path, failing="*")
    assert result.returncode == 1
    assert len((tmp_path / "tried").read_text().splitlines()) == 3
    assert "died: Could not install git-into-gsoc from any source" in result.stderr
    assert "done" not in result.stdout


def test_the_powershell_installer_checks_each_install_and_falls_back() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    # A failed native command does not stop PowerShell, so every route must go through
    # the loop that reads $LASTEXITCODE.
    assert text.count("Install-FirstWorking {") == 3
    assert "$LASTEXITCODE -eq 0" in text
    assert "Get-InstallSpec " not in text and "(Get-InstallSpec)" not in text


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
    pipx_python: str | None = None,
    pipx_has_environment: bool = True,
    pipx_script: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh's offer_uv on a PATH with no uv, pipx, or Python (unless asked).

    `pipx_python` adds a pipx that runs on a Python of that version ("3.9" or "3.12").
    Without `pipx_has_environment` it is pipx 1.0 (Ubuntu 22.04's), which cannot say
    which Python it uses: only the first line of its script names it.
    """
    text = (ROOT / "install.sh").read_text()
    functions = []
    names = ("pipx_python", "pipx_python_run", "pipx_ok", "python_ok", "python_version")
    names += ("venv_ok", "python_hint")
    for name in (*names, "ask_yes", "offer_uv"):
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
    if pipx_python:
        # pipx's own Python answers the version check, and prints its version.
        old = tuple(int(part) for part in pipx_python.split(".")) < (3, 11)
        fake = tmp_path / "pipx-python"
        fake.write_text(
            "#!/bin/sh\n"
            f'case "$2" in *print*) echo {pipx_python};; *) exit {1 if old else 0};; esac\n'
        )
        fake.chmod(0o755)
        if pipx_has_environment:
            (bin_dir / "pipx").write_text(f"#!/bin/sh\necho {fake}\n")
        else:
            (bin_dir / "pipx").write_text(f"#!{fake}\n# pipx 1.0: no `environment` command\n")
        (bin_dir / "pipx").chmod(0o755)
    if pipx_script is not None:
        (bin_dir / "pipx").write_text(pipx_script)
        (bin_dir / "pipx").chmod(0o755)
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


@posix_only
def test_a_pipx_on_an_old_python_is_not_used(tmp_path: Path) -> None:
    # Ubuntu 22.04's pipx runs on Python 3.10, and `pip3 install pipx` on a Mac on 3.9.
    # The installer used it, every source failed with "requires a different Python", and
    # it said to check the internet connection.
    result = _offer_uv(tmp_path, flag=False, pipx_python="3.9")
    assert result.returncode == 1
    assert "pipx is here, but it runs on Python 3.9" in result.stderr
    assert "| bash -s -- --install-uv" in result.stderr
    newer = tmp_path / "newer"
    newer.mkdir()
    result = _offer_uv(newer, flag=False, pipx_python="3.12")
    assert result.returncode == 0 and result.stdout.strip() == "uv-ready"
    # Ubuntu 22.04's pipx 1.0 has no `environment --value`; its first line names Python.
    ubuntu = tmp_path / "ubuntu"
    ubuntu.mkdir()
    result = _offer_uv(ubuntu, flag=False, pipx_python="3.10", pipx_has_environment=False)
    assert result.returncode == 1
    assert "pipx is here, but it runs on Python 3.10" in result.stderr


@posix_only
def test_a_pipx_wrapped_in_a_shell_script_is_still_tried(tmp_path: Path) -> None:
    # Nix and hand-made setups start pipx with `#!/bin/sh`: that line names no Python, so
    # the installer cannot tell, and tries pipx rather than calling it too old.
    result = _offer_uv(tmp_path, flag=False, pipx_script="#!/bin/sh\nexit 2\n")
    assert result.returncode == 0 and result.stdout.strip() == "uv-ready"
    assert "pipx is here" not in result.stderr


_PS_PIPX = r"""
$ErrorActionPreference = "Stop"
$names = "Get-PipxPython", "Test-PipxOk"
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$null, [ref]$null)
$found = $ast.FindAll({ param($n)
  $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in $names }, $true)
foreach ($f in $found) { . ([scriptblock]::Create($f.Extent.Text)) }
function pipx { "oldpython" }
function oldpython { $global:LASTEXITCODE = [int]$env:FAKE_PIPX_PYTHON_EXIT }
Write-Output "OK $(Test-PipxOk)"
"""


@needs_pwsh
def test_powershell_does_not_use_a_pipx_on_an_old_python(tmp_path: Path) -> None:
    script = tmp_path / "pipx.ps1"
    script.write_text(_PS_PIPX, encoding="utf-8")
    seen = {}
    for code in ("1", "0"):
        result = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(script),
                str(ROOT / "install.ps1"),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "FAKE_PIPX_PYTHON_EXIT": code},
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        seen[code] = result.stdout.strip()
    assert seen == {"1": "OK False", "0": "OK True"}


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
