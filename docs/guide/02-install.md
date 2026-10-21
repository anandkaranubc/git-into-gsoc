# 2. Install the tool

You will download this repository and install its Python package. A **repository** is a project's files and change history. A **terminal** is the application where you type the commands below. Copy the commands without adding a `$` prompt.

## Check prerequisites

You need an internet connection, [Git](https://git-scm.com/downloads), and [Python 3.11 or newer](https://www.python.org/downloads/). Open Terminal on macOS, a terminal on Linux, or your WSL Linux terminal on Windows:

```bash
git --version
python3 --version
```

Both commands should print a version. If either is missing or Python is older than 3.11, install it first, reopen the terminal, and check again. On Windows, you can instead use the PowerShell steps below.

## macOS, Linux, or WSL

Run these once in the folder where you keep projects:

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
./install.sh --no-user-skills
source .venv/bin/activate
git-into-gsoc --version
git-into-gsoc program
```

`git clone` downloads a copy. `cd` moves into it. The installer creates a **virtual environment**, a folder called `.venv` that keeps this tool's Python dependencies separate from other projects. It installs the package, runs `git-into-gsoc doctor`, and copies the assistant skill into `.agents`, `.cursor`, and `.claude` inside the repository. It replaces existing copies of this skill in those locations.

`--version` should print the installed version. `program` should show the current GSoC phase and a timeline; it needs network access the first time to fetch official dates, and falls back to an embedded snapshot when offline.

The activation step is important: an installer cannot activate the environment in your current terminal. Each time you open a new terminal, return to the downloaded folder and run:

```bash
source .venv/bin/activate
```

You can leave the environment with `deactivate`, or run `.venv/bin/git-into-gsoc` directly without activating it.

## Windows PowerShell

The Bash installer does not run directly in PowerShell. Install Git and Python 3.11 or newer, then use the manual route:

```powershell
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\git-into-gsoc.exe --version
.\.venv\Scripts\git-into-gsoc.exe program
```

Check that `py -3 --version` reports at least 3.11 before creating the environment. This route installs the CLI and MCP server without copying assistant skills. Use the full `.exe` path in place of `git-into-gsoc` in later examples. Automated installer checks run on Linux; report Windows-specific problems with your Python and Windows versions.

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

| Option | Effect |
|---|---|
| `--no-user-skills` | Install the package and copy skills only inside this repository |
| No option, or `--user-skills` | Also copy skills into supported locations in your home folder |
| `--skill-only` | Copy skill files without installing Python dependencies |
| `--mcp-only` | Install the package and print assistant setup hints, without copying skills |

Use `--skill-only` and `--mcp-only` separately. Use `PYTHON=python3.12 ./install.sh --no-user-skills` to choose another installed Python before creating `.venv`. For an existing environment with the wrong version, follow [troubleshooting](../troubleshooting.md).

Optional: `git-into-gsoc --install-completion` adds tab completion for your shell.

**Ready to move on:** `git-into-gsoc program` prints a timeline. If not, use [troubleshooting](../troubleshooting.md).

[Next: connect an assistant (optional)](03-connect-your-ai-assistant.md) · [Skip to finding organizations](04-find-organizations.md) · [Guide contents](../README.md)
