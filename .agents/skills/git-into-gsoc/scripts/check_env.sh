#!/usr/bin/env bash
# Quick environment check for agents
set -euo pipefail
if command -v git-into-gsoc >/dev/null 2>&1; then
  git-into-gsoc doctor
else
  echo "git-into-gsoc not on PATH. Run ./install.sh from the repo root."
  exit 1
fi
