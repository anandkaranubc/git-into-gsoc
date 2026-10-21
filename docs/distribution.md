# Distribution: how git-into-gsoc reaches each assistant

This page is for maintainers. People who want to install the tool should read [use git-into-gsoc in your AI assistant](assistants.md).

## One repository, every native format

Several assistants read another assistant's plugin format, so a few files cover many tools:

| File | Read by |
|---|---|
| `.claude-plugin/plugin.json` and `marketplace.json` | Claude Code, Cursor, GitHub Copilot CLI, VS Code agent plugins, Devin, Factory Droid, Antigravity's converter, and Codex when `.codex-plugin` is missing |
| `.codex-plugin/plugin.json` | Codex. It is read first, and only it can carry Codex's start timeout and the variables to pass on |
| `gemini-extension.json` | Gemini CLI, Qwen Code, Antigravity's converter |
| `server.json` | The official MCP registry, and the directories that copy it (Glama, PulseMCP) |
| `skills/git-into-gsoc/` | Every host above finds it in the default `skills/` folder; `npx skills add` and `gh skill install` read it too |
| `.github/workflows/mcp-registry.yml` builds `git-into-gsoc.mcpb` | Claude Desktop and other hosts that install MCP bundles |

All plugin manifests, and the install buttons in `README.md` and `docs/assistants.md`, are written from one definition, `src/git_into_gsoc/install/distribution.py`. After changing it:

```bash
python scripts/sync_integrations.py           # rewrite the files
python scripts/sync_integrations.py --check   # what the tests run
```

### Launch commands

- **Plugins and extensions** run the server from their own installed copy: `uvx --from ${CLAUDE_PLUGIN_ROOT}`, `uvx --from ${extensionPath}`, or, for Codex, `uvx --from .` with `cwd: "."`. The server then always matches the skill next to it, updates arrive with the plugin, and nothing is cloned when it starts.
- **One-click buttons and copied configs** run `uvx --from git+https://github.com/anandkaranubc/git-into-gsoc@main`. `main` changes only through reviewed pull requests that pass CI. A `stable` branch that follows releases was tried and dropped: the built-in Actions token may not create or move a branch whose commits change workflow files, so it would need a personal token stored as a secret.
- **`git-into-gsoc setup`** writes the absolute path of the installed command, which works offline and starts fastest.

When the package is on PyPI, switch `remote_command()` to `uvx git-into-gsoc@latest mcp`, run the sync script, and add a `pypi` package to `server.json` (see below).

## What happens at release

Release Please bumps `version` in `pyproject.toml`, `src/git_into_gsoc/__init__.py`, both plugin manifests, `gemini-extension.json`, and `server.json`. After the release:

- `release.yml` dispatches `mcp-registry.yml`, which attaches the wheel, source archive, and `git-into-gsoc.mcpb` and publishes the registry entry.
- Claude Code, Codex, and Copilot see the new `version` and offer the update. Gemini CLI compares release tags, so `--auto-update` installs pick it up at the next start.

## Compatibility checks

`scripts/check_agents.py` installs the plugin, and with `--setup` runs `git-into-gsoc setup`, for every agent command it finds. Each agent gets a throwaway home folder, with token variables removed and no model calls. It then asks the agent what it registered and checks that the server answers. `scripts/mcp_smoke.py` is the MCP client it uses; it works against any launch command:

```bash
python scripts/check_agents.py --setup              # this checkout, every agent installed here
python scripts/check_agents.py --remote --only codex  # what people get from GitHub
python scripts/mcp_smoke.py -- uvx --from . git-into-gsoc mcp
```

`.github/workflows/agents.yml` runs it on Linux with pinned versions of Claude Code, Codex, Gemini CLI, and Copilot CLI, plus the current Antigravity CLI, Cursor agent CLI, and VS Code from their vendors' installers, whenever the files they read change. It also checks the one-click button configs and the Claude Desktop bundle. Every Monday it also runs with their newest releases and installs from GitHub, because agents change their formats often. Bump the pinned versions in that workflow from time to time.

## Listings that need the owner

None of these has been submitted. Each needs the repository owner's account or decision, and some are reviewed by the platform. The files they need are already in the repository unless noted.

| Where | What it reaches | How |
|---|---|---|
| PyPI | `uvx git-into-gsoc`, `pip install`, VS Code's MCP gallery (it cannot install `mcpb` packages) | Add the trusted publisher in [releasing](releasing.md), then the next release uploads. Then add a `pypi` package to `server.json`: `{"registryType": "pypi", "identifier": "git-into-gsoc", "version": "<version>", "runtimeHint": "uvx", "transport": {"type": "stdio"}, "packageArguments": [{"type": "positional", "value": "mcp"}]}`, and have `mcp-registry.yml` keep it |
| Gemini CLI extension gallery | geminicli.com/extensions | Done: the GitHub topic `gemini-cli-extension` was added on 2026-10-21. The gallery crawls tagged repositories daily, so the listing appears after the next crawl; check https://geminicli.com/extensions.json for `anandkaranubc/git-into-gsoc`. Remove the topic to unlist |
| Anthropic plugin directory | claude.ai, Cowork, Claude Code (`claude-community`) | Submit at claude.ai/directory/manage (paid plan). Track a release tag or `main`. Expect a human review. The README must list the network destinations, which it does under "Where the results come from" and in [sources](sources.md) |
| GitHub MCP registry | VS Code's `@mcp` gallery, JetBrains, Visual Studio | After PyPI: post an onboarding request in github/github-mcp-server discussion 1257 or email partnerships@github.com, with the registry name and the two `curl` checks |
| github/awesome-copilot | The default plugin marketplace in Copilot CLI and VS Code | The external-plugin issue form, with a release tag and its full commit SHA |
| Cursor Marketplace and cursor.directory | Cursor's plugin browser | cursor.com/marketplace/publish (reviewed); cursor.directory/plugins/new (paste the repo URL) |
| Codex plugin directory | Codex and ChatGPT | platform.openai.com/plugins. Local MCP servers are accepted only from approved partners, so submit the skill only |
| Antigravity marketplace | Antigravity | The interest form linked from antigravity.google/docs/marketplace |
| Glama | glama.ai, and awesome-mcp-servers (which asks for a Glama score) | Claim the listing, which already exists, by adding a `glama.json` with the owner's GitHub name, then sign in. A score needs Glama to build the server from a Dockerfile |
| Smithery | smithery.ai | `smithery mcp publish ./git-into-gsoc.mcpb -n <org>/git-into-gsoc` with a Smithery account |
| Cline, Kilo Code, MCP Market, mcp.so | Their in-app marketplaces | A pull request or form each; Cline asks for a 400x400 PNG logo |

### Details most forms ask for

| Field | Value |
|---|---|
| Name | git-into-gsoc |
| One line (under 100 characters) | Evidence-based GSoC preparation: organizations, repositories, free beginner issues, proposals. |
| Description | The `DESCRIPTION` in `src/git_into_gsoc/install/distribution.py` |
| Category | Developer tools; education |
| Logo | `brand/logo/mark-tile-512.png` (512x512). For a 400x400 PNG (Cline), resize it, for example `sips -z 400 400 brand/logo/mark-tile-512.png --out logo-400.png` on macOS |
| Repository and license | https://github.com/anandkaranubc/git-into-gsoc, MIT |
| Support | https://github.com/anandkaranubc/git-into-gsoc/issues |
| Privacy policy | https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/privacy.md |
| Network destinations | summerofcode.withgoogle.com, api.gsocorganizations.dev, api.github.com, commits.ecosyste.ms, and each organization's ideas page (read only) |
| Credentials | None required; an optional GitHub token raises the rate limit and is sent only to api.github.com |
| Install command | `claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc`, or the matching command in [assistants](assistants.md) |

Already listed, with nothing to do: the official MCP registry (every release), Glama (copied from the registry), and `gh skill search gsoc`. skills.sh lists a repository once people install it with `npx skills add`.
