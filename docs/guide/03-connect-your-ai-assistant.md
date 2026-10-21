# 3. Connect your AI assistant (optional)

Skip this page if you prefer the terminal. Both routes use the same underlying tools.

There are two separate parts:

- An **Agent Skill** is a folder of written instructions that teaches an assistant how to coach you through GSoC without inventing organizations or encouraging spam contributions.
- **Model Context Protocol (MCP)** lets an assistant call tools, such as organization search or issue availability. This project's MCP server runs on your computer and reads public data from the official GSoC site, the organization archive, and GitHub. It can also save local progress.

Installing the skill does not register the MCP server. An assistant that can run terminal commands can also use the skill with the CLI directly.

## Make the skill available

The [installer](02-install.md) copies the skill into `.agents/skills`, `.cursor/skills`, and `.claude/skills` inside the repository. Open the repository in your assistant and restart its session.

To copy the skill to your user folders as well, run this from the repository:

```bash
./install.sh --skill-only
```

This replaces this skill's folders in `~/.agents`, `~/.cursor`, `~/.claude`, and `~/.codex`. It also copies to `~/.gemini` when that folder or the Gemini command exists. Skill discovery depends on your assistant version. If it does not find the skill, ask it to read `skills/git-into-gsoc/SKILL.md` in this repository explicitly.

## Find the server command

After installation, run from the repository on macOS, Linux, or WSL:

```bash
"$(pwd)/.venv/bin/git-into-gsoc" --version
```

Use the full path to that executable in your assistant settings. This avoids relying on a terminal's activated environment. In Windows use the full path to `.venv\Scripts\git-into-gsoc.exe`; JSON paths need doubled backslashes or forward slashes. A WSL executable requires an assistant running in the same Linux environment.

## Choose your assistant

Run only the commands for the assistant you already use, from the repository folder.

### Cursor

Merge this entry into `~/.cursor/mcp.json`, keeping any existing servers. Replace `/absolute/path/to/git-into-gsoc` with your actual folder path. The file must contain valid JSON, without comments.

```json
{
  "mcpServers": {
    "git-into-gsoc": {
      "command": "/absolute/path/to/git-into-gsoc/.venv/bin/git-into-gsoc",
      "args": ["mcp"]
    }
  }
}
```

Restart Cursor and check its MCP settings. See [Cursor's MCP documentation](https://cursor.com/docs/mcp).

### Claude Code

```bash
claude mcp add --transport stdio git-into-gsoc -- "$(pwd)/.venv/bin/git-into-gsoc" mcp
claude mcp list
```

This uses Claude Code's default local scope. See [Claude Code's MCP documentation](https://code.claude.com/docs/en/mcp) for user-wide configuration and connection status. Claude Desktop uses separate configuration; follow its own MCP setup instructions and supply the same command and `mcp` argument.

### Codex CLI

```bash
codex mcp add git-into-gsoc -- "$(pwd)/.venv/bin/git-into-gsoc" mcp
codex mcp list
```

Restart the session after adding the server. See [Codex's MCP documentation](https://developers.openai.com/codex/mcp) for configuration details.

### Gemini CLI

```bash
gemini mcp add git-into-gsoc "$(pwd)/.venv/bin/git-into-gsoc" mcp
gemini mcp list
```

See [Gemini CLI's MCP documentation](https://geminicli.com/docs/tools/mcp-server/) for configuration scope and status.

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

The server resolves a token the same way the CLI does: `GITHUB_TOKEN` or `GH_TOKEN` in its environment, then `gh auth token` if the GitHub CLI is logged in. Because the assistant launches the server, the GitHub CLI route is the most reliable: it does not depend on which terminal exported a variable. If you must pass a token explicitly, use your assistant's environment-variable settings and never put a real token in a committed file or paste it into chat. See [configuration](../configuration.md).

[Next: find organizations](04-find-organizations.md) · [Troubleshooting](../troubleshooting.md) · [MCP tool reference](../mcp.md) · [Guide contents](../README.md)
