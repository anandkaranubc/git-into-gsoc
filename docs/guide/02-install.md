# 2. Install the tool

You will install one command, `git-into-gsoc`. A **terminal** is the application where you type the commands below: Terminal on macOS, your distribution's terminal on Linux, PowerShell on Windows. Copy each command without a leading `$`.

## One command

You need an internet connection and nothing else. On macOS, Linux, or Windows with WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
```

On Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
```

The installer downloads the newest release from [PyPI](https://pypi.org/project/git-into-gsoc/), the Python Package Index. It installs the command with [uv](https://docs.astral.sh/uv/) or pipx if you have one of them, otherwise with Python 3.11 or newer into a private folder in your home directory. If you have none of these, it offers to install uv, a free tool that brings its own Python. Answer yes. It then connects every AI assistant it finds ([chapter 3](03-connect-your-ai-assistant.md) explains what that means), prints what it created or changed, and tells you your next steps. It is safe to run again.

Open a new terminal and check:

```bash
git-into-gsoc --version
git-into-gsoc start
```

`start` shows where the program is right now, asks four quick questions, and suggests organizations that fit you. Press Enter to skip any question. If the terminal says `command not found`, the installer printed the line to add to your PATH, the list of folders your terminal searches for commands; [troubleshooting](../troubleshooting.md#git-into-gsoc-command-not-found) has it too.

To skip the question about uv, pass `--install-uv` through the pipe:

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash -s -- --install-uv
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1))) -InstallUv
```

## Already use uv or pipx?

```bash
uv tool install git-into-gsoc    # or: pipx install git-into-gsoc
git-into-gsoc setup              # connect your AI assistants; add --dry-run to preview
```

pipx installs with the Python it runs on, which must be 3.11 or newer. Ubuntu 22.04's packaged pipx runs on Python 3.10, and `pip3 install pipx` on a Mac can use 3.9; there `pipx install git-into-gsoc` fails with "No matching distribution found" or "requires a different Python". Use uv instead, or the one-line installer, which skips such a pipx and offers to install uv.

To install one particular release, add its version, for example `uv tool install git-into-gsoc==0.14.1`. Every release is on the [PyPI page](https://pypi.org/project/git-into-gsoc/#history) and the [releases page](https://github.com/anandkaranubc/git-into-gsoc/releases), each with a **wheel**, Python's ready-to-install package file, which `uv tool install` or `pipx install` accepts by address when PyPI is slow to update. For the newest code that is not released yet, run `uv tool install git+https://github.com/anandkaranubc/git-into-gsoc`, which needs Git.

## Let GitHub know who you are (recommended)

Checking issues and repositories uses GitHub's API, which allows 60 requests an hour without signing in and 5,000 with. Install [GitHub's `gh` tool](https://cli.github.com/) and sign in once:

```bash
gh auth login
git-into-gsoc doctor
```

git-into-gsoc picks up the login by itself. `doctor` should report the token as found via `gh auth token`, along with your version, your data folders, and the requests you have left. Other ways to supply a token are in [configuration](../configuration.md). Nothing else needs an account.

## Install from a copy of the code

You only need this if you have no uv or pipx and the one-line installer did not work for you. If you want to change the tool, follow [CONTRIBUTING.md](../../CONTRIBUTING.md) instead. You need [Git](https://git-scm.com/downloads) and [Python 3.11 or newer](https://www.python.org/downloads/). Check both with `git --version` and `python3 --version` (`py -3 --version` on Windows, where `python3` can open the Microsoft Store instead).

macOS, Linux, or WSL:

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
./install.sh
source .venv/bin/activate
git-into-gsoc --version
```

Windows PowerShell:

```powershell
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\.venv\Scripts\git-into-gsoc.exe --version
```

`git clone` downloads a copy and `cd` moves into it. The installer creates a **virtual environment**, a folder named `.venv` that keeps this tool's Python packages apart from everything else, installs the package there, and sets up your AI assistants inside this folder only (`./install.sh --user-skills` sets them up for your whole home folder instead). An installer cannot turn the environment on in your terminal, so run `source .venv/bin/activate` (PowerShell: `.\.venv\Scripts\Activate.ps1`) in every new terminal, or call `.venv/bin/git-into-gsoc` directly. Windows blocks downloaded scripts by default, which is why the PowerShell line starts with `-ExecutionPolicy Bypass`; running `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once allows them for good.

`./install.sh --help` lists the options: `--user-skills`, `--no-user-skills`, `--assistant NAME`, `--skill-only`, `--mcp-only`, `--dry-run`, and `--install-uv`. `install.ps1` takes the same options in PowerShell form, such as `-UserSkills` and `-DryRun`. Use `PYTHON=python3.12 ./install.sh` to pick a particular Python. Everything after the package install is `git-into-gsoc setup`, which you can run again on its own at any time.

## Windows and Linux-only projects

Some organizations build software that only runs on Linux, such as GNOME, KDE, and the Linux kernel. git-into-gsoc itself works on Windows, but to build and test those projects you need Linux. [WSL](https://learn.microsoft.com/windows/wsl/install) (Windows Subsystem for Linux) gives you one inside Windows: run `wsl --install` in PowerShell, restart, and use the one-line Linux installer in the Ubuntu terminal it adds. The organization's contributor guide says which systems it supports.

## Update or remove

To update, run the same one-line installer again. It installs the newest release over the old one and refreshes your assistant setup. With uv or pipx, run `uv tool upgrade git-into-gsoc` or `pipx upgrade git-into-gsoc`, then `git-into-gsoc setup`. From a copy of the code, run `git pull` and then `./install.sh` again.

To remove everything:

```bash
git-into-gsoc setup --remove          # undo the assistant setup
uv tool uninstall git-into-gsoc       # or: pipx uninstall git-into-gsoc
```

If the installer used its private folder instead of uv or pipx, delete the `venv` folder inside `~/.local/share/git-into-gsoc` and the `~/.local/bin/git-into-gsoc` link (on Windows, the `venv` folder inside `%LOCALAPPDATA%\git-into-gsoc`). Run `git-into-gsoc doctor` first to see where your progress file lives. Keep it, and a later install picks up where you left off.

Optional: `git-into-gsoc --install-completion` adds tab completion for your shell.

You understood the program in chapter 1 and the tool works, so mark the first phase done:

```bash
git-into-gsoc progress complete_phase --phase learn
```

**Ready to move on:** `git-into-gsoc program` prints a timeline. If not, use [troubleshooting](../troubleshooting.md).

[Next: connect an assistant (optional)](03-connect-your-ai-assistant.md) · [Skip to finding organizations](04-find-organizations.md) · [Guide contents](../README.md)
