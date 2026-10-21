# Install the tool and connect an assistant

This skill works as written guidance on its own. Live searches need the Python
package. The repository's [installation guide](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide/02-install.md)
has the full walkthrough, Windows steps, and troubleshooting.

## Quick install (macOS, Linux, or WSL)

You need Git and Python 3.11 or newer.

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
./install.sh
source .venv/bin/activate
git-into-gsoc doctor
```

The installer creates a virtual environment in `.venv`, installs the package,
and runs the project-scoped assistant setup described below. The `source` line
turns the tool on in the current terminal; repeat it in every new terminal.
`doctor` prints the version, where cache and progress files live, whether a
GitHub token was found, and which assistants have the skill and the MCP server.

Package only, with no assistant setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows PowerShell, create the environment with `py -3 -m venv .venv` and
run `.\.venv\Scripts\git-into-gsoc.exe` wherever these notes say
`git-into-gsoc`.

## GitHub token (optional)

Without a token, GitHub allows 60 requests per hour, enough to try the tool.
With one, 5,000. The tool looks for a token in this order: `GIG_GITHUB_TOKEN`,
`GITHUB_TOKEN`, or `GH_TOKEN` in the environment or in a `.env` file in the
current folder, then the GitHub CLI (`gh auth token`) when `gh` is installed
and logged in. `doctor` reports which source it used without printing the
token. Never paste a token into chat.

## Connect an assistant

MCP (Model Context Protocol) lets an assistant call the tool directly. The
server runs on the person's computer and reads public data; it never posts to
GitHub.

`git-into-gsoc setup` copies this skill and registers the MCP server for every
assistant it detects: Claude Code, Cursor, Codex, Gemini CLI, Windsurf, and
VS Code.

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
The command is the full path to the executable
(`/absolute/path/to/git-into-gsoc/.venv/bin/git-into-gsoc`, or
`.venv\Scripts\git-into-gsoc.exe` on Windows) with the single argument `mcp`.
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
