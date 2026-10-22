# 3. Connect your AI assistant (optional)

Skip this page if you prefer the terminal. Both routes use the same underlying tools.

There are two separate parts:

- An **Agent Skill** is a folder of written instructions that teaches an assistant how to coach you through GSoC without inventing organizations or encouraging spam contributions.
- **Model Context Protocol (MCP)** lets an assistant call tools, such as organization search or issue availability. This project's MCP server runs on your computer and reads public data from the official GSoC site, the organization archive, and GitHub. It can also save local progress.

An assistant that can run terminal commands can also use the skill with the CLI directly.

## Two ways to connect

**If you ran the one-line installer** from [chapter 2](02-install.md), it already ran `git-into-gsoc setup` for every assistant it found. Restart your assistant and skip to [your first question](#your-first-question). Run setup again any time you install another assistant:

```bash
git-into-gsoc setup
```

Setup detects the assistants on your machine. It puts the skill in the folders they read, and registers the MCP server in each one's configuration file. It merges with whatever is already there and keeps a `.bak` copy. Most assistants share one copy of the skill in `~/.agents/skills`, so each lists it once. It prints a table of what it created, updated, or left unchanged. Useful variations:

```bash
git-into-gsoc setup --dry-run                      # preview only
git-into-gsoc setup --assistant claude-code        # one assistant (claude-code, cursor, codex, gemini, antigravity, windsurf, vscode, all)
git-into-gsoc setup --scope project                # inside the current repository instead of your home folder
git-into-gsoc setup --no-mcp                       # skill only
git-into-gsoc setup --remove                       # undo, leaving the rest of each config file alone
git-into-gsoc doctor                               # shows which assistants have the skill and where MCP is registered
```

For Claude Code at user scope, setup runs `claude mcp add` for you when the `claude` command is installed; otherwise it prints the exact command to run. Then restart your assistant.

**If you only want it inside your assistant**, install it as a plugin or extension with your assistant's own command. You do not need the installer, only [uv](https://docs.astral.sh/uv/), a free tool that starts the server. The plugin updates with your assistant. For example:

```bash
claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc     # Claude Code
agy plugin install https://github.com/anandkaranubc/git-into-gsoc                 # Antigravity
gemini extensions install https://github.com/anandkaranubc/git-into-gsoc          # Gemini CLI, paid plans only
```

Since 18 June 2026, Gemini CLI no longer works with a free Google account or a Google AI Pro or Ultra plan. Google moved those accounts to Antigravity, so use the `agy` line instead ([Google's notice](https://docs.cloud.google.com/gemini/docs/codeassist/release-notes)).

[Use git-into-gsoc in your AI assistant](../assistants.md) has the command for every assistant (Codex, Copilot, VS Code, Cursor, Windsurf, Claude Desktop, and others), one-click buttons, and how to update and remove each one.

Skill discovery depends on your assistant version. If it does not find the skill, ask it to read the `SKILL.md` file inside the folder that `doctor` prints as "skill source".

## Doing it by hand

You only need this section if setup could not write a file for your assistant, or you prefer to see the configuration. The server command is the path `setup` and `doctor` print, for example `/home/you/.local/bin/git-into-gsoc mcp` or, from a clone, `/absolute/path/to/git-into-gsoc/.venv/bin/git-into-gsoc mcp`. Use the full path, not a terminal alias. On Windows use the full path to `git-into-gsoc.exe`; JSON paths need doubled backslashes or forward slashes.

| Assistant | What setup writes | Manual equivalent |
|---|---|---|
| Cursor | `~/.cursor/mcp.json` (or `.cursor/mcp.json` in the project) | Add `"git-into-gsoc": {"command": "<path>", "args": ["mcp"]}` under `mcpServers`; see [Cursor's MCP documentation](https://cursor.com/docs/mcp) |
| Claude Code | `claude mcp add --scope user --transport stdio git-into-gsoc -- <path> mcp`, or `.mcp.json` in the project | Run that command yourself; `claude mcp list` shows the result. See [Claude Code's MCP documentation](https://code.claude.com/docs/en/mcp). Claude Desktop has its own settings; supply the same command and `mcp` argument there |
| Codex | `[mcp_servers."git-into-gsoc"]` in `~/.codex/config.toml` (or `.codex/config.toml` in a project you trust), with `env_vars` so your token reaches the server and a 60-second start timeout | `codex mcp add git-into-gsoc -- <path> mcp`; see [Codex's MCP documentation](https://learn.chatgpt.com/docs/extend/mcp). Running `codex mcp add` again drops the extra lines |
| Gemini CLI | `~/.gemini/settings.json` (or `.gemini/settings.json` in the project), with token variables named in `env` because Gemini CLI hides them otherwise | `gemini mcp add -s user git-into-gsoc <path> mcp` (no `--` before the path); see [Gemini CLI's MCP documentation](https://geminicli.com/docs/tools/mcp-server/) |
| Antigravity | `~/.gemini/config/mcp_config.json` (or `.agents/mcp_config.json` in the project) | `agy mcp add git-into-gsoc -- <path> mcp`; see [Antigravity's MCP documentation](https://antigravity.google/docs/mcp) |
| Windsurf (Devin Desktop) | `~/.config/devin/mcp_config.json`, or `~/.codeium/windsurf/mcp_config.json` for Windsurf before it was renamed (or `.devin/mcp_config.json` in the project) | Same `mcpServers` shape as Cursor; see [Devin's MCP documentation](https://docs.devin.ai/cli/extensibility/mcp/configuration) |
| VS Code and Copilot CLI | `~/.copilot/mcp-config.json`, which VS Code's Copilot sessions and Copilot CLI both read (or `.vscode/mcp.json` in the project) | `copilot mcp add git-into-gsoc -- <path> mcp`, or `code --add-mcp '{"name":"git-into-gsoc","command":"<path>","args":["mcp"]}'` |

The skill goes into one shared folder, `~/.agents/skills`, which Codex, Cursor, Gemini CLI, Devin Desktop, VS Code, Copilot CLI, and many other tools read, plus `~/.claude/skills` for Claude Code and `~/.gemini/config/skills` for Antigravity (with `--scope project`, `.agents/skills` and `.claude/skills` inside the project). One copy per folder means each assistant lists the skill once. If older versions of setup left copies in an assistant's own folder, setup removes them. Restart the assistant after any change.

## Your first question

Restart the assistant, then ask in your own words, for example:

```text
I want to do Google Summer of Code. I know Python and like science. Where do I start?
```

You should see tool calls such as `gsoc_program_info` and `gsoc_search_orgs`, then a short answer with real organizations, links, and one next step. In a test run with Claude Code, this question gave five sourced organizations in about 20 seconds.

The server also offers ready-made prompts. `get_started` asks you a few questions and suggests organizations, the same as `git-into-gsoc start` in a terminal. In Claude Code, prompts appear in the `/` menu with names like `/mcp__git-into-gsoc__get_started`. Other assistants list them in their own prompt or command menus. The [MCP reference](../mcp.md) lists all of them.

Claude Code asks permission the first time it uses each tool. Choose the answer that stops it asking for that tool, so each question comes up once.

## Check the connection

If the answer has no tool calls or links, ask directly:

```text
Use the git-into-gsoc skill and call gsoc_program_info.
Tell me the current GSoC phase and whether the dates are official or estimates.
Tell me if the tool is unavailable.
```

You should see a tool call and a short, sourced answer. Then try `gsoc_search_orgs` with `technologies="python"` and `limit=3` to check network access. A confident answer alone is not evidence of a connection; the skill tells the assistant to say when data is missing. `git-into-gsoc doctor` in a terminal shows which assistants have the server registered.

The assistant normally starts and stops the server itself. If you run `git-into-gsoc mcp` in a terminal, it waits for protocol input rather than showing a chat interface. Press Ctrl+C to stop it.

## GitHub token for the assistant

The server looks for a token the same way the CLI does: `GIG_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN` in its environment, then a `.env` file in the folder it starts in, then `gh auth token` if the GitHub CLI is logged in. Because the assistant launches the server, the GitHub CLI route is the most reliable: it does not depend on which terminal exported a variable. If you must pass a token explicitly, use your assistant's environment-variable settings and never put a real token in a committed file or paste it into chat. Project-scope files such as `.mcp.json` and `.cursor/mcp.json` contain machine-specific paths and are ignored by Git in this repository. See [configuration](../configuration.md).

[Next: find organizations](04-find-organizations.md) · [Troubleshooting](../troubleshooting.md) · [MCP tool reference](../mcp.md) · [Guide contents](../README.md)
