#!/usr/bin/env bash
# git-into-gsoc installer: Python package, Agent Skill copies, and MCP setup hints.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="${ROOT}/skills/git-into-gsoc"
PYTHON="${PYTHON:-python3}"
DOCS_URL="https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs"

SKILL_ONLY=0
MCP_ONLY=0
USER_SKILLS=0

usage() {
  cat <<'USAGE'
Usage: ./install.sh [options]

By default this creates .venv, installs the package into it, and copies the
Agent Skill into this repository's .agents, .cursor, and .claude folders.
Nothing outside this folder is changed unless you ask for it.

  --user-skills    Also copy the skill into ~/.agents, ~/.cursor, ~/.claude,
                   ~/.codex, and ~/.gemini (when Gemini CLI is present).
                   Existing copies of this skill there are replaced.
  --no-user-skills Keep skill copies inside this repository (the default)
  --skill-only     Copy the skill only; skip the Python package
  --mcp-only       Install the Python package and show MCP setup; skip the skill copy
  -h, --help       Show this help

Use a specific Python:  PYTHON=python3.12 ./install.sh
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill-only) SKILL_ONLY=1 ;;
    --mcp-only) MCP_ONLY=1 ;;
    --user-skills) USER_SKILLS=1 ;;
    --no-user-skills) USER_SKILLS=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

log() { printf '==> %s\n' "$*"; }

install_python() {
  log "Installing the Python package into ${ROOT}/.venv"
  if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3.11 or newer is required, but '${PYTHON}' was not found." >&2
    echo "Install it from https://www.python.org/downloads/ and run this script again." >&2
    exit 1
  fi
  "$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(
        f"Python 3.11 or newer is required, but this is Python {sys.version.split()[0]}.\n"
        "Install a newer Python, then run: PYTHON=python3.12 ./install.sh"
    )
print(f"Using {sys.executable}")
PY
  if [[ ! -d "${ROOT}/.venv" ]]; then
    "$PYTHON" -m venv "${ROOT}/.venv"
  fi
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
  pip install -U pip >/dev/null
  pip install -e "${ROOT}[dev]"
  log "Checking your setup"
  git-into-gsoc doctor || true
}

copy_skill() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -R "${SKILL_SRC}/." "$dest/"
  log "Skill copied to ${dest}"
}

install_skills() {
  if [[ ! -f "${SKILL_SRC}/SKILL.md" ]]; then
    echo "Missing skill at ${SKILL_SRC}" >&2
    exit 1
  fi
  # Project-local copies let assistants find the skill when this folder is open.
  local targets=(
    "${ROOT}/.agents/skills/git-into-gsoc"
    "${ROOT}/.cursor/skills/git-into-gsoc"
    "${ROOT}/.claude/skills/git-into-gsoc"
  )
  if [[ "$USER_SKILLS" -eq 1 ]]; then
    targets+=(
      "${HOME}/.agents/skills/git-into-gsoc"
      "${HOME}/.cursor/skills/git-into-gsoc"
      "${HOME}/.claude/skills/git-into-gsoc"
      "${HOME}/.codex/skills/git-into-gsoc"
    )
    if [[ -d "${HOME}/.gemini" ]] || command -v gemini >/dev/null 2>&1; then
      targets+=("${HOME}/.gemini/skills/git-into-gsoc")
    fi
  fi
  for dest in "${targets[@]}"; do
    copy_skill "$dest"
  done
  if [[ "$USER_SKILLS" -eq 0 ]]; then
    log "Skill copies stay inside this repository. Add --user-skills to install them for every project."
  fi
}

print_mcp_help() {
  local cmd="${ROOT}/.venv/bin/git-into-gsoc"
  cat <<MCP

MCP server (lets AI assistants call git-into-gsoc directly)

For Cursor, merge this into ~/.cursor/mcp.json:
{
  "mcpServers": {
    "git-into-gsoc": {
      "command": "${cmd}",
      "args": ["mcp"]
    }
  }
}

Claude Code, Codex, and Gemini CLI steps:
  ${DOCS_URL}/guide/03-connect-your-ai-assistant.md
MCP
}

print_next_steps() {
  cat <<NEXT

All set. Next steps:

  1. Turn on the tool in this terminal. Do this again in every new terminal:
       source "${ROOT}/.venv/bin/activate"

  2. Try your first command:
       git-into-gsoc program

  3. Follow the beginner guide, one step at a time:
       ${DOCS_URL}/README.md
NEXT
}

main() {
  log "git-into-gsoc installer"
  if [[ "$SKILL_ONLY" -eq 0 ]]; then
    install_python
  fi
  if [[ "$MCP_ONLY" -eq 0 ]]; then
    install_skills
    log "Restart your AI assistant so it picks up the git-into-gsoc skill."
  fi
  if [[ "$SKILL_ONLY" -eq 0 ]]; then
    print_mcp_help
    print_next_steps
  fi
}

main
