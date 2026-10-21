# 2. Install the tool

You will download this repository and install its Python package. A **repository** is a project's files and change history. A **terminal** is the application where you type the commands below. Copy the commands without adding a `$` prompt.

## The quick way: one command

You need an internet connection and [Python 3.11 or newer](https://www.python.org/downloads/). Open Terminal on macOS, a terminal on Linux, or your WSL Linux terminal on Windows, and run:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
```

On Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
```

The script installs the `git-into-gsoc` command with [uv](https://docs.astral.sh/uv/) or pipx if you have one of them (otherwise into a private folder under your home directory), then runs `git-into-gsoc setup`. Setup copies the **Agent Skill**, a folder of instructions for AI assistants, into the folders used by Claude Code, Cursor, Codex, Gemini CLI, Windsurf, and VS Code, and registers the tool's **MCP server** with each assistant it finds. It prints a table of exactly what it created or left unchanged, keeps a `.bak` copy of any file it edited, and can be re-run safely. If you have no assistant, that is fine; the command-line tool works on its own.

Then open a new terminal and check:

```bash
git-into-gsoc --version
git-into-gsoc program
```

`program` should show the current GSoC phase and a timeline. It needs network access the first time to fetch official dates and falls back to an embedded snapshot when offline.

If you would rather see each step, this is what the script does:

```bash
uv tool install git+https://github.com/anandkaranubc/git-into-gsoc    # or: pipx install git+https://github.com/anandkaranubc/git-into-gsoc
git-into-gsoc setup                                                     # add --dry-run to preview
```

To install one particular release instead of the latest code, use the wheel attached to that release on the [releases page](https://github.com/anandkaranubc/git-into-gsoc/releases). A **wheel** is Python's ready-to-install package file, and its name carries the version:

```bash
uv tool install https://github.com/anandkaranubc/git-into-gsoc/releases/download/v0.2.1/git_into_gsoc-0.2.1-py3-none-any.whl
```

`pipx install` accepts the same address. Swap both version numbers for the release you want. Once the package is on PyPI, `uv tool install git-into-gsoc` is the shorter way.

## From a clone (contributors, or no uv/pipx)

You also need [Git](https://git-scm.com/downloads). Check both tools:

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

`git clone` downloads a copy. `cd` moves into it. From a clone, the installer creates a **virtual environment**, a folder called `.venv` that keeps this tool's Python dependencies separate from other projects, installs the package there, and runs `git-into-gsoc setup --scope project`, which puts the skill and MCP registration inside the repository folder only. Add `--user-skills` to set up your home folder instead, so every project can use it.

The activation step is important: an installer cannot activate the environment in your current terminal. Each time you open a new terminal, return to the downloaded folder and run:

```bash
source .venv/bin/activate
```

You can leave the environment with `deactivate`, or run `.venv/bin/git-into-gsoc` directly without activating it.

## Windows PowerShell from a clone

```powershell
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
.\install.ps1
.\.venv\Scripts\git-into-gsoc.exe --version
.\.venv\Scripts\git-into-gsoc.exe program
```

`install.ps1` accepts `-NoUserSkills`, `-UserSkills`, `-Assistant name`, `-SkillOnly`, `-McpOnly`, and `-DryRun`, matching the Bash options below. Use the full `.exe` path in place of `git-into-gsoc`, or run `.\.venv\Scripts\Activate.ps1` first. The installer is checked on Windows in CI; report problems with your Python and Windows versions.

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

Everything after the package install is `git-into-gsoc setup`, so you can re-run that command alone at any time; see the [command reference](../cli.md#setup-and-maintenance). Use `PYTHON=python3.12 ./install.sh` to choose another installed Python before creating `.venv`. For an existing environment with the wrong version, follow [troubleshooting](../troubleshooting.md).

Optional: `git-into-gsoc --install-completion` adds tab completion for your shell.

**Ready to move on:** `git-into-gsoc program` prints a timeline. If not, use [troubleshooting](../troubleshooting.md).

[Next: connect an assistant (optional)](03-connect-your-ai-assistant.md) · [Skip to finding organizations](04-find-organizations.md) · [Guide contents](../README.md)
