#!/usr/bin/env bash
# git-into-gsoc one-shot installer (macOS, Linux, WSL).
#
#   From a clone:   ./install.sh [options]
#                   -> installs the package into ./.venv, then runs `git-into-gsoc setup`
#   From anywhere:  curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
#                   -> installs the tool with uv or pipx (or a private venv), then runs setup
#
# `git-into-gsoc setup` is what copies the Agent Skill and registers the MCP
# server with your assistants; it is plain Python, so Windows users can run
# install.ps1 or call `setup` directly.
set -euo pipefail

# GIG_REPO_URL overrides the source (CI tests the bootstrap against a local checkout).
REPO_URL="${GIG_REPO_URL:-https://github.com/anandkaranubc/git-into-gsoc}"
DOCS_URL="${REPO_URL}/blob/main/docs"
PYTHON="${PYTHON:-python3}"

SCOPE=""
DO_PACKAGE=1
DO_SKILL=1
DO_MCP=1
DRY_RUN=0
INSTALL_UV=0
ASSISTANTS=()

usage() {
  cat <<'USAGE'
Usage: ./install.sh [options]

  --no-user-skills   Set up inside this repository only (project scope; default from a clone)
  --user-skills      Set up in your home folder so every project can use it (user scope)
  --assistant NAME   Configure only this assistant (repeatable): claude-code, cursor, codex,
                     gemini, windsurf, vscode, all. Default: every assistant detected.
  --skill-only       Copy the Agent Skill only (skip package install and MCP registration)
  --mcp-only         Install the package and register the MCP server, skip the skill copy
  --dry-run          Show what setup would change without writing anything
  --install-uv       If there is no uv, pipx, or Python 3.11+, install uv without asking
  -h, --help         Show this help

Use a specific Python:  PYTHON=python3.12 ./install.sh
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-user-skills) SCOPE="project" ;;
    --user-skills) SCOPE="user" ;;
    --assistant) shift; [[ $# -gt 0 ]] || { echo "--assistant needs a name" >&2; exit 1; }; ASSISTANTS+=("$1") ;;
    --assistant=*) ASSISTANTS+=("${1#*=}") ;;
    --skill-only) DO_PACKAGE=0; DO_MCP=0 ;;
    --mcp-only) DO_SKILL=0 ;;
    --dry-run) DRY_RUN=1 ;;
    --install-uv) INSTALL_UV=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- where are we
ROOT=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
MODE="remote"
if [[ -n "$ROOT" && -f "$ROOT/pyproject.toml" ]] && grep -q '^name = "git-into-gsoc"' "$ROOT/pyproject.toml"; then
  MODE="checkout"
fi
if [[ -z "$SCOPE" ]]; then
  SCOPE="project"; [[ "$MODE" == "remote" ]] && SCOPE="user"
fi

check_python() {
  command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3.11 or newer is required, but '$PYTHON' was not found. $(python_hint)"
  "$PYTHON" - <<'PY' || exit 1
import sys
if sys.version_info < (3, 11):
    raise SystemExit(
        f"error: Python 3.11 or newer is required, but this is Python {sys.version.split()[0]}.\n"
        "Install a newer Python, then run: PYTHON=python3.12 ./install.sh"
    )
print(f"Using {sys.executable}")
PY
  venv_ok || die "Python $(python_version) is installed, but its venv module is missing, so it cannot make a private environment. $(python_hint)"
}

# The Python found, as "3.12.3", or "none".
python_version() {
  "$PYTHON" -c 'import platform; print(platform.python_version())' 2>/dev/null || echo "none"
}

# Ubuntu, Debian, and WSL split venv and ensurepip into a separate package.
venv_ok() {
  "$PYTHON" -c 'import ensurepip, venv' >/dev/null 2>&1
}

# Another way to a usable Python on this system, in one line, for what is wrong.
python_hint() {
  if command -v "$PYTHON" >/dev/null 2>&1 \
    && "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "Or run: sudo apt install python3-venv, then run this installer again."
    else
      echo "Or install the venv package for your Python, then run this installer again."
    fi
  elif command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Your system's Python is too old to update in place, so --install-uv is the easiest way."
  elif command -v brew >/dev/null 2>&1; then
    echo "Or run: brew install python, then run this installer again."
  elif command -v dnf >/dev/null 2>&1; then
    echo "Or run: sudo dnf install python3, then run this installer again."
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Or run: sudo apt install python3 python3-venv, then run this installer again."
  else
    echo "Or install Python 3.11 or newer from https://www.python.org/downloads/, then run this installer again."
  fi
}

# ----------------------------------------------------------- install package
GIG_BIN=""

install_checkout() {
  log "Installing git-into-gsoc into ${ROOT}/.venv"
  check_python
  [[ -d "${ROOT}/.venv" ]] || "$PYTHON" -m venv "${ROOT}/.venv"
  "${ROOT}/.venv/bin/python" -m pip install -q -U pip
  "${ROOT}/.venv/bin/python" -m pip install -q -e "${ROOT}"
  GIG_BIN="${ROOT}/.venv/bin/git-into-gsoc"
}

# Where the package comes from, best first:
#   1. PyPI, but only for a release that this repository's own release workflow published.
#      The name "git-into-gsoc" is not reserved on PyPI until the first upload, so anyone
#      could claim it; PyPI checks the trusted-publishing attestation on every upload and
#      serves the publisher it verified, which an upload from another repository cannot fake.
#   2. The wheel attached to the newest GitHub release: a finished package, so neither
#      Git nor a build step is needed.
#   3. The source on GitHub (needs Git), at the newest release's tag. Only when the release
#      cannot be looked up at all is it the newest commit instead.
# Each later source is also a fallback when installing an earlier one fails. Right after
# a release, PyPI can serve its provenance before every PyPI server offers the files, so
# for a few minutes the PyPI install can fail while the release wheel works. The release
# also appears a little before its wheel is attached, and the tag keeps the source in
# that gap the same code as the release, not changes merged since.
# An explicit GIG_REPO_URL means "install exactly this source", so 1 and 2 are skipped.
OWN_REPO="anandkaranubc/git-into-gsoc"
GIT_SPEC="git+${REPO_URL}"

# Prints the newest release's version without the leading "v".
latest_release_version() {
  [[ -z "${GIG_REPO_URL:-}" ]] && command -v curl >/dev/null 2>&1 || return 1
  local version
  version="$(curl -fsSL --max-time 10 "https://api.github.com/repos/${OWN_REPO}/releases/latest" 2>/dev/null \
    | sed -n 's/^ *"tag_name": *"v\{0,1\}\([0-9][0-9A-Za-z.+-]*\)".*/\1/p')" || version=""
  if [[ -z "$version" ]]; then
    # The API allows 60 requests an hour per address, which a classroom can use up. The
    # release page redirects to the newest tag without counting against that limit.
    version="$(curl -fsSIL -o /dev/null -w '%{url_effective}' --max-time 10 \
      "https://github.com/${OWN_REPO}/releases/latest" 2>/dev/null \
      | sed -n 's|.*/releases/tag/v\{0,1\}\([0-9][0-9A-Za-z.+-]*\)$|\1|p')" || return 1
  fi
  [[ -n "$version" ]] || return 1
  printf '%s\n' "$version"
}

verified_pypi_spec() {
  local version="$1" wheel publisher
  wheel="git_into_gsoc-${version}-py3-none-any.whl"
  publisher="$(curl -fsSL --max-time 10 \
    "https://pypi.org/integrity/git-into-gsoc/${version}/${wheel}/provenance" 2>/dev/null \
    | grep -o '"publisher": *{[^}]*}')" || return 1
  [[ "$publisher" == *'"kind":"GitHub"'* || "$publisher" == *'"kind": "GitHub"'* ]] || return 1
  [[ "$publisher" == *"\"repository\":\"${OWN_REPO}\""* || "$publisher" == *"\"repository\": \"${OWN_REPO}\""* ]] || return 1
  printf 'git-into-gsoc==%s\n' "$version"
}

release_wheel_spec() {
  local version="$1" url
  url="https://github.com/${OWN_REPO}/releases/download/v${version}/git_into_gsoc-${version}-py3-none-any.whl"
  curl -fsSIL --max-time 15 "$url" >/dev/null 2>&1 || return 1
  printf '%s\n' "$url"
}

# Sets SPECS to the sources to try, best first, and SPEC to the first of them.
SPEC=""
SPECS=()
choose_spec() {
  local version spec git_spec="$GIT_SPEC" from="$REPO_URL"
  SPECS=()
  if version="$(latest_release_version)"; then
    git_spec="${GIT_SPEC}@v${version}"
    from="${REPO_URL}, release v${version}"
    if spec="$(verified_pypi_spec "$version")"; then
      log "Using ${spec} from PyPI (published by ${OWN_REPO})"
      SPECS+=("$spec")
    fi
    if spec="$(release_wheel_spec "$version")"; then
      [[ ${#SPECS[@]} -gt 0 ]] || log "Using release v${version} from GitHub"
      SPECS+=("$spec")
    fi
  fi
  if [[ ${#SPECS[@]} -eq 0 ]]; then
    [[ -n "${GIG_REPO_URL:-}" || -n "${version:-}" ]] || log "Could not look up the newest release (no network, or GitHub is busy)"
    log "Using the source on GitHub (${from})"
    command -v git >/dev/null 2>&1 || die "Installing from the source needs Git, which was not found. Check your internet connection and try again in a few minutes, or install Git from https://git-scm.com/downloads first."
    SPECS=("$git_spec")
  elif command -v git >/dev/null 2>&1; then
    SPECS+=("$git_spec")
  fi
  SPEC="${SPECS[0]}"
}

# Runs the given install command with each source from choose_spec until one works.
install_first() {
  local spec
  for spec in "${SPECS[@]}"; do
    if "$@" "$spec"; then
      [[ "$spec" == "$SPEC" ]] || log "Installed from ${spec} instead"
      return 0
    fi
    echo  # the tool's last error line can lack a newline
    if [[ "$spec" == git-into-gsoc==* ]]; then
      log "Could not install ${spec} from PyPI. A new release can take a few minutes to reach every PyPI server, so trying the next source."
    else
      log "Could not install ${spec}. Trying the next source."
    fi
  done
  die "Could not install git-into-gsoc from any source. Check your internet connection and try again in a few minutes."
}

pipx_install_quiet() { pipx install --force "$1" >/dev/null; }

# pipx installs with the Python it runs on. Ubuntu 22.04's pipx runs on Python 3.10, and
# `pip3 install pipx` on a Mac on 3.9: every source then fails with "requires a different
# Python", and the installer blamed the network. Such a pipx is not used.
# Its Python: what pipx says, else (pipx 1.0, Ubuntu 22.04's, has no `environment`)
# PIPX_DEFAULT_PYTHON, else the interpreter on the first line of the pipx script.
pipx_python() {
  local py line
  if py="$(pipx environment --value PIPX_DEFAULT_PYTHON 2>/dev/null)" && [[ -n "$py" ]]; then
    printf '%s\n' "$py"
  elif [[ -n "${PIPX_DEFAULT_PYTHON:-}" ]]; then
    printf '%s\n' "$PIPX_DEFAULT_PYTHON"
  elif IFS= read -r line <"$(command -v pipx)" 2>/dev/null && [[ "$line" == '#!'*python* ]]; then
    # Only a Python names it; a shell wrapper (Nix's `#!/bin/sh`) cannot tell.
    printf '%s\n' "${line#\#!}"
  else
    return 1
  fi
}
# Runs pipx's Python with the given arguments. It may be "/usr/bin/env python3", so the
# command is split into words on purpose.
pipx_python_run() {
  local -a cmd
  read -r -a cmd <<<"$(pipx_python)" && [[ ${#cmd[@]} -gt 0 ]] || return 1
  "${cmd[@]}" "$@"
}
pipx_ok() {
  command -v pipx >/dev/null 2>&1 || return 1
  pipx_python >/dev/null || return 0  # cannot tell: try it
  pipx_python_run -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null
}

# --------------------------------------------------- uv, when nothing else fits
# uv installs Python by itself, so a computer without Python 3.11 can still install
# the tool. It is only offered when there is no uv, no pipx, and no usable Python.
python_ok() {
  command -v "$PYTHON" >/dev/null 2>&1 \
    && "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null \
    && venv_ok
}

# Asks on the terminal, which still works when this script is piped into bash.
ask_yes() {
  local answer=""
  { exec 3</dev/tty; } 2>/dev/null || return 1
  printf '%s [Y/n] ' "$1" >&2
  read -r answer <&3 || answer="n"
  exec 3<&-
  [[ -z "$answer" || "$answer" == [Yy]* ]]
}

offer_uv() {
  command -v uv >/dev/null 2>&1 || pipx_ok || python_ok && return 0
  {
    if command -v pipx >/dev/null 2>&1; then
      echo "pipx is here, but it runs on Python $(pipx_python_run -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "older than 3.11"), and git-into-gsoc needs 3.11 or newer."
    fi
    if ! command -v "$PYTHON" >/dev/null 2>&1; then
      echo "This computer has no uv, no pipx, and no Python."
    elif "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
      echo "This computer has Python $(python_version), but without its venv module, and no uv or usable pipx."
    else
      echo "This computer has Python $(python_version), which is older than 3.11, and no uv or usable pipx."
    fi
    echo "uv is a free tool from Astral (https://docs.astral.sh/uv/) that installs Python"
    echo "programs and the Python they need, into your home folder only."
  } >&2
  if [[ "$INSTALL_UV" -eq 1 ]] || ask_yes "Install uv now?"; then
    command -v curl >/dev/null 2>&1 || die "curl is needed to install uv."
    log "Installing uv from https://astral.sh/uv/install.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${XDG_BIN_HOME:-${HOME}/.local/bin}:${HOME}/.cargo/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv was installed but is not on PATH yet. Open a new terminal and run this script again."
  else
    die "To let this installer get uv for you, run it again with --install-uv:
  curl -fsSL https://raw.githubusercontent.com/${OWN_REPO}/main/install.sh | bash -s -- --install-uv
$(python_hint)"
  fi
}

install_remote() {
  offer_uv
  choose_spec
  if command -v uv >/dev/null 2>&1; then
    log "Installing git-into-gsoc with uv"
    # A release minutes old can be missing from uv's cached copy of the PyPI index.
    install_first uv tool install --refresh-package git-into-gsoc -q --force
    GIG_BIN="$(uv tool dir --bin)/git-into-gsoc"
  elif pipx_ok; then
    log "Installing git-into-gsoc with pipx"
    install_first pipx_install_quiet
    GIG_BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "${HOME}/.local/bin")/git-into-gsoc"
  else
    check_python
    local base="${XDG_DATA_HOME:-${HOME}/.local/share}/git-into-gsoc"
    log "Installing git-into-gsoc into ${base}/venv (install uv or pipx for a lighter setup)"
    mkdir -p "$base" "${HOME}/.local/bin"
    # A venv left half-made by an earlier run without python3-venv has no pip; rebuild it.
    if ! "${base}/venv/bin/python" -m pip --version >/dev/null 2>&1; then
      "$PYTHON" -m venv --clear "${base}/venv"
    fi
    "${base}/venv/bin/python" -m pip install -q -U pip
    install_first "${base}/venv/bin/python" -m pip install -q
    ln -sf "${base}/venv/bin/git-into-gsoc" "${HOME}/.local/bin/git-into-gsoc"
    ln -sf "${base}/venv/bin/gsoc" "${HOME}/.local/bin/gsoc"
    GIG_BIN="${HOME}/.local/bin/git-into-gsoc"
  fi
}

locate_existing() {
  if [[ "$MODE" == "checkout" && -x "${ROOT}/.venv/bin/git-into-gsoc" ]]; then
    GIG_BIN="${ROOT}/.venv/bin/git-into-gsoc"
  elif command -v git-into-gsoc >/dev/null 2>&1; then
    GIG_BIN="$(command -v git-into-gsoc)"
  else
    die "git-into-gsoc is not installed yet; run ./install.sh without --skill-only first."
  fi
}

# --------------------------------------------------------------------- setup
run_setup() {
  local args=(setup --scope "$SCOPE")
  [[ "$SCOPE" == "project" && -n "$ROOT" ]] && args+=(--project-dir "$ROOT")
  [[ "$DO_SKILL" -eq 1 ]] || args+=(--no-skill)
  [[ "$DO_MCP" -eq 1 ]] || args+=(--no-mcp)
  [[ "$DRY_RUN" -eq 1 ]] && args+=(--dry-run)
  for a in "${ASSISTANTS[@]:-}"; do [[ -n "$a" ]] && args+=(--assistant "$a"); done
  log "Running: git-into-gsoc ${args[*]}"
  "$GIG_BIN" "${args[@]}"
}

# The file a PATH line belongs in, for the shell this person uses. Printed for the
# person to read, so the tilde stays literal.
# shellcheck disable=SC2088
shell_rc() {
  case "$(basename "${SHELL:-}")" in
    zsh) echo "~/.zshrc" ;;
    bash) if [[ "$(uname -s)" == Darwin ]]; then echo "~/.bash_profile"; else echo "~/.bashrc"; fi ;;
    *) echo "~/.profile" ;;
  esac
}

on_path() {
  case ":${PATH}:" in *":$1:"*) return 0 ;; esac
  return 1
}

# How to make a new terminal find the command, or nothing when it already will.
path_advice() {
  local bin="$1" shown
  on_path "$bin" && return 0
  shown="${bin/#${HOME}/\$HOME}"
  echo "  The command is in ${bin}, which your terminal does not search yet."
  echo "  Run this once so every new terminal finds it:"
  if [[ "$(basename "${SHELL:-}")" == fish ]]; then
    echo "       fish_add_path ${shown}"
  else
    echo "       echo 'export PATH=\"${shown}:\$PATH\"' >> $(shell_rc)"
  fi
  echo "  Until then, run it with its full path: ${GIG_BIN}"
  echo
}

print_next_steps() {
  echo
  echo "All set. Next steps:"
  echo
  if [[ "$MODE" == "checkout" ]]; then
    cat <<NEXT
  1. Turn on the tool in this terminal. Do this again in every new terminal:
       source "${ROOT}/.venv/bin/activate"

  2. Answer four quick questions and see organizations that fit you:
       git-into-gsoc start
NEXT
  else
    path_advice "$(dirname "${GIG_BIN}")"
    cat <<NEXT
  1. Open a new terminal, then answer four quick questions and see
     organizations that fit you:
       git-into-gsoc start

  2. Any time you are unsure what to do next:
       git-into-gsoc next
NEXT
  fi
  cat <<NEXT

  3. If something does not work:
       git-into-gsoc doctor

  The beginner guide walks through every step: ${DOCS_URL}/README.md
NEXT
}

main() {
  log "git-into-gsoc installer (${MODE} mode, ${SCOPE} scope)"
  if [[ "$DO_PACKAGE" -eq 1 ]]; then
    if [[ "$MODE" == "checkout" ]]; then install_checkout; else install_remote; fi
    "$GIG_BIN" --version >/dev/null || die "Installed, but '${GIG_BIN} --version' failed."
  else
    locate_existing
  fi
  run_setup
  [[ "$DRY_RUN" -eq 1 ]] || print_next_steps
}

main
