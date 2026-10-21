# Troubleshooting

Start with the symptom below. Run commands from the downloaded repository unless a step says otherwise. If you are still stuck, the last section explains how to ask for help.

## `git-into-gsoc: command not found`

Activate the environment in the terminal you are using:

```bash
source .venv/bin/activate
git-into-gsoc --version
```

Or use `.venv/bin/git-into-gsoc --version` directly. On Windows PowerShell use `.\.venv\Scripts\git-into-gsoc.exe --version`. If the executable is missing, repeat the [installation steps](guide/02-install.md). Installing in one terminal does not activate another terminal.

## Python is missing, too old, or cannot create `.venv`

Run `python3 --version` (PowerShell: `py -3 --version`) and confirm Python 3.11 or newer. Install a supported version from [Python](https://www.python.org/downloads/). Some Linux distributions package `venv` separately; install the matching package if Python reports that it is missing.

To choose an already-installed Python on macOS or Linux:

```bash
PYTHON=python3.12 ./install.sh --no-user-skills
```

The installer reuses an existing `.venv`. If it was created with an older Python, close assistants using it, deactivate it if active, and move it aside before reinstalling:

```bash
mv .venv .venv.backup
PYTHON=python3.12 ./install.sh --no-user-skills
source .venv/bin/activate
```

Keep your source files in place. This does not reset your separately stored progress.

## `./install.sh`: permission denied or file not found

Make sure you are inside the cloned repository. Try `bash install.sh --no-user-skills`. In PowerShell, use the manual Windows instructions; the installer is a Bash script.

## Installation cannot download dependencies

Check your internet connection and the first error from pip. If a network proxy or certificate is required, follow your network administrator's instructions. Retry the installer after fixing connectivity. Do not use `sudo pip` or disable certificate checking to get past the error.

## `error: GitHub API rate limit exceeded`

The message says when the limit resets. Cached results keep working meanwhile. If the hint says to run `gh auth login` or set `GITHUB_TOKEN`, you are unauthenticated and limited to 60 requests per hour; see [configuration](configuration.md). A **secondary rate limit** means too many searches in a short time; a token does not remove it, so wait a few minutes. Narrow searches with `--repo` and a small `-n` to use fewer requests. `doctor` shows the main allowance.

## `error: HTTP 401` or a token that seems ignored

The token is invalid or expired. Run `gh auth login` again, replace the token, or remove it so the tool falls back to the next source:

```bash
unset GITHUB_TOKEN GH_TOKEN
```

Also remove a token stored in `.env` if you want to stop using it. Restart the assistant's MCP server after changing settings. Do not share the token when asking for help.

## `error: HTTP 404`, no matching organization, or no issues

Check spelling. A repository argument looks like `sympy/sympy` or a GitHub URL. `issues --org` takes a GitHub login; `repos` and `org` take the GSoC organization name or a GitHub login. Private or deleted repositories also return 404. `issue` refuses pull-request numbers and tells you so.

For organization searches, try a broader `--query` or fewer technologies. The tool cannot discover future participants before Google announces them; until then it shows the latest official list and says so. If the official site and the archive are both unavailable, the error names the source; use the [official GSoC directory](https://summerofcode.withgoogle.com) and retry later.

An empty issue search does not mean the project has no useful work. Try `--label` with the repository's own beginner label (shown by `repo`), `--scope all`, or browse the issue tracker and contribution guide. See [how to choose an issue](guide/05-choose-an-issue.md).

## Results are old or an issue is already taken

GitHub responses are cached for an hour and revalidated after that. For a fresh check, use `GIG_CACHE_TTL_SECONDS=0` for one command or `git-into-gsoc cache --clear`. Restart an MCP server to clear its in-memory organization data. Even fresh results cannot prove availability: the tool reads up to 100 timeline events and maintainers may coordinate elsewhere. Read the live issue discussion before starting.

## "Ideas page not readable"

Some organizations host ideas on wikis that block automated readers. `repos` then ranks by activity and beginner issues only, and `org` still shows the ideas URL for you to open in a browser.

## MCP seems stuck or the assistant cannot find the tool

`git-into-gsoc mcp` waits for protocol input. It is not an interactive chat command. Press Ctrl+C if you started it manually, then let your assistant launch it.

Check that the server setting uses the full executable path and `args: ["mcp"]`, that the path still exists, and that running that executable with `--version` succeeds. A moved repository needs an updated path. Restart the assistant and inspect its server status. Skill discovery and MCP registration are separate; use the [assistant guide](guide/03-connect-your-ai-assistant.md) to check both.

## Progress will not load

Find the data directory with `doctor`. Back up `progress.json` before making changes. An incomplete manual edit can make the JSON invalid. Restore a working backup, or rename the file and let the next save create a fresh one. See [local data](configuration.md).

## Ask for help

[Open a bug report](https://github.com/anandkaranubc/git-into-gsoc/issues/new?template=bug_report.yml) with your operating system, Python version, tool version, the command you ran, what you expected, and the error text. Include an assistant name and server status if relevant. Remove tokens and private paths or notes you do not want to share. You do not need to diagnose the cause first.

For project-specific contribution questions, use that project's preferred community channel. For program rules, consult the [official GSoC resources](https://developers.google.com/open-source/gsoc/resources).

[Guide contents](README.md)
