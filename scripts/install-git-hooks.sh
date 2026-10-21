#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${ROOT}/.git/hooks"
cp "${ROOT}/scripts/commit-msg.hook" "${ROOT}/.git/hooks/commit-msg"
chmod +x "${ROOT}/.git/hooks/commit-msg"
echo "Installed .git/hooks/commit-msg (strips AI tool attribution trailers)"
