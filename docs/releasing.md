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

A scheduled workflow (`snapshot-refresh.yml`, Mondays) runs the same refresher and opens a pull request when the data changed, so a release rarely needs a manual refresh; close and reopen that pull request to run CI, then squash-merge it.

## 2. Merge the release pull request

Release Please keeps a pull request titled `chore(main): release X.Y.Z` open whenever `main` has unreleased commits. Because the bot pushes that branch with the built-in Actions token, GitHub does not start CI on it, and the branch rules require passing checks. Trigger the checks yourself before merging: close and reopen the pull request, or rebase its branch onto `main` and push it (which also picks up any test or manifest fixes that landed after the bot last refreshed it). To make this automatic, store a fine-grained personal access token with contents and pull-request write permission as a repository secret and pass it to the action as `token:` in `release.yml`. It updates `CHANGELOG.md`, the version in `pyproject.toml`, `src/git_into_gsoc/__init__.py`, and the plugin manifests. While the project is below 1.0, `feat:` commits bump the minor version and `fix:` commits bump the patch version. Merging that pull request creates the Git tag and the GitHub release.

## 3. Publish to PyPI (one-time setup)

The release workflow builds a wheel and publishes it with [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/), which needs no stored token. Until a trusted publisher is configured, the `Publish to PyPI` job fails (shown in red) without failing the release, and its run summary repeats the values to enter below; the GitHub release and its assets are published either way. A green `Publish to PyPI` job now always means the upload happened.

To set it up once:

1. On PyPI, open your account's **Publishing** page and add a pending publisher with project name `git-into-gsoc`, owner `anandkaranubc`, repository `git-into-gsoc`, workflow `release.yml`, and environment `release`.
2. On GitHub, create an environment named `release` under **Settings > Environments** (no secrets needed; optionally require a reviewer).
3. Merge the next release pull request. The `Publish to PyPI` job runs under that environment and uploads the wheel.

After the first publish, users can install with `uv tool install git-into-gsoc` or `pipx install git-into-gsoc` instead of the Git URL; the installer scripts try the package name first once it exists. Until then, every release carries the wheel and the source archive as release assets, so anyone can install a pinned version by URL (see the [install guide](guide/02-install.md)).

## 4. Release assets and the MCP registry (automatic)

Merging the release pull request also starts `Release assets and MCP registry` (`.github/workflows/mcp-registry.yml`). The release workflow dispatches it with the new tag, because a release created with the built-in Actions token does not fire the `release` event. The workflow checks out the tagged source, builds the wheel and source archive with `python -m build` and the MCPB bundle with `scripts/build_mcpb.py`, and uploads all three as release assets. A **wheel** is Python's ready-to-install package file, so `uv tool install <wheel URL>` or `pipx install <wheel URL>` installs that exact release without PyPI. The workflow then rewrites `server.json` to point at the bundle and publishes with `mcp-publisher login github-oidc`. Nothing to configure.

To rebuild the assets for a tag, run the workflow from the Actions tab with the tag name, or `gh workflow run mcp-registry.yml -f tag=v0.2.1`. When that version is already in the registry, the run refreshes the wheel and the source archive, checks that the bundle on the release still matches the checksum the registry recorded (restoring it when it is missing), and skips the publish step. The bundle is built with fixed entry times, so the same tag always gives the same bytes.

## Checks before merging a release

```bash
ruff check src tests && ruff format --check src tests
mypy src
pytest
git-into-gsoc setup --dry-run --assistant all
```

The CI matrix already runs these on Linux, macOS, and Windows for every pull request.

[Guide contents](README.md) · [Contributing](../CONTRIBUTING.md)
