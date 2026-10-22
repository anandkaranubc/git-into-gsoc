# Install the tool and connect an assistant

This skill works as written guidance on its own. Live searches need the Python
package. The repository's [installation guide](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide/02-install.md)
has the full walkthrough, Windows steps, and troubleshooting.

## Quick install

The one-line installer needs only an internet connection: no Git, and no Python
unless the person already has it. Give the person the command to run in their own
terminal; do not run it for them. Say what it does first, because it pipes a
script into a shell, and mention that they can read the script at the same URL.

On macOS, Linux, or WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
```

On Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
```

It installs the newest release from PyPI (or from GitHub when PyPI lags) with uv
or pipx, or with Python 3.11 or newer into a private folder. With none of them,
it offers to install [uv](https://docs.astral.sh/uv/), a free tool that brings
its own Python. Then it runs `git-into-gsoc setup`, which connects every
assistant it finds. After it finishes, open a new terminal and run
`git-into-gsoc doctor`. It prints the version, where cache and progress files
live, whether a GitHub token was found, and which assistants have the skill and
the MCP server.

People who already use uv or pipx can install the
[PyPI package](https://pypi.org/project/git-into-gsoc/) themselves:

```bash
uv tool install git-into-gsoc    # or: pipx install git-into-gsoc
git-into-gsoc setup
```

Contributors who cloned the repository can run `./install.sh` (or
`.\install.ps1` on Windows) from the clone instead. It installs the package
into `.venv` inside the clone and sets up assistants for that folder only.

## GitHub token (optional)

Without a token, GitHub allows 60 requests per hour, enough to try the tool.
With one, 5,000. The tool looks for a token in this order: `GIG_GITHUB_TOKEN`,
`GITHUB_TOKEN`, or `GH_TOKEN` in the environment or in a `.env` file in the
current folder, then the GitHub CLI (`gh auth token`) when `gh` is installed
and logged in. `doctor` reports which source it used without printing the
token. Never paste a token into chat.

## Install inside an assistant, without the terminal tool

Most assistants can install the skill and the MCP server together as a plugin
or extension. Each needs [uv](https://docs.astral.sh/uv/) to start the server:

- Claude Code: `claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc`
- Codex: `codex plugin marketplace add anandkaranubc/git-into-gsoc`, then `codex plugin add git-into-gsoc@git-into-gsoc`
- Copilot CLI: `copilot plugin marketplace add anandkaranubc/git-into-gsoc`, then `copilot plugin install git-into-gsoc@git-into-gsoc`
- Antigravity: `agy plugin install https://github.com/anandkaranubc/git-into-gsoc`
- Gemini CLI, paid plans only: `gemini extensions install https://github.com/anandkaranubc/git-into-gsoc`.
  Since 18 June 2026 it refuses free Google accounts and Google AI Pro or Ultra
  plans, so point those people to Antigravity.

The repository's [assistant page](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/assistants.md)
covers VS Code, Cursor, Windsurf, Claude Desktop, and others, with update and
removal steps.

## Connect an assistant

MCP (Model Context Protocol) lets an assistant call the tool directly. The
server runs on the person's computer and reads public data; it never posts to
GitHub.

`git-into-gsoc setup` copies this skill and registers the MCP server for every
assistant it detects: Claude Code, Codex, Cursor, VS Code and Copilot CLI,
Gemini CLI, Antigravity, and Windsurf (Devin Desktop). Most of them read one
shared copy in `~/.agents/skills`. When Claude Code's `claude` command is not
installed, setup prints the command to register the server by hand. An
assistant that already has the git-into-gsoc plugin is left to the plugin.

```bash
git-into-gsoc setup                       # every detected assistant, user-wide
git-into-gsoc setup --assistant cursor    # one assistant
git-into-gsoc setup --scope project       # only inside the current project folder
git-into-gsoc setup --dry-run             # show what would change
```

Existing configuration files are merged, never replaced, and a `.bak` copy is
written first. Running it again reports "unchanged". `--no-skill` and
`--no-mcp` limit it to one half of the job. From a clone, `./install.sh`
runs the project-scoped setup and `./install.sh --user-skills` runs the
user-wide one.

If the installed version has no `setup` command, register the server by hand.
The command is the full path to the executable (`command -v git-into-gsoc`
prints it; on Windows, `(Get-Command git-into-gsoc).Source`) with the single
argument `mcp`. Without the terminal tool, any MCP client can run
`uvx git-into-gsoc@latest mcp`, which needs only uv.
[mcp.example.json](../assets/mcp.example.json) shows the shape for clients
that read a JSON file, such as Cursor. The repository's
[assistant setup guide](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide/03-connect-your-ai-assistant.md)
has the commands for each client.

Running `git-into-gsoc mcp` by hand shows nothing: the server waits for an
assistant to talk to it. Press Ctrl+C to stop it. Normally the assistant
starts and stops it.

## Check the connection

Ask the assistant to call `gsoc_journey_guide` with `phase="learn"` (works
offline), then `gsoc_search_orgs` with `technologies="python"` and `limit=3`
(needs the network). Look for real tool output in the response. A confident
answer without a tool call is not a connection.

For settings, cache behavior, and where progress is saved, see the
repository's [configuration guide](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/configuration.md).
