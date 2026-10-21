#!/usr/bin/env bash
# Quick check that the git-into-gsoc command is available. Assistants can run
# this before relying on live data.
set -euo pipefail
if command -v git-into-gsoc >/dev/null 2>&1; then
  git-into-gsoc doctor
else
  echo "git-into-gsoc is not on PATH."
  echo "From the repository folder run:  ./install.sh && source .venv/bin/activate"
  exit 1
fi
