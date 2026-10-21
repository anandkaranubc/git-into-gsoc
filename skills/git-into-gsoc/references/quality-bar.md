# Contribution quality bar

## What “good” looks like

- Fixes a real, maintainer-acknowledged problem (issue link).
- Matches project style, tests, and CI expectations.
- Small enough to review; large enough to matter.
- PR description explains *why*, *what*, and *how tested*.
- Author can walk through the change on a voice call without notes.

## Encouraged first contributions

- Well-scoped bug fixes with reproduction steps
- Missing tests for important untested behavior
- Documentation fixes verified against source (examples run)
- Accessibility / error-message clarity improvements
- Build/CI flakiness fixes with evidence

## Discouraged / refuse to help produce

- Pure typo farms across many files
- Unsolicited dependency bumps without issue/discussion
- Reformatting-only PRs
- “Add my name to contributors” vanity changes
- AI-generated code the user cannot explain
- Duplicate PRs on already-claimed issues
- Security “findings” without responsible disclosure norms

## Before opening a PR

1. Read README + CONTRIBUTING + CoC.
2. Reproduce the issue (or write a failing test).
3. Run the project's lint/tests locally (or via documented commands).
4. Rebase on the default branch; keep history clean per project norms.
5. Self-review the diff as if you were the maintainer.

## AI-assisted coding rules (default)

Unless the org is more permissive:

- User designs the approach first; agent helps research and draft.
- User validates every generated hunk.
- No merging of code nobody understands.
- Disclose AI assistance if the org asks.

## Availability etiquette

- Prefer issues marked available / good-first-issue without assignee or open linked PR.
- Comment once with intent + brief plan; wait for maintainer guidance when the issue says so.
- If someone else is clearly working it, pick another issue.
