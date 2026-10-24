#!/usr/bin/env bash
# A complete git-into-gsoc terminal session.
#
# Every command here only reads public data. Nothing is posted to GitHub and
# nothing is saved to your progress file.
#
# Before running:  source .venv/bin/activate   (from the repository folder)
# Then:            bash examples/cli-session.sh
set -euo pipefail

step() { printf '\n==> %s\n\n' "$*"; }

step "Check the setup: version, data folders, GitHub token, request allowance"
git-into-gsoc doctor || true   # no token or no network is not fatal here

step "Where are we in the program year? (dates for an unpublished year are estimates)"
git-into-gsoc program --year 2027

step "Find organizations that use Python and work on science"
git-into-gsoc orgs --tech python --topics science -n 5

step "Look at one organization: ideas page, channels, past projects"
git-into-gsoc org "SymPy"

step "Rank that organization's repositories for a first contribution"
git-into-gsoc repos "SymPy" -n 5

step "Check whether one repository is active and welcoming"
git-into-gsoc repo sympy/sympy

step "Find open beginner issues in that repository"
git-into-gsoc issues --repo sympy/sympy -n 5

step "Check one issue before commenting.
Choose an issue from the list above and run:
  git-into-gsoc issue OWNER/REPO#NUMBER
Replace OWNER/REPO and NUMBER with your own values."

step "What a proposal needs"
git-into-gsoc proposal

step "The same data as JSON, for scripts and assistants"
git-into-gsoc proposal --output json | head -c 400
echo

step "Done"
echo "Next: open docs/README.md and repeat these steps with an organization you care about."
echo "To save a shortlist or a note:  git-into-gsoc progress shortlist_org --value \"SymPy\""
