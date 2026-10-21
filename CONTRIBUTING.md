# Contributing to git-into-gsoc

Thanks for helping aspiring GSoC contributors succeed the right way.

## Principles

1. **Evidence over vibes** — prefer real API/archive data and official links.
2. **No fabrication** — never invent orgs, issues, or deadlines.
3. **Anti-spam** — features must not optimize for low-quality AI PR volume.
4. **Beginner-welcoming DX** — clear errors, docs, and installer paths.
5. **Quality over speed** — never bypass branch protections or merge failing CI.

## Development setup

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install pre-commit
pre-commit install
./install.sh --skill-only   # optional: wire local skills
```

## Local quality checks

Run the same gates CI runs before opening a PR:

```bash
ruff check src tests
ruff format src tests
mypy src
pytest --cov=git_into_gsoc --cov-fail-under=50
pip-audit
git-into-gsoc doctor
```

Or via pre-commit:

```bash
pre-commit run --all-files
```

## Git workflow

### Branches

1. Create a focused branch from an up-to-date `main`:

   ```bash
   git fetch origin
   git checkout main
   git pull --ff-only origin main
   git checkout -b feat/short-description
   ```

2. Prefer prefixes: `feat/`, `fix/`, `docs/`, `chore/`, `ci/`, `test/`, `refactor/`.
3. Keep branches short-lived and scoped to one concern.

### Commits (Conventional Commits)

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(optional-scope): <description>

[optional body]

[optional footer]
```

Common types: `feat`, `fix`, `docs`, `ci`, `test`, `refactor`, `chore`, `perf`.

Examples:

```text
feat(github): detect linked open PRs in issue availability
fix(cli): make --version eager under Typer
docs: clarify GSoC 2027 estimate disclaimer
ci: add pip-audit to quality job
```

Breaking changes: add `!` after the type/scope or a `BREAKING CHANGE:` footer.

**Atomic commits:** one logical change per commit. Do not mix refactors with features.

### Pull requests

- Open a PR early; keep it reviewable (prefer < ~400 LOC when practical).
- Fill out the PR template: summary, test plan, validation results.
- Link issues with `Fixes #123` / `Closes #123` when applicable.
- Ensure CI is green (`Quality`, `Test`, `Installer smoke`).
- Resolve all review conversations before merge.
- Expect **squash merge** into `main` (merge commits and rebase merges are disabled).
- Merged branches are deleted automatically.

### Reviews

- Be specific and kind.
- Prefer evidence (logs, commands, links) over opinions.
- CODEOWNERS may request review automatically for owned paths.

## Project layout

| Path | Purpose |
|------|---------|
| `src/git_into_gsoc/` | CLI, MCP server, GitHub/GSoC clients, scoring |
| `skills/git-into-gsoc/` | Portable Agent Skill |
| `tests/` | Unit + integration tests |
| `docs/` | Extended documentation |
| `install.sh` | One-shot installer |
| `.github/` | CI, templates, CODEOWNERS, Dependabot |

## Adding an MCP tool

1. Implement logic in `service.py` (or a focused module).
2. Expose via `mcp_server.py` and, if useful, `cli.py`.
3. Add tests with fixtures/`respx` — no live network in unit tests.
4. Document in README + skill references if user-facing.

## Skill edits

Keep `skills/git-into-gsoc/SKILL.md` under 500 lines. Put depth in `references/`.
Descriptions must include WHAT + WHEN trigger terms.

## Releases (SemVer)

Versions follow [Semantic Versioning](https://semver.org/):

- `feat:` → minor (while `<1.0.0`, release-please may bump minor for features)
- `fix:` → patch
- `BREAKING CHANGE` → major (or minor pre-1.0 per config)

[Release Please](https://github.com/googleapis/release-please) opens a release PR from Conventional Commits on `main`. Do not hand-edit version numbers in that PR unless asked.

## Dependency updates

Dependabot opens weekly grouped PRs for Python and GitHub Actions. Review CI results before merging.

## Code of conduct

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md). Do not open public issues for vulnerabilities.
