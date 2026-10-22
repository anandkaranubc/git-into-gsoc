# Releasing

Releases are cut by [Release Please](https://github.com/googleapis/release-please) from Conventional Commits on `main`. A maintainer does two things by hand: checks the embedded data is fresh, and merges the release pull request. Publishing, release assets, the registry entry, and plugin versions follow by themselves. This page is for maintainers; contributors need only [CONTRIBUTING.md](../CONTRIBUTING.md).

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

Release Please keeps a pull request titled `chore(main): release X.Y.Z` open whenever `main` has unreleased commits. This repository gives Release Please a token of its own, the `RELEASE_PLEASE_TOKEN` secret, so CI and CodeQL start on that pull request by themselves. Release Please does not refresh its pull request for `chore:` or `ci:` commits, so when the last merge was one of those, update the branch from the pull request page before you merge.

Without the secret, `release.yml` falls back to the built-in Actions token. GitHub does not start CI on a branch pushed with that token, and the branch rules require passing checks. Then trigger the checks yourself: close and reopen the pull request, or rebase its branch onto `main` and push it (which also picks up any test or manifest fixes that landed after the bot last refreshed it).

To set up the secret, or to replace an expired token:

1. Create a fine-grained personal access token at https://github.com/settings/personal-access-tokens/new. Choose the resource owner `anandkaranubc`, **Only select repositories** with `git-into-gsoc`, and set **Contents**, **Issues**, and **Pull requests** to **Read and write**. Release Please uses Issues for the labels it puts on its pull requests. Pick an expiration date you will remember.
2. Store it: run `gh secret set RELEASE_PLEASE_TOKEN --repo anandkaranubc/git-into-gsoc` and paste the token when asked. It is not shown on screen.

Release pull requests then show as opened by you, and CI and CodeQL run on them like on any other pull request. When the token expires, the Release Please step fails with an authentication error. Create a new token and set the secret again, or delete the secret to go back to closing and reopening.

Release Please updates `CHANGELOG.md`, the version in `pyproject.toml`, `src/git_into_gsoc/__init__.py`, and the plugin manifests. While the project is below 1.0, `feat:` commits bump the minor version and `fix:` commits bump the patch version. Merging that pull request creates the Git tag and the GitHub release.

## 3. Publish to PyPI (automatic)

The release workflow builds the wheel and the source archive and publishes them to [PyPI](https://pypi.org/project/git-into-gsoc/) with [trusted publishing](https://docs.pypi.org/trusted-publishers/), which needs no stored token. It has done so since version 0.14.1. If the `Publish to PyPI` job fails, it shows in red without failing the release, and its run summary says what to check; the GitHub release and its assets are published either way. A green `Publish to PyPI` job always means the upload happened. To retry a failed upload, re-run that job: `gh run rerun <run id> --failed`. PyPI never accepts the same version twice, so a version that did upload cannot be replaced.

The trusted publisher is already set up. A fork, or a new owner, sets it up once like this:

1. On PyPI, open your account's **Publishing** page and add a pending publisher with project name `git-into-gsoc`, owner `anandkaranubc`, repository `git-into-gsoc`, workflow `release.yml`, and environment `release`.
2. On GitHub, create an environment named `release` under **Settings > Environments** (no secrets needed; optionally require a reviewer).
3. Merge the next release pull request. The `Publish to PyPI` job runs under that environment and uploads the wheel.

The PyPI page shows `README.md`. PyPI does not have the rest of the repository, so the build rewrites relative images to raw GitHub files and relative links to GitHub pages (the `fancy-pypi-readme` settings in `pyproject.toml`). A version's page never changes after upload, so a README fix reaches PyPI with the next release. CI builds the package and runs `twine check --strict` on every pull request.

People can install with `uv tool install git-into-gsoc` or `pipx install git-into-gsoc`. The installer scripts use PyPI only for the latest GitHub release, and only when PyPI's provenance record says this repository's workflow published it. PyPI checks that attestation on upload, and the publish action creates it by default with trusted publishing. When the check fails, for example because the upload for the newest release failed, the installers use the wheel attached to the GitHub release instead. Every release carries the wheel and the source archive as release assets, so anyone can also install a pinned version by URL (see the [install guide](guide/02-install.md)).

## 4. Release assets and the MCP registry (automatic)

Merging the release pull request also starts `Release assets and MCP registry` (`.github/workflows/mcp-registry.yml`). The release workflow dispatches it with the new tag. It has no `release` trigger of its own: a release made with the built-in token fires no event, and one made with `RELEASE_PLEASE_TOKEN` would start it twice. For a release you create by hand, run it from the Actions tab. The workflow checks out the tagged source, builds the wheel and source archive with `python -m build` and the MCPB bundle with `scripts/build_mcpb.py`, and uploads all three as release assets. A **wheel** is Python's ready-to-install package file, so `uv tool install <wheel URL>` or `pipx install <wheel URL>` installs that exact release without PyPI. The workflow then rewrites `server.json` to list the bundle and the PyPI package, and publishes with `mcp-publisher login github-oidc`. Nothing to configure. The registry accepts the PyPI package only after PyPI serves that version with the README's `mcp-name` line, so the workflow waits up to 10 minutes for the `Publish to PyPI` job. The registry's own view of PyPI can lag a few minutes more, so when it answers that the version was not found, the workflow tries again every minute for up to 10 minutes. If PyPI still does not have it by then, the entry lists only the bundle and the run shows a warning. A registry version cannot be changed later, so fix the PyPI upload before the next release.

The workflow downloads a fixed `mcp-publisher` release and checks it against its published checksum before running it. To move to a newer release, change `MCP_PUBLISHER_VERSION` and `MCP_PUBLISHER_SHA256` in the workflow, taking the checksum from the `mcp-publisher_linux_amd64.tar.gz` line in that release's `registry_<version>_checksums.txt`.

To rebuild the assets for a tag, run the workflow from the Actions tab with the tag name, or `gh workflow run mcp-registry.yml -f tag=v0.2.1`. When that version is already in the registry, the run refreshes the wheel and the source archive, checks that the bundle on the release still matches the checksum the registry recorded (restoring it when it is missing), and skips the publish step. The bundle is built with fixed entry times, so the same tag always gives the same bytes.

## 5. Plugins and one-click links (automatic)

Release Please also bumps `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.github/plugin/plugin.json`, `gemini-extension.json`, and `server.json`, so Claude Code, Codex, Copilot, and Gemini CLI offer the update. The one-click install buttons run the newest release from PyPI, and the Claude Desktop button downloads the newest release's bundle, so they need no change at release. See [distribution](distribution.md) for how the manifests are generated and checked, and for directory listings that need the owner.

## Checks before and after a release

CI already ran the [standard checks](../CONTRIBUTING.md#make-a-change) on every merged pull request. Before merging the release pull request, also run `git-into-gsoc setup --dry-run --assistant all` from a checkout of `main`, so a broken assistant setup never reaches a release.

Unit tests never touch the network. After a release, run the **Live journeys** workflow from the Actions tab (it also runs every Monday). It installs the newest release on Linux, macOS, and Windows and runs beginner commands against live GitHub, GitLab, and GSoC data with `scripts/live_journeys.py`. A crash fails it. A step marked drift ran fine but gave a different answer, because live data changed; read it and update the step if the new answer is right. Run the same script on your own computer with `python scripts/live_journeys.py`. The same workflow also installs the newest release while hiding it from PyPI (`UV_EXCLUDE_NEWER`), the few minutes after a release when PyPI's index has not caught up, and checks on all three systems that the installers fall back to the wheel attached to the GitHub release.

[Guide contents](README.md) · [Contributing](../CONTRIBUTING.md)
