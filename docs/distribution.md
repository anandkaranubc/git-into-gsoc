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

All plugin manifests, `server.json`, and the install buttons in `README.md` and `docs/assistants.md` are written from one definition, `src/git_into_gsoc/install/distribution.py`. The server reads its own description and icons from there too, so assistants and directories show the same name, text, and logo. After changing it:

```bash
python scripts/sync_integrations.py           # rewrite the files
python scripts/sync_integrations.py --check   # what the tests run
```

### Launch commands

- **Plugins and extensions** run the server from their own installed copy: `uvx --from ${CLAUDE_PLUGIN_ROOT}`, `uvx --from ${extensionPath}`, or, for Codex, `uvx --from .` with `cwd: "."`. The server then always matches the skill next to it, updates arrive with the plugin, and nothing is cloned when it starts.
- **One-click buttons and copied configs** run the newest PyPI release: `uvx git-into-gsoc@latest mcp`. They need only uv, and uv checks PyPI for a newer release at every start. Before the package was on PyPI they ran `main` from GitHub, which also needed Git.
- **`git-into-gsoc setup`** writes the absolute path of the installed command, which works offline and starts fastest.

## What happens at release

Release Please bumps `version` in `pyproject.toml`, `src/git_into_gsoc/__init__.py`, both plugin manifests, `gemini-extension.json`, and `server.json`. After the release:

- `release.yml` uploads the wheel and source archive to PyPI, and dispatches `mcp-registry.yml`, which attaches the wheel, source archive, and `git-into-gsoc.mcpb` to the release and publishes the registry entry. The committed `server.json` lists only the PyPI package, with no version, which means the newest release. The workflow keeps every other field and replaces the package list with that release's bundle and its PyPI version. The registry accepts a PyPI package only after PyPI serves that version, so the workflow waits up to 10 minutes for it, and retries for up to 10 more when the registry still answers that the version was not found. If it never does, the entry lists only the bundle and the run shows a warning.
- Claude Code, Codex, and Copilot see the new `version` and offer the update. Gemini CLI compares release tags, so `--auto-update` installs pick it up at the next start.

## Compatibility checks

`scripts/check_agents.py` installs the plugin, and with `--setup` runs `git-into-gsoc setup`, for every agent command it finds. Each agent gets a throwaway home folder, with token variables removed and no model calls. It then asks the agent what it registered and checks that the server answers. Before installing from a checkout, it also runs each format's own validator: `claude plugin validate --profile directory` (the checks Anthropic's plugin directory runs on a submission), `gemini extensions validate`, and, when Node.js is installed, the MCP bundle validator `@anthropic-ai/mcpb validate`. `tests/unit/test_manifests.py` checks `server.json` against a copy of the registry's schema in `tests/fixtures/`. `scripts/mcp_smoke.py` is the MCP client the script uses; it works against any launch command:

```bash
python scripts/check_agents.py --setup              # this checkout, every agent installed here
python scripts/check_agents.py --remote --only codex  # what people get from GitHub
python scripts/mcp_smoke.py -- uvx --from . git-into-gsoc mcp
```

`.github/workflows/agents.yml` runs it on Linux with pinned versions of Claude Code, Codex, Gemini CLI, and Copilot CLI, plus the current Antigravity CLI, Cursor agent CLI, and VS Code from their vendors' installers, whenever the files they read change. It also checks the one-click button configs and the Claude Desktop bundle. Every Monday it also runs with their newest releases and installs from GitHub, because agents change their formats often. Bump the pinned versions in that workflow from time to time.

## Where people can find it

Checked on 2026-10-22. Listings change without notice, so re-check before relying on a row.

### Listed, nothing to do

| Where | How it stays current |
|---|---|
| [PyPI](https://pypi.org/project/git-into-gsoc/) | Every release since 0.14.1, by trusted publishing |
| [Official MCP registry](https://registry.modelcontextprotocol.io/v0.1/servers?search=git-into-gsoc) | Every release, by `mcp-registry.yml`, with the bundle and the PyPI package |
| [Glama](https://glama.ai/mcp/servers/anandkaranubc/git-into-gsoc) | Indexed by Glama itself. Not claimed yet (see below) |
| `gh skill search gsoc` | GitHub code search finds `skills/git-into-gsoc/SKILL.md` |

### Waiting on someone else

| Where | What it reaches | State |
|---|---|---|
| GitHub MCP registry | VS Code's `@mcp` gallery, Copilot CLI's `/mcp search`, and the registry setting in JetBrains, Eclipse, and Xcode | GitHub adds each new server by hand, then syncs its versions. Requested on 2026-10-22 in github/github-mcp-server discussion 1257; do not post again. Check with `curl -s "https://api.mcp.github.com/v0.1/servers?search=git-into-gsoc"` |
| Gemini CLI extension gallery | geminicli.com/extensions | The repository meets all three rules (public, the `gemini-cli-extension` topic, `gemini-extension.json` at the root). The gallery file was last rebuilt on 2026-10-16, before the topic was added. Check https://geminicli.com/extensions.json for `anandkaranubc/git-into-gsoc` |
| skills.sh | The skills.sh search | Lists a skill after people install it with `npx skills add anandkaranubc/git-into-gsoc`. There is nothing to submit |
| PulseMCP | pulsemcp.com | Submissions are paused. It says it will copy servers from the official registry when it reopens |

### Needs the owner

Each needs the repository owner's account or decision, and most are reviewed by a person. The files they need are already in the repository unless noted.

| Where | What it reaches | How |
|---|---|---|
| Anthropic plugin directory | Claude Code's built-in marketplace, so `claude plugin install git-into-gsoc` works with no `--marketplace`; also claude.ai and Cowork | Submit at claude.ai/directory/manage (paid plan). A person reviews it. Local servers are accepted only inside a plugin, not as an MCP bundle. `claude plugin validate . --profile directory` passes, and CI runs it. The README lists the network destinations under "Where the results come from" and in [sources](sources.md). Run the portal's Validate first. Per Anthropic's pre-submission checklist, expect a reviewer hold, not a refusal, for two data files over 256 KiB (`src/git_into_gsoc/data/official_orgs.json` and `org_signals.json`), `brand/favicon/favicon.ico`, the `uvx` launcher, and a GitHub token read from the environment. The local validator does not check launchers. If Validate reports "Unpinned uvx launcher", which blocks, the plugin needs another way to start the server, such as `uv run --frozen` with a committed `uv.lock` |
| Glama claim | A "claimed by its maintainer" badge and a tool score, which awesome-mcp-servers asks for | Add `glama.json` with `{"$schema": "https://glama.ai/mcp/schemas/server.json", "maintainers": ["anandkaranubc"]}`, then sign in to Glama and claim. The score also needs a Dockerfile set up on Glama's site |
| github/awesome-copilot | The default plugin marketplace in Copilot CLI and VS Code | The external-plugin issue form, with a release tag and its full commit SHA |
| Cursor Marketplace and cursor.directory | Cursor's plugin browser | cursor.com/marketplace/publish (reviewed). cursor.directory/plugins/new: sign in and paste the repository URL |
| Antigravity marketplace | Antigravity | The interest form linked from antigravity.google/docs/plugins |
| Smithery | smithery.ai | `smithery mcp publish ./git-into-gsoc.mcpb -n <namespace>/git-into-gsoc` with a Smithery account |
| mcp.so, MCP Market, mcpservers.org | Their web catalogs | A form each (mcp.so also takes a GitHub issue on chatmcp/mcpso). Free reviews take from days to six weeks |
| Cline, Kilo Code | Their in-app marketplaces | Cline: an issue on cline/mcp-marketplace with a 400x400 PNG logo. Kilo Code: a pull request adding `mcps/<id>/MCP.yaml` to Kilo-Org/kilo-marketplace |
| punkpeye/awesome-mcp-servers | A long-running list many people read | A pull request under Education. Its bot asks for a Glama listing that passes Glama's checks, so claim Glama first |
| Codex plugin directory | Codex and ChatGPT | Not open to this project: local MCP servers are accepted only from approved partners |

### Looked at, not adopted

| Idea | Why not |
|---|---|
| MCP server cards (`.well-known`, SEP-2127) | They describe remote servers only. This server runs on the person's computer |
| `llms.txt` on the project site | No assistant vendor says it reads one, and a May 2026 study of 137,210 sites found 97% of these files were never requested (https://ahrefs.com/blog/llmstxt-study/) |
| The Agent Plugins 1.0.0 root `plugin.json` | Codex, Cursor, Copilot, VS Code, and Antigravity read it, but every one of them already installs the current manifests, and Cursor expects a different folder variable (`${CURSOR_PLUGIN_ROOT}`). Revisit when an assistant stops reading the current formats; the weekly Agents run would show it |
| A Dockerfile for Docker's MCP catalog | The server saves progress to a file on the person's computer, which a throwaway container would lose, and an image is one more thing to keep updated |
| Buttons for Goose, LM Studio, Raycast, and Cherry Studio | Their install links use app schemes such as `goose://`, which GitHub removes from rendered Markdown. `goose_install_link()` in `distribution.py` builds Goose's link for a page that keeps such links |

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
