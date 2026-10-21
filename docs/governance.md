# Repository governance

This project follows industry-standard GitHub collaboration practices.

## Branch protection (`main`)

- Changes land only through pull requests
- Squash merge only (merge commits and rebase merges disabled)
- Merged branches are deleted automatically
- Required status checks must pass
- Review conversations must be resolved before merge
- Force pushes and branch deletion on `main` are blocked

## Commit and review norms

- [Conventional Commits](https://www.conventionalcommits.org/) on feature branches
- Squash merge uses the PR title as the commit subject on `main`
- Keep PRs focused; link issues when applicable
- See [CONTRIBUTING.md](../CONTRIBUTING.md)

## Automation

| System | Purpose |
|--------|---------|
| CI workflow | Ruff, format, mypy, pip-audit, pytest, installer smoke |
| Dependabot | Weekly pip + Actions updates (grouped) |
| Release Please | SemVer releases from Conventional Commits |
| CODEOWNERS | Default review routing |

## Releases

Release Please opens a release PR when `main` has releasable commits.
PyPI publish is optional and requires Trusted Publishing on the `release` environment.
