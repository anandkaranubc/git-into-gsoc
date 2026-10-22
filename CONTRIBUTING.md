# Contributing to git-into-gsoc

Thank you for helping people make a good start in open source. This guide walks you through your first change, from setup to merged pull request. You do not need previous open-source experience. If anything here is unclear, open an issue and say so; that is a useful contribution too.

## Quick start

You need [Git](https://git-scm.com/downloads), [Python 3.11 or newer](https://www.python.org/downloads/), and a GitHub account. Fork the repository on GitHub (the **Fork** button at the top right), then:

```bash
git clone https://github.com/YOUR_USERNAME/git-into-gsoc.git
cd git-into-gsoc
git remote add upstream https://github.com/anandkaranubc/git-into-gsoc.git
python3 -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
pytest
```

`YOUR_USERNAME` is your GitHub username. When pytest ends with a line such as "1003 passed", you are ready to change something. The sections below explain each step and what happens after you open a pull request.

## What we value

- **Real data over guesses.** Features read official GSoC pages, the community archive, and GitHub. Nothing invents organizations, issues, or deadlines.
- **Help people learn, not farm PRs.** Nothing we ship should encourage mass, low-effort contributions or generic AI-written proposals.
- **Beginner-friendly everywhere.** Clear errors, plain-language help text, and docs that define terms the first time they appear.
- **Small, reviewable changes.** One concern per pull request.

## Ways to contribute

- Tell us how your own preparation went: run `git-into-gsoc feedback`, or fill in the [feedback form](https://github.com/anandkaranubc/git-into-gsoc/issues/new?template=feedback.yml). Knowing where people get stuck is how this project decides what to fix next.
- Watch someone new try the tool for 30 minutes and send us your notes. It needs no code, and it finds problems nothing else does. [How to run the session](docs/watch-someone-try-it.md).
- Report a bug or confusing behavior with a [bug report](https://github.com/anandkaranubc/git-into-gsoc/issues/new?template=bug_report.yml). `git-into-gsoc feedback --bug` fills in your versions.
- Suggest an improvement with a [feature request](https://github.com/anandkaranubc/git-into-gsoc/issues/new?template=feature_request.yml).
- Fix documentation. If an instruction did not work for you, that is a bug in the docs.
- Pick an issue labeled [good first issue](https://github.com/anandkaranubc/git-into-gsoc/labels/good%20first%20issue) or [help wanted](https://github.com/anandkaranubc/git-into-gsoc/labels/help%20wanted). Practise the habit this tool teaches: run `git-into-gsoc issue anandkaranubc/git-into-gsoc#NUMBER` first to see whether someone already claimed it. If nobody has, you do not need to wait to be assigned: comment with what you plan to do, then start.
- Improve the Agent Skill in `skills/git-into-gsoc/` or add an MCP tool.

For larger changes, open an issue first so we can agree on the approach before you spend time on it.

## Set up your environment

You need [Git](https://git-scm.com/downloads) and [Python 3.11 or newer](https://www.python.org/downloads/).

1. Fork the repository on GitHub, then clone your fork:

   ```bash
   git clone https://github.com/YOUR_USERNAME/git-into-gsoc.git
   cd git-into-gsoc
   git remote add upstream https://github.com/anandkaranubc/git-into-gsoc.git
   ```

   `origin` is your fork; `upstream` is the main project, which you start new work from.

2. Create a virtual environment and install the package with its development tools:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   pre-commit install
   ```

   `-e` installs the package in editable mode, so your edits take effect immediately. `pre-commit install` adds a Git hook that formats each commit and lints it (runs automatic style and error checks).

3. Check that everything works:

   ```bash
   git-into-gsoc --version
   pytest
   ```

Run `source .venv/bin/activate` again in every new terminal. If `./install.sh` was used earlier, the same `.venv` is reused.

## Make a change

1. Start from an up-to-date `main` and create a branch named after the change:

   ```bash
   git fetch upstream
   git switch -c fix/short-description upstream/main
   ```

   Common prefixes are `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `ci/`, and `chore/`.

2. Make your change. Keep it focused on one problem.

3. Run the checks. CI (continuous integration, the checks GitHub runs automatically on every pull request) runs the same ones:

   ```bash
   ruff check src tests scripts
   ruff format src tests scripts
   mypy src
   pytest
   ```

   CI also measures test coverage (it must stay at 85% or more) and runs `pip-audit` to look for known security problems in the dependencies. A new feature with tests keeps coverage where it is.

   The full test suite takes about 30 seconds on a recent laptop. While you work, run only the file you changed, such as `pytest tests/unit/test_next.py`, and run everything once before you push.

   `pre-commit run --all-files` runs the first three at once. Tests that need the network must fake it with `respx`, a library that returns prepared HTTP responses; the test setup blocks real connections so results stay reproducible.

4. Commit using [Conventional Commits](https://www.conventionalcommits.org/):

   ```text
   fix(cli): explain how to activate the environment after install
   ```

   Commit from a terminal where `.venv` is active. The commit hook runs ruff and mypy from whatever is on your `PATH`, so outside the environment it may use other versions, or fail with an error that has nothing to do with your change.

   Types we use: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`, `chore`. Add a scope in parentheses when it helps, such as `cli`, `github`, `gsoc`, `skill`, or `docs`. Releases and the changelog are generated from these messages, so `feat` means a new capability for users and `fix` means a bug fix.

   Do not name another project's issue or pull request as `owner/repo#123`, or by its link, in a commit message, PR title, or PR body. GitHub then posts a notice on that issue for every push of the commit, so its maintainers hear from this project each time you rebase, and the squash merge copies the PR body onto `main`. Describe it in words instead ("SymPy issue 30671"). This repository's own `#123` is fine.

5. Push your branch with `git push -u origin fix/short-description` and open the pull request link GitHub prints, against `main`. The pull request template asks what changed, why, and how you tested it. Link the issue with `Fixes #123` when there is one.

## What happens next

- CI runs lint, type checks, and a dependency audit, then the tests on Python 3.11, 3.13, and 3.14 on Linux and on Python 3.12 on macOS and Windows, then the installers on Linux and Windows. All checks must pass before merging.
- A maintainer reviews the change. Reviews are conversations: ask questions, push follow-up commits to the same branch, and resolve each thread when it is addressed.
- Pull requests are squash-merged: all of your commits become one commit on `main`. The PR title becomes the commit message on `main`, so keep it in Conventional Commits form. Your branch is deleted automatically after merging.
- [Release Please](https://github.com/googleapis/release-please) opens a release pull request when `main` has new `feat` or `fix` commits. Merging it tags a release and updates `CHANGELOG.md`. You do not edit version numbers by hand.
- Dependabot opens weekly update PRs for Python packages, GitHub Actions, and pre-commit hooks. It waits a week after a release before proposing it; security fixes come right away.

## Using AI tools

You are welcome to use AI assistants while contributing. You are responsible for every line you submit: understand it, test it, and be able to explain it in review. If an AI tool wrote a substantial part of a change, mention it in the pull request so reviewers know where to look closely. No special commit trailers or badges are needed.

## Code and documentation style

- Python 3.11+, fully typed, `mypy --strict` clean. Ruff handles formatting and linting; the configuration lives in `pyproject.toml`.
- Shared logic goes in `service.py` or a focused module. The CLI (`cli.py`) and the MCP server (`mcp_server.py`) are thin layers over it, so they never drift apart.
- Every CLI option has help text. Error messages say what happened and what to try next.
- Docs and user-facing strings use plain language and short sentences. Define a term the first time it appears, write for someone who has never contributed to open source, and avoid em dashes.
- Commands shown in docs must run as written. Uppercase words such as `OWNER/REPO` are placeholders and the text should say so.

## Project layout

| Path | What lives there |
|---|---|
| `src/git_into_gsoc/cli.py` | Command-line interface, built with Typer |
| `src/git_into_gsoc/mcp_server.py` | MCP server that exposes the same features to assistants |
| `src/git_into_gsoc/service.py` | Shared layer used by both |
| `src/git_into_gsoc/onboarding.py` | First-run guidance: the home screen and `start` |
| `src/git_into_gsoc/github/` | GitHub client, repository ranking, issue availability |
| `src/git_into_gsoc/gsoc/` | Official GSoC data, community archive, timelines, ideas pages |
| `src/git_into_gsoc/scoring/` | Transparent scoring rules for organizations, repositories, and issues |
| `src/git_into_gsoc/progress/` | Local progress file |
| `src/git_into_gsoc/data/` | Embedded snapshots used offline |
| `skills/git-into-gsoc/` | The Agent Skill (the only tracked copy; the installer makes the others) |
| `docs/` | Beginner guide and references for users, see [docs/](docs/) |
| `examples/` | Example terminal session, assistant prompts, MCP config |
| `tests/` | Unit and integration tests with fixtures; no live network |
| `install.sh` | Installer for users |
| `.github/` | CI workflows, issue and PR templates, Dependabot |

[docs/architecture.md](docs/architecture.md) explains how the pieces fit together and how to add a command, an MCP tool, or a scoring signal.

## Adding a command or MCP tool

1. Put the logic in `service.py` (or a focused module it calls) and return plain dictionaries.
2. Expose it in `mcp_server.py`. Add a CLI command in `cli.py` if people would use it directly.
3. Add tests with fixtures and `respx` mocks.
4. Update `docs/cli.md`, `docs/mcp.md`, and the skill references if the behavior is user-facing.

## Editing the Agent Skill

The skill is written for AI assistants that read `skills/git-into-gsoc/SKILL.md`. Keep `SKILL.md` short and move depth into `references/`. The description in the front matter (the `---` block at the top of `SKILL.md`) should say what the skill does and when to use it. Tests in `tests/unit/test_skill_package.py` check the structure. The copies under `.agents/skills/` and `.claude/skills/` are written by `git-into-gsoc setup` (which the installers run) and are not tracked.

The plugin and extension manifests (`.claude-plugin/`, `.codex-plugin/`, `gemini-extension.json`), the MCP registry entry `server.json`, and the install buttons in the README are generated from `src/git_into_gsoc/install/distribution.py`. Change that file, run `python scripts/sync_integrations.py`, and commit the result; a test fails if they differ. `python scripts/check_agents.py --setup` installs the plugin into every AI assistant command you have, in throwaway folders, and checks that each can start the server. [Distribution](docs/distribution.md) explains the whole setup.

## Community and security

Everyone participating agrees to the [Code of Conduct](CODE_OF_CONDUCT.md). To report a security problem, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
