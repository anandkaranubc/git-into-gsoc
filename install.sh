#!/usr/bin/env bash
# git-into-gsoc one-shot installer — package + Agent Skill + MCP hints
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="${ROOT}/skills/git-into-gsoc"
PYTHON="${PYTHON:-python3}"

SKILL_ONLY=0
MCP_ONLY=0
USER_SKILLS=1

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --skill-only     Copy Agent Skill only (skip Python package)
  --mcp-only       Install Python package / show MCP config (skip skill copy)
  --no-user-skills Do not copy skills into ~/.cursor, ~/.claude, etc.
  -h, --help       Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill-only) SKILL_ONLY=1 ;;
    --mcp-only) MCP_ONLY=1 ;;
    --no-user-skills) USER_SKILLS=0 ;;
    --user-skills) USER_SKILLS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

log() { printf '==> %s\n' "$*"; }
warn() { printf 'warn: %s\n' "$*" >&2; }

install_python() {
  log "Installing Python package (editable)"
  if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3.11+ is required (python3 not found)" >&2
    exit 1
  fi
  "$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ required, found {sys.version}")
print(f"Using {sys.executable}")
PY
  if [[ ! -d "${ROOT}/.venv" ]]; then
    "$PYTHON" -m venv "${ROOT}/.venv"
  fi
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
  pip install -U pip >/dev/null
  pip install -e "${ROOT}[dev]"
  log "CLI available as: $(command -v git-into-gsoc)"
  git-into-gsoc doctor || true
}

copy_skill() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -R "${SKILL_SRC}/." "$dest/"
  log "Skill installed → ${dest}"
}

install_skills() {
  if [[ ! -f "${SKILL_SRC}/SKILL.md" ]]; then
    echo "Missing skill at ${SKILL_SRC}" >&2
    exit 1
  fi
  # Always install project-local copies for repo users
  local targets=(
    "${ROOT}/.agents/skills/git-into-gsoc"
    "${ROOT}/.cursor/skills/git-into-gsoc"
    "${ROOT}/.claude/skills/git-into-gsoc"
  )
  if [[ "$USER_SKILLS" -eq 1 ]]; then
    targets+=(
      "${HOME}/.cursor/skills/git-into-gsoc"
      "${HOME}/.agents/skills/git-into-gsoc"
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
}

print_mcp_help() {
  local cmd="git-into-gsoc"
  if [[ -x "${ROOT}/.venv/bin/git-into-gsoc" ]]; then
    cmd="${ROOT}/.venv/bin/git-into-gsoc"
  fi
  cat <<EOF

MCP server (stdio):
  ${cmd} mcp

Example Cursor MCP snippet (~/.cursor/mcp.json):
{
  "mcpServers": {
    "git-into-gsoc": {
      "command": "${cmd}",
      "args": ["mcp"],
      "env": {
        "GITHUB_TOKEN": "\${env:GITHUB_TOKEN}"
      }
    }
  }
}

Set GITHUB_TOKEN (or GH_TOKEN) for higher GitHub API rate limits.
EOF
}

main() {
  log "git-into-gsoc installer"
  if [[ "$SKILL_ONLY" -eq 0 ]]; then
    install_python
  fi
  if [[ "$MCP_ONLY" -eq 0 ]]; then
    install_skills
  fi
  if [[ "$SKILL_ONLY" -eq 0 ]]; then
    print_mcp_help
  fi
  log "Done. Try: git-into-gsoc program --year 2027"
  log "In your assistant: ask to use the git-into-gsoc skill for your GSoC journey."
}

main
