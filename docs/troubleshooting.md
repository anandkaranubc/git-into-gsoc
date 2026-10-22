# Troubleshooting

Start with the symptom below. If you installed from a clone, run these commands from that folder; with the one-line installer you can run them from anywhere. If you are still stuck, the last section explains how to ask for help.

## `git-into-gsoc: command not found`

If you installed with the one-line installer, open a new terminal so your PATH (the list of folders your shell searches for commands) is refreshed. The command lives in `~/.local/bin` on macOS and Linux. If it is still missing, add that folder to your PATH once, then open a new terminal:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc    # macOS; on Linux use ~/.bashrc
```

`uv tool update-shell` or `pipx ensurepath` do the same for those tools. On Windows, the installer adds its folder to your user PATH itself; open a new PowerShell window. If you installed from a clone, activate the environment in the terminal you are using:

```bash
source .venv/bin/activate
git-into-gsoc --version
```

Or use `.venv/bin/git-into-gsoc --version` directly. On Windows PowerShell use `.\.venv\Scripts\git-into-gsoc.exe --version`. If the executable is missing, repeat the [installation steps](guide/02-install.md). Installing in one terminal does not activate another terminal.

## Python is missing, too old, or cannot create `.venv`

Run `python3 --version` (PowerShell: `py -3 --version`) and confirm Python 3.11 or newer. Install a supported version from [Python](https://www.python.org/downloads/). Some Linux distributions package `venv` separately. On Ubuntu, Debian, and WSL, creating `.venv` fails with "ensurepip is not available" until you run `sudo apt install python3-venv` (use the versioned name, such as `python3.12-venv`, if Python asks for it). Then delete the half-made `.venv` folder and run the install again.

To choose an already-installed Python on macOS or Linux:

```bash
PYTHON=python3.12 ./install.sh
```

The installer reuses an existing `.venv`. If it was created with an older Python, close assistants using it, deactivate it if active, and move it aside before reinstalling:

```bash
mv .venv .venv.backup
PYTHON=python3.12 ./install.sh
source .venv/bin/activate
```

Keep your source files in place. This does not reset your separately stored progress.

## `./install.sh`: permission denied or file not found

Make sure you are inside the cloned repository. Try `bash install.sh`. In PowerShell, run `.\install.ps1` instead; `install.sh` is a Bash script.

## PowerShell: "running scripts is disabled on this system"

Windows blocks script files by default. Run the installer with a one-time exception, which changes no settings:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The one-line `irm ... | iex` install is not affected. To activate a `.venv` in your own PowerShell window, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## "Cannot save your progress" or a permission error inside an AI assistant

Some assistants run commands in a sandbox that may not write outside your project folder. Reading still works: the tool runs without its cache, and only saving progress fails. Allow the assistant to write to the folder the error names, or point the tool at a folder inside your project, for example `GIG_DATA_DIR=.gsoc-data GIG_CACHE_DIR=.gsoc-cache`. `git-into-gsoc doctor` shows which folder cannot be written.

## Installation cannot download dependencies

Check your internet connection and the first error from pip. If a network proxy or certificate is required, follow your network administrator's instructions. Retry the installer after fixing connectivity. Do not use `sudo pip` or disable certificate checking to get past the error.

## `error: GitHub API rate limit exceeded`

The message says when the limit resets and which limit it was. A **search rate limit** is separate from the hourly allowance: GitHub permits 10 searches a minute without a token and 30 with one, and `issues` and `repos` each use at least one search, so wait a minute or narrow the search with `--repo` or `--org`. Cached results keep working meanwhile. If the hint says to run `gh auth login` or set `GITHUB_TOKEN`, you are unauthenticated and limited to 60 requests per hour; see [configuration](configuration.md). A **secondary rate limit** means too many searches in a short time; a token does not remove it, so wait a few minutes. Narrow searches with `--repo` and a small `-n` to use fewer requests. `doctor` shows the main allowance.

## Issues marked `unknown` in a list

The hourly limit can also run out partway through `issues`. The list still appears, but some issues read `unknown`, which means the tool could not check them for claims and pull requests. The note under the list then starts with how many were not checked, how long until the limit resets, and how to raise it. Without a token, one `issues` search uses 10 to 20 of the 60 hourly requests, so a few searches use it all. Run `gh auth login` once to raise the limit to 5,000, or wait for the reset and run `issue owner/repo#N` on the issue you want before you comment.

## `error: HTTP 401` or a token that seems ignored

The token is invalid or expired. Run `gh auth login` again, replace the token, or remove it so the tool falls back to the next source:

```bash
unset GIG_GITHUB_TOKEN GITHUB_TOKEN GH_TOKEN
```

Also remove a token stored in `.env` if you want to stop using it. Restart the assistant's MCP server after changing settings. Do not share the token when asking for help.

## `error: HTTP 404`, no matching organization, or no issues

Check spelling. A repository argument looks like `sympy/sympy` or a GitHub URL. `issues --org` takes a GitHub login; `repos` and `org` take the GSoC organization name or a GitHub login. Private or deleted repositories also return 404. `issue` refuses pull-request numbers and tells you so.

Run `git-into-gsoc doctor` first: it reports whether the official site, the organization archive, and the commit statistics service answer, so you know which source is down. For organization searches, try a broader `--query` or fewer technologies. The tool cannot discover future participants before Google announces them; until then it shows the latest official list and says so. If the official site and the archive are both unavailable, the error names the source; open the organization list on [summerofcode.withgoogle.com](https://summerofcode.withgoogle.com) in your browser and try again later.

An empty issue search does not mean the project has no useful work. Try `--label` with the repository's own beginner label (shown by `repo`), `--scope all`, or browse the issue tracker and contribution guide. See [how to choose an issue](guide/05-choose-an-issue.md).

## Results are old or an issue is already taken

Most GitHub responses are cached for an hour and revalidated after that; issue checks refresh after 5 minutes. For a fresh check, run `git-into-gsoc cache --clear` first (`GIG_CACHE_TTL_SECONDS` changes only the one-hour default and does not affect issue checks). Restart an MCP server to clear its in-memory organization data. Even fresh results cannot prove availability: the tool reads up to 100 timeline events and maintainers may coordinate elsewhere. Read the live issue discussion before starting.

## "Ideas page not readable"

Some organizations host ideas on wikis that block automated readers. `repos` then ranks by activity and beginner issues only, and `org` still shows the ideas URL for you to open in a browser.

## MCP seems stuck or the assistant cannot find the tool

`git-into-gsoc mcp` waits for protocol input. It is not an interactive chat command. Press Ctrl+C if you started it manually, then let your assistant launch it.

Run `git-into-gsoc doctor`: it lists which assistants have the skill and which config files register the MCP server. If yours is missing, run `git-into-gsoc setup --assistant NAME` and restart the assistant. If you moved or reinstalled the tool, re-run setup so the registered path is updated; it reports `updated` for the files it changed. A `setup` row that ends in `left as is` means setup did not change that config file. Usually the file has comments or trailing commas, which VS Code and Cursor allow but which setup will not rewrite, because rewriting would drop your comments. Setup then prints a manual step with the exact entry to paste, and `doctor` finds the entry once you add it. Before every write setup saves a `.bak` copy next to the file, and it keeps the file's permissions and any symlink. [Set up by hand](assistants.md#set-up-by-hand) has the manual equivalents.

## A plugin or one-click button installed, but the tools never appear

- `uvx: command not found`, or the server shows as failed: plugins and buttons start the server with [uv](https://docs.astral.sh/uv/). Install it (see [before you start](assistants.md#before-you-start-install-uv)), open a new terminal, and restart the assistant.
- The first start downloads what the server needs and can take up to a minute. An assistant may report it as disconnected or timed out the first time. Restart the assistant once the download is done.
- Gemini CLI shows the server as disabled: it starts MCP servers only in folders you trust. Run `/permissions` in the folder, or answer yes when it asks.
- Gemini CLI stops at sign-in with "This client is no longer supported for Gemini Code Assist for individuals": Gemini CLI now needs a paid plan. Use Antigravity instead; see [Gemini CLI](assistants.md#gemini-cli) and [Antigravity](assistants.md#antigravity).
- Codex says the server took too long to start: the plugin allows 120 seconds. A config you wrote yourself may have only Codex's default of 10. Add `startup_timeout_sec = 60` under `[mcp_servers."git-into-gsoc"]` in `~/.codex/config.toml`, or run `git-into-gsoc setup --assistant codex`, which writes it for you.
- A one-click button's server asks PyPI for the newest release each time it starts, so it needs network access. Behind a proxy, set `HTTPS_PROXY` where the assistant can see it, or use `git-into-gsoc setup`, which registers the installed command and starts offline.
- The skill is listed twice: use one route per assistant. `git-into-gsoc setup --remove --assistant NAME` takes away what setup added, and `doctor` lists every copy it finds.

## Progress will not load

If `progress.json` is damaged (for example by a manual edit), the tool keeps it as `progress.damaged-<date>.json` next to the original, prints a one-line warning, and starts a fresh file, so every command keeps working. Copy any entries you need back from the kept file. A file that cannot be read at all, because of its permissions or another program holding it, is different: the command stops with `Cannot read` and leaves the file where it is. `doctor` shows the data directory. Saves are atomic and locked, so a crash or an assistant and the CLI saving at the same moment cannot damage the file; if a save reports that another process is saving and none is running, delete the `progress.json.lock` file it names. See [local data](configuration.md).

## Ask for help

[Open a bug report](https://github.com/anandkaranubc/git-into-gsoc/issues/new?template=bug_report.yml) with your operating system, Python version, tool version, the command you ran, what you expected, and the error text. Include an assistant name and server status if relevant. Remove tokens and private paths or notes you do not want to share. You do not need to diagnose the cause first.

For project-specific contribution questions, use that project's preferred community channel. For program rules, consult the [official GSoC resources](https://developers.google.com/open-source/gsoc/resources).

[Guide contents](README.md)
