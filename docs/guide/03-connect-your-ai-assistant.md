# 3. Connect your AI assistant (optional)

Skip this page if you prefer the terminal. Both routes use the same underlying tools.

There are two separate parts:

- An **Agent Skill** is a folder of written instructions that teaches an assistant how to coach you through GSoC without inventing organizations or encouraging spam contributions.
- **Model Context Protocol (MCP)** lets an assistant call tools, such as organization search or issue availability. This project's MCP server runs on your computer and reads public data from the official GSoC site, the organization archive, and GitHub. It can also save local progress.

An assistant that can run terminal commands can also use the skill with the CLI directly.

## One command does both

```bash
git-into-gsoc setup
```

Setup detects the assistants on your machine, copies the skill into each one's skills folder, and registers the MCP server in each one's configuration file, merging with whatever is already there and keeping a `.bak` copy. It prints a table of what it created, updated, or left unchanged. Useful variations:

```bash
git-into-gsoc setup --dry-run                      # preview only
git-into-gsoc setup --assistant claude-code        # one assistant (claude-code, cursor, codex, gemini, antigravity, windsurf, vscode, all)
git-into-gsoc setup --scope project                # inside the current repository instead of your home folder
git-into-gsoc setup --no-mcp                       # skill only
git-into-gsoc doctor                               # shows which assistants have the skill and where MCP is registered
```

For Claude Code at user scope, setup runs `claude mcp add` for you when the `claude` command is installed; otherwise it prints the exact command to run. Then restart your assistant.

Skill discovery depends on your assistant version. If it does not find the skill, ask it to read the `SKILL.md` file inside the folder that `doctor` prints as "skill source".

## Other ways to connect

You do not have to install anything locally for some assistants:

- **Claude Code plugin**: `/plugin marketplace add anandkaranubc/git-into-gsoc`, then `/plugin install git-into-gsoc@git-into-gsoc` installs the skill and the MCP server together. It runs the server with [uv](https://docs.astral.sh/uv/) straight from this repository, so uv must be installed.
- **Gemini CLI extension**: the repository ships `gemini-extension.json`; install it from the repository URL with Gemini CLI's extension command (see [Gemini CLI's extension documentation](https://geminicli.com/docs/extensions/)).
- **MCP registry**: clients that browse the public MCP registry can find the server as `io.github.anandkaranubc/git-into-gsoc`; every release publishes an updated entry and a bundle automatically.

`setup` remains the right choice when you want the skill in a specific assistant's folder or the server registered in a project. To undo it later, run `git-into-gsoc setup --remove` with the same `--scope` and `--assistant` options; it deletes only what setup created and leaves the rest of each config file alone.

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

## Verify the connection

Ask your assistant:

```text
Use the git-into-gsoc skill and call gsoc_program_info.
Tell me the current GSoC phase and whether the dates are official or estimates.
Tell me if the tool is unavailable.
```

You should see a tool call and a short, sourced answer. Then try `gsoc_search_orgs` with `technologies="python"` and `limit=3` to check network access. A confident answer alone is not evidence of a connection; the skill tells the assistant to say when data is missing.

The assistant normally starts and stops the server itself. If you run `git-into-gsoc mcp` in a terminal, it waits for protocol input rather than showing a chat interface. Press Ctrl+C to stop it.

## GitHub token for the assistant

The server looks for a token the same way the CLI does: `GIG_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN` in its environment, then a `.env` file in the folder it starts in, then `gh auth token` if the GitHub CLI is logged in. Because the assistant launches the server, the GitHub CLI route is the most reliable: it does not depend on which terminal exported a variable. If you must pass a token explicitly, use your assistant's environment-variable settings and never put a real token in a committed file or paste it into chat. Project-scope files such as `.mcp.json` and `.cursor/mcp.json` contain machine-specific paths and are ignored by Git in this repository. See [configuration](../configuration.md).

[Next: find organizations](04-find-organizations.md) · [Troubleshooting](../troubleshooting.md) · [MCP tool reference](../mcp.md) · [Guide contents](../README.md)
