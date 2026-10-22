# 3. Connect your AI assistant (optional)

Skip this page if you prefer the terminal. Both routes use the same underlying tools.

An assistant gets two things:

- An **Agent Skill**, a folder of written instructions that teaches it how to coach you through GSoC without inventing organizations or encouraging spam contributions.
- The **MCP server**. MCP (Model Context Protocol) is a standard way for an assistant to call tools. The server is a small program on your computer that lets the assistant run the same searches and checks as the terminal command. It reads public data and can save your local progress.

## Connect it

**If you ran the one-line installer** in [chapter 2](02-install.md), it already ran `git-into-gsoc setup` for every assistant it found. Restart your assistant and skip to [your first question](#your-first-question). Installed another assistant since? Run setup again:

```bash
git-into-gsoc setup                                # every assistant it finds
git-into-gsoc setup --dry-run                      # preview only
git-into-gsoc doctor                               # which assistants have the skill and the server
```

Setup puts the skill in the folders your assistants read and registers the server in each one's configuration file. It merges with whatever is already there and keeps a `.bak` copy. The [command reference](../cli.md#setup-and-maintenance) lists its options.

**If you only want it inside your assistant**, install it as a plugin or extension with the assistant's own command, for example `claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc` for Claude Code. You do not need the installer, only [uv](https://docs.astral.sh/uv/), a free tool that starts the server. [Use git-into-gsoc in your AI assistant](../assistants.md) has the command for every assistant, how to update and remove each one, and how to set one up by hand when setup cannot write its file.

## Your first question

Restart the assistant, then ask in your own words, for example:

```text
I want to do Google Summer of Code. I know Python and like science. Where do I start?
```

You should see tool calls such as `gsoc_program_info` and `gsoc_search_orgs`, then a short answer with real organizations, links, and one next step. Your assistant may ask permission the first time it uses each tool. Choose the answer that stops it asking for that tool, so each question comes up once.

The server also offers ready-made prompts. `get_started` asks you a few questions and suggests organizations, the same as `git-into-gsoc start` in a terminal. In Claude Code, prompts appear in the `/` menu with names like `/mcp__git-into-gsoc__get_started`; other assistants list them in their own prompt or command menus. The [MCP reference](../mcp.md) lists all of them.

## Check the connection

If the answer has no tool calls or links, ask directly:

```text
Use the git-into-gsoc skill and call gsoc_program_info.
Tell me the current GSoC phase and whether the dates are official or estimates.
Tell me if the tool is unavailable.
```

You should see a tool call and a short, sourced answer. A confident answer alone is not evidence of a connection; the skill tells the assistant to say when data is missing. If the assistant does not find the skill, ask it to read the `SKILL.md` file inside the folder that `git-into-gsoc doctor` prints as "skill source". `doctor` also shows which assistants have the server registered, and [troubleshooting](../troubleshooting.md#mcp-seems-stuck-or-the-assistant-cannot-find-the-tool) covers the rest.

## GitHub token for the assistant

The server looks for a token the same way the terminal command does, and the easiest route is the same: install [GitHub's `gh` tool](https://cli.github.com/) and run `gh auth login` once. Because the assistant launches the server, that route does not depend on which terminal exported a variable. Never put a real token in a committed file or paste it into chat. [Configuration](../configuration.md) has the other ways.

[Next: find organizations](04-find-organizations.md) · [Guide contents](../README.md)
