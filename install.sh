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
  command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3.11 or newer is required, but '$PYTHON' was not found. Install it from https://www.python.org/downloads/ and run this script again."
  "$PYTHON" - <<'PY' || exit 1
import sys
if sys.version_info < (3, 11):
    raise SystemExit(
        f"Python 3.11 or newer is required, but this is Python {sys.version.split()[0]}.\n"
        "Install a newer Python, then run: PYTHON=python3.12 ./install.sh"
    )
print(f"Using {sys.executable}")
PY
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
#   3. The source on GitHub (needs Git), when the release cannot be looked up.
# An explicit GIG_REPO_URL means "install exactly this source", so 1 and 2 are skipped.
OWN_REPO="anandkaranubc/git-into-gsoc"
GIT_SPEC="git+${REPO_URL}"

# Prints the newest release's version without the leading "v".
latest_release_version() {
  [[ -z "${GIG_REPO_URL:-}" ]] && command -v curl >/dev/null 2>&1 || return 1
  local version
  version="$(curl -fsSL --max-time 10 "https://api.github.com/repos/${OWN_REPO}/releases/latest" 2>/dev/null \
    | sed -n 's/^ *"tag_name": *"v\{0,1\}\([0-9][0-9A-Za-z.+-]*\)".*/\1/p')" || return 1
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

SPEC=""
choose_spec() {
  local version
  if version="$(latest_release_version)"; then
    if SPEC="$(verified_pypi_spec "$version")"; then
      log "Using ${SPEC} from PyPI (published by ${OWN_REPO})"
      return
    fi
    if SPEC="$(release_wheel_spec "$version")"; then
      log "Using release v${version} from GitHub"
      return
    fi
  fi
  SPEC="$GIT_SPEC"
  log "Using the source on GitHub (${REPO_URL})"
  command -v git >/dev/null 2>&1 || die "Installing from the source needs Git, which was not found. Install it from https://git-scm.com/downloads and run this script again."
}

# --------------------------------------------------- uv, when nothing else fits
# uv installs Python by itself, so a computer without Python 3.11 can still install
# the tool. It is only offered when there is no uv, no pipx, and no usable Python.
python_ok() {
  command -v "$PYTHON" >/dev/null 2>&1 \
    && "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null
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
  command -v uv >/dev/null 2>&1 || command -v pipx >/dev/null 2>&1 || python_ok && return 0
  echo "This computer has no uv, no pipx, and no Python 3.11 or newer."
  echo "uv is a free tool from Astral (https://docs.astral.sh/uv/) that installs Python"
  echo "programs and the Python they need, into your home folder only."
  if [[ "$INSTALL_UV" -eq 1 ]] || ask_yes "Install uv now?"; then
    command -v curl >/dev/null 2>&1 || die "curl is needed to install uv."
    log "Installing uv from https://astral.sh/uv/install.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${XDG_BIN_HOME:-${HOME}/.local/bin}:${HOME}/.cargo/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || die "uv was installed but is not on PATH yet. Open a new terminal and run this script again."
  else
    die "Install Python 3.11 or newer (https://www.python.org/downloads/) or uv (https://docs.astral.sh/uv/), then run this script again. To let this script install uv for you, add --install-uv."
  fi
}

install_remote() {
  offer_uv
  choose_spec
  local spec="$SPEC"
  if command -v uv >/dev/null 2>&1; then
    log "Installing git-into-gsoc with uv"
    uv tool install -q --force "$spec"
    GIG_BIN="$(uv tool dir --bin)/git-into-gsoc"
  elif command -v pipx >/dev/null 2>&1; then
    log "Installing git-into-gsoc with pipx"
    pipx install --force "$spec" >/dev/null
    GIG_BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "${HOME}/.local/bin")/git-into-gsoc"
  else
    check_python
    local base="${XDG_DATA_HOME:-${HOME}/.local/share}/git-into-gsoc"
    log "Installing git-into-gsoc into ${base}/venv (install uv or pipx for a lighter setup)"
    mkdir -p "$base" "${HOME}/.local/bin"
    [[ -d "${base}/venv" ]] || "$PYTHON" -m venv "${base}/venv"
    "${base}/venv/bin/python" -m pip install -q -U pip
    "${base}/venv/bin/python" -m pip install -q "$spec"
    ln -sf "${base}/venv/bin/git-into-gsoc" "${HOME}/.local/bin/git-into-gsoc"
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

print_next_steps() {
  echo
  echo "All set. Next steps:"
  if [[ "$MODE" == "checkout" ]]; then
    cat <<NEXT

  1. Turn on the tool in this terminal. Do this again in every new terminal:
       source "${ROOT}/.venv/bin/activate"

  2. Try your first command:
       git-into-gsoc program
NEXT
  else
    cat <<NEXT

  1. Open a new terminal and check that the command is found:
       git-into-gsoc --version
     If it says "command not found", add $(dirname "${GIG_BIN}") to your PATH,
     then open a new terminal.

  2. Try your first command:
       git-into-gsoc program
NEXT
  fi
  cat <<NEXT

  3. Check your setup any time:
       git-into-gsoc doctor

  4. Follow the beginner guide, one step at a time:
       ${DOCS_URL}/README.md
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
