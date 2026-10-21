# 2. Install the tool

You will install one command, `git-into-gsoc`, and connect it to any AI assistant you use. A **terminal** is the application where you type the commands below. Copy the commands without adding a `$` prompt.

## The quick way: one command

You need an internet connection. Open Terminal on macOS, a terminal on Linux, or your WSL Linux terminal on Windows, and run:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
```

No `curl`? `wget -qO- https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash` does the same.

On Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
```

The script downloads the newest release from GitHub and installs the `git-into-gsoc` command with [uv](https://docs.astral.sh/uv/) or pipx if you have one of them, otherwise with [Python 3.11 or newer](https://www.python.org/downloads/) into a private folder under your home directory. If you have none of the three, it asks whether to install uv, a free tool that installs Python programs together with the Python they need, all inside your home folder. Answer yes. To skip the question, pass the option through the pipe like this:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash -s -- --install-uv
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1))) -InstallUv
```

On Ubuntu, Debian, and WSL, Python often comes without its `venv` part. The installer notices and offers uv instead, or you can run `sudo apt install python3-venv` first. Then it runs `git-into-gsoc setup`. Setup copies the **Agent Skill**, a folder of instructions for AI assistants, into the folders your assistants read. It also registers the tool's **MCP server**, a small program your assistant starts so it can run these same commands, with each assistant it finds: Claude Code, Codex, Cursor, VS Code and Copilot CLI, Gemini CLI, Antigravity, and Windsurf. It prints a table of exactly what it created or left unchanged, keeps a `.bak` copy of any file it edited, and can be re-run safely. If you have no assistant, that is fine; the command-line tool works on its own.

At the end, the installer prints your next steps. If the folder with the new command is not on your **PATH** (the list of folders your terminal searches for commands), it prints the exact line to add, and the full path you can use right away. Then open a new terminal and check:

```bash
git-into-gsoc --version
git-into-gsoc start
```

`start` shows where the program is right now, asks four quick questions, and suggests organizations that fit you. Press Enter to skip any question. It needs network access the first time to fetch official dates and falls back to an embedded snapshot when offline. Run `git-into-gsoc` with no command any time to see your progress and what to do next.

If you would rather see each step, this is what the script does:

```bash
uv tool install git+https://github.com/anandkaranubc/git-into-gsoc    # needs Git; or: pipx install git+https://github.com/anandkaranubc/git-into-gsoc
git-into-gsoc setup                                                     # add --dry-run to preview
```

To install one particular release instead of the latest code, use the wheel attached to that release on the [releases page](https://github.com/anandkaranubc/git-into-gsoc/releases). A **wheel** is Python's ready-to-install package file, and its name carries the version. Replace both `X.Y.Z` with the release you want, for example `0.9.0`:

```bash
uv tool install https://github.com/anandkaranubc/git-into-gsoc/releases/download/vX.Y.Z/git_into_gsoc-X.Y.Z-py3-none-any.whl
```

`pipx install` accepts the same address. Once the package is on PyPI, `uv tool install git-into-gsoc` is the shorter way.

## From a clone (contributors, or no uv/pipx)

You need [Git](https://git-scm.com/downloads) and [Python 3.11 or newer](https://www.python.org/downloads/). Check both tools:

```bash
git --version
python3 --version
```

If either is missing or Python is older than 3.11, install it first, reopen the terminal, and check again. Then run these once in the folder where you keep projects:

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
./install.sh
source .venv/bin/activate
git-into-gsoc --version
git-into-gsoc program
```

`git clone` downloads a copy. `cd` moves into it. From a clone, the installer creates a **virtual environment**, a folder called `.venv` that keeps this tool's Python dependencies separate from other projects, installs the package there, and runs `git-into-gsoc setup --scope project`, which puts the skill and MCP registration inside the repository folder only. Run `./install.sh --user-skills` instead to set up your home folder, so every project can use it.

The activation step is important: an installer cannot activate the environment in your current terminal. Each time you open a new terminal, return to the downloaded folder and run:

```bash
source .venv/bin/activate
```

You can leave the environment with `deactivate`, or run `.venv/bin/git-into-gsoc` directly without activating it.

## Windows PowerShell from a clone

Windows blocks downloaded scripts by default ("running scripts is disabled on this system"), so start the installer through PowerShell with a one-time exception:

```powershell
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\.venv\Scripts\git-into-gsoc.exe --version
.\.venv\Scripts\git-into-gsoc.exe program
```

`install.ps1` accepts `-NoUserSkills`, `-UserSkills`, `-Assistant name`, `-SkillOnly`, `-McpOnly`, `-DryRun`, and `-InstallUv`, matching the Bash options below. Use the full `.exe` path in place of `git-into-gsoc`, or run `.\.venv\Scripts\Activate.ps1` first. The installer is checked on Windows in CI; report problems with your Python and Windows versions.

## Manual install on macOS or Linux

If you want only the Python package, run this from the downloaded repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The `-e` option keeps the installation connected to this folder, so keep the folder in place. Contributors can install development tools with `python -m pip install -e ".[dev]"`.

## Check GitHub access

```bash
git-into-gsoc doctor
```

Expect a version, cache and data locations, token status, and your GitHub request allowance. Without a token GitHub allows 60 requests per hour, which is enough to try the tool but runs out quickly when checking issues. The easiest fix is the [GitHub CLI](https://cli.github.com/): after `gh auth login`, git-into-gsoc uses that login automatically and the doctor reports the token as found via `gh auth token`. Other ways to supply a token are in [configuration](../configuration.md). The doctor can print a connection failure and still exit successfully, so read its output.

## Installer options

| `install.sh` option | Effect |
|---|---|
| no option | From a clone: project scope (skill and MCP inside the repository). Via curl: user scope |
| `--user-skills` | User scope: set up your home folder so every project can use the skill and server |
| `--no-user-skills` | Project scope explicitly |
| `--assistant NAME` | Configure only this assistant (repeatable); default is every assistant detected |
| `--skill-only` | Copy the skill only; skip the package install and MCP registration |
| `--mcp-only` | Install the package and register MCP; skip the skill copy |
| `--dry-run` | Show what setup would change without writing |
| `--install-uv` | If there is no uv, pipx, or Python 3.11 or newer, install uv without asking first |

Everything after the package install is `git-into-gsoc setup`, so you can re-run that command alone at any time; see the [command reference](../cli.md#setup-and-maintenance). Use `PYTHON=python3.12 ./install.sh` to choose another installed Python before creating `.venv`. For an existing environment with the wrong version, follow [troubleshooting](../troubleshooting.md).

Optional: `git-into-gsoc --install-completion` adds tab completion for your shell.

## Update or remove the tool

To update, run the same one-line install command again. It installs the newest release over the old one and refreshes the skill and MCP registration, and `git-into-gsoc --version` shows the new number. From a clone, run `git pull` and then `./install.sh` again.

To remove everything, first undo the assistant setup, then remove the package with the tool that installed it:

```bash
git-into-gsoc setup --remove          # deletes the skill copies and MCP entries that setup made
uv tool uninstall git-into-gsoc       # or: pipx uninstall git-into-gsoc
```

If the installer used its private folder instead of uv or pipx, delete the `venv` folder inside `~/.local/share/git-into-gsoc` and the `~/.local/bin/git-into-gsoc` link (on Windows, the `venv` folder inside `%LOCALAPPDATA%\git-into-gsoc`). Delete only `venv`: on Linux and Windows your saved progress lives next to it. Run `git-into-gsoc doctor` before removing anything to see the data folder; keep it and a later install picks up where you left off, or delete it too for a clean start.

Now that the tool works, mark the first step of the journey done:

```bash
git-into-gsoc progress complete_phase --phase learn
```

**Ready to move on:** `git-into-gsoc program` prints a timeline. If not, use [troubleshooting](../troubleshooting.md).

[Next: connect an assistant (optional)](03-connect-your-ai-assistant.md) · [Skip to finding organizations](04-find-organizations.md) · [Guide contents](../README.md)
