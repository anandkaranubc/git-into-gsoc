# Releasing

Releases are cut by [Release Please](https://github.com/googleapis/release-please) from Conventional Commits on `main`. Maintainers only need to do three things.

## 1. Refresh the embedded organization snapshot

The package ships a compact copy of the official organization list and every organization's history so `orgs` works offline and never needs the large archive. Refresh it from the live sources before a release and commit the result:

```bash
python -m git_into_gsoc.gsoc.snapshot
git add src/git_into_gsoc/data/org_history.json src/git_into_gsoc/data/official_orgs.json
git commit -m "chore(data): refresh the organization snapshot"
```

Pass a year to pin which official list is embedded, for example `python -m git_into_gsoc.gsoc.snapshot 2027` once that year's organizations are announced.

## 2. Merge the release pull request

Release Please keeps a pull request titled `chore(main): release X.Y.Z` open whenever `main` has unreleased commits. Because the bot pushes that branch with the built-in Actions token, GitHub does not start CI on it, and the branch rules require passing checks. Trigger the checks yourself before merging: close and reopen the pull request, or rebase its branch onto `main` and push it (which also picks up any test or manifest fixes that landed after the bot last refreshed it). To make this automatic, store a fine-grained personal access token with contents and pull-request write permission as a repository secret and pass it to the action as `token:` in `release.yml`. It updates `CHANGELOG.md`, the version in `pyproject.toml`, `src/git_into_gsoc/__init__.py`, and the plugin manifests. While the project is below 1.0, `feat:` commits bump the minor version and `fix:` commits bump the patch version. Merging that pull request creates the Git tag and the GitHub release.

## 3. Publish to PyPI (one-time setup)

The release workflow builds a wheel and publishes it with [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/), which needs no stored token. Until a trusted publisher is configured, the publish step is allowed to fail and only the GitHub release exists.

To set it up once:

1. On PyPI, open your account's **Publishing** page and add a pending publisher with project name `git-into-gsoc`, owner `anandkaranubc`, repository `git-into-gsoc`, workflow `release.yml`, and environment `release`.
2. On GitHub, create an environment named `release` under **Settings > Environments** (no secrets needed; optionally require a reviewer).
3. Merge the next release pull request. The `Publish to PyPI` job runs under that environment and uploads the wheel.

After the first publish, users can install with `uv tool install git-into-gsoc` or `pipx install git-into-gsoc` instead of the Git URL; the installer scripts try the package name first once it exists.

## 4. MCP registry (automatic)

Publishing the release creates the GitHub release, which triggers `Publish to MCP Registry`. The workflow builds `dist/git-into-gsoc.mcpb` with `scripts/build_mcpb.py`, uploads it as a release asset, rewrites `server.json` to point at it, and publishes with `mcp-publisher login github-oidc`. Nothing to configure; to republish a tag by hand, run the workflow from the Actions tab with the tag name.

## Checks before merging a release

```bash
ruff check src tests && ruff format --check src tests
mypy src
pytest
git-into-gsoc setup --dry-run --assistant all
```

The CI matrix already runs these on Linux, macOS, and Windows for every pull request.

[Guide contents](README.md) · [Contributing](../CONTRIBUTING.md)
