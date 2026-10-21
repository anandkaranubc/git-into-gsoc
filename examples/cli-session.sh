#!/usr/bin/env bash
# Example end-to-end CLI session (safe, read-only against public APIs)
set -euo pipefail

echo "=== doctor ==="
git-into-gsoc doctor || true

echo "=== program ==="
git-into-gsoc program --year 2027

echo "=== org search ==="
git-into-gsoc orgs --tech python --topics science --year 2026 -n 5

echo "=== proposal checklist ==="
git-into-gsoc proposal --output json | head -c 500
echo

echo "=== progress ==="
git-into-gsoc progress summary --output json

echo "Done. Add --github and GITHUB_TOKEN for personalized recommend/issues."
