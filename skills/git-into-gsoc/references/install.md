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
and copies this skill into the repository's `.agents`, `.cursor`, and `.claude`
folders. The `source` line turns the tool on in the current terminal; repeat
it in every new terminal. `doctor` prints the version, where cache and progress
files live, and whether a GitHub token was found.

To copy the skill into your home folders as well (`~/.agents`, `~/.cursor`,
`~/.claude`, `~/.codex`, and `~/.gemini` when present), run
`./install.sh --skill-only --user-skills` from the repository. Existing copies
of this skill are replaced.

Package only, no skill copies:

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

## Connect an assistant over MCP

MCP (Model Context Protocol) lets an assistant call the tool directly. The
server runs on the person's computer and reads public data; it never posts to
GitHub. Register it with the full path to the executable and the single
argument `mcp`:

- macOS, Linux, WSL: `/absolute/path/to/git-into-gsoc/.venv/bin/git-into-gsoc`
- Windows: `C:\path\to\git-into-gsoc\.venv\Scripts\git-into-gsoc.exe`

[mcp.example.json](../assets/mcp.example.json) shows the shape for clients
that read a JSON file, such as Cursor. Replace the placeholder path and merge
the entry into the existing configuration. For Claude Code, Codex CLI, and
Gemini CLI commands, follow the repository's
[assistant setup guide](https://github.com/anandkaranubc/git-into-gsoc/blob/main/docs/guide/03-connect-your-ai-assistant.md).

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
