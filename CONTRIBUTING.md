# Contributing to git-into-gsoc

Thank you for helping people make a good start in open source. This guide takes you from a fresh copy of the code to a merged pull request. You do not need previous open-source experience. If anything here is unclear, open an issue and say so; that is a useful contribution too.

Looking for help using the tool instead? Start with the [beginner guide](docs/README.md).

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

## Set up

You need [Git](https://git-scm.com/downloads), [Python 3.11 or newer](https://www.python.org/downloads/), and a [GitHub account](https://github.com/signup). Fork the repository on GitHub (the **Fork** button at the top right), then run these commands once:

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

What each line does, in case the words are new:

- A **fork** is your own copy of the repository on GitHub, and `git clone` downloads it to your computer. `YOUR_USERNAME` is your GitHub username.
- Git calls your fork `origin` and the main project `upstream`. New work starts from `upstream`, and your branches are pushed to `origin`.
- `python3 -m venv .venv` creates a **virtual environment**, a folder that keeps this project's Python packages apart from everything else on your computer. `source .venv/bin/activate` turns it on for the current terminal. Run that line again in every new terminal; installing in one terminal does not activate another. On Windows, use `py -3 -m venv .venv` if `python3` opens the Microsoft Store.
- `pip install -e ".[dev]"` installs the tool in **editable** mode, so your edits take effect at once, together with the test and lint tools.
- `pre-commit install` adds a Git hook that formats and checks each commit. Commit from a terminal where `.venv` is active, so the hook uses the project's own versions of the tools.
- `pytest` runs the tests. It takes about half a minute and ends with a line that counts the passed tests and reports no failures. Then you are ready to change something.

If `./install.sh` was used earlier, the same `.venv` is reused.

## Make a change

1. Start from an up-to-date `main`, on a branch named after the change:

   ```bash
   git fetch upstream
   git switch -c fix/short-description upstream/main
   ```

   Prefixes we use: `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `ci/`, and `chore/`.

2. Make the change. Keep it to one problem. If behavior changed, update the docs in the page that owns the topic (see [Writing docs](#writing-docs)).

3. Run the checks. CI (continuous integration, the checks GitHub runs on every pull request) runs the same ones:

   ```bash
   ruff check src tests scripts
   ruff format src tests scripts
   mypy src
   pytest
   ```

   While you work, run only the test file you touched, such as `pytest tests/unit/test_next.py`, and run everything once before you push. CI also keeps test coverage at 85% or more and runs `pip-audit`, which looks for known security problems in the dependencies.

4. Commit with a [Conventional Commits](https://www.conventionalcommits.org/) message:

   ```text
   fix(cli): explain how to activate the environment after install
   ```

   Types: `feat` (a new capability for users), `fix` (a bug fix), `docs`, `test`, `refactor`, `perf`, `ci`, and `chore`. Add a scope in parentheses when it helps, such as `cli`, `github`, `gsoc`, `skill`, or `docs`. Releases and the changelog are generated from these messages.

5. Push, then open the pull request against `main`:

   ```bash
   git push -u origin fix/short-description
   ```

   GitHub prints a link that opens the pull request. The template asks what changed, why, and how you tested it. Link the issue with `Fixes #123` when there is one.

## After you open a pull request

- CI runs lint, type checks, and the dependency audit, then the tests on Python 3.11, 3.13, and 3.14 on Linux and on Python 3.12 on macOS and Windows, then both installers. All checks must pass before merging.
- A maintainer reviews the change. Reviews are conversations: ask questions, push follow-up commits to the same branch, and resolve each thread once it is addressed.
- Pull requests are squash-merged: your commits become one commit on `main`, with the PR title as its message, so keep the title in Conventional Commits form. Your branch is deleted after merging.
- [Release Please](https://github.com/googleapis/release-please) opens a release pull request when `main` has new `feat` or `fix` commits. Merging it tags a release and updates `CHANGELOG.md`. Nobody edits version numbers by hand. [Releasing](docs/releasing.md) has the details.
- Dependabot opens weekly update PRs for Python packages, GitHub Actions, and pre-commit hooks.

## Standards

### Code

- Python 3.11 or newer, fully typed, `mypy --strict` clean. Ruff formats and lints; the settings live in `pyproject.toml`.
- Shared logic goes in `service.py` or a focused module. The CLI (`cli.py`) and the MCP server (`mcp_server.py`) are thin layers over it, so they never drift apart.
- Every CLI option has help text. Error messages say what happened and what to try next.
- Tests never touch the network. Mock HTTP with `respx`, a library that returns prepared responses, and keep sample responses in `tests/fixtures/`.
- Everything a person reads, including help text, errors, and tool descriptions, follows the writing rules below.

### Comments

Most of the code explains itself through its names. A comment is for what the code cannot say: why a rule exists, the real case that made it necessary, a limit of a data source, or a trade-off chosen on purpose.

- Say why, not what. `# check the pull requests` repeats the code; this one from `service.py` earns its place: `# Silence would read as "no look-alike pull requests", which is not known.`
- Name the real case. Many comments here cite the organization, issue, or blind test that showed the problem, with a date. Keep that habit: it tells the next reader what would break.
- Every module starts with a docstring that says what it is for. A public function or class gets one when its name does not say it all: what it returns, what it leaves out, and what it raises.
- The docstring of a command in `cli.py` is its `--help` text, so a change there changes what people see in the terminal. Check `git-into-gsoc COMMAND --help` after editing one.
- Do not add comments to tidy an area you are not changing, and do not delete one you do not understand; ask in the pull request.
- Two kinds of text are for models, not people: the MCP tool docstrings in `mcp_server.py` and the skill in `skills/git-into-gsoc/`. Change those only with before-and-after assistant runs.

### Writing docs

The docs should read as if one person wrote them. These rules keep them that way:

- **One home per fact.** Explain each thing once, in the page that owns it, and link to it from everywhere else. The map: `README.md` is the first two minutes. `docs/README.md` is the index. The guide chapters say what to do and why, in order. `docs/cli.md` and `docs/mcp.md` list every command, tool, and option briefly; a test fails when one is missing. `docs/sources.md` says where data comes from and what it cannot tell you. `docs/troubleshooting.md` is organized by symptom and `docs/configuration.md` by setting. `docs/architecture.md`, `docs/releasing.md`, and `docs/distribution.md` are for people changing the tool.
- **Write for someone who has never contributed to open source.** Short sentences. Define a term the first time a page uses it. Say what to do before explaining why.
- **Plain words.** No em dashes; use a comma, a colon, a period, or parentheses. No filler or sales words, the kind that praise the tool instead of saying what it does; `tests/unit/test_docs_style.py` keeps the short list of words we never use.
- **Commands run as written.** Uppercase words such as `OWNER/REPO` are placeholders, and the page says so once. Prefer placeholders to real issue numbers, so nobody acts on an issue they never chose.
- **Describe the tool as it is today.** No dated session notes, audit records, or plans in `docs/`; the changelog and the pull request history keep the record. When behavior changes, change the docs in the same pull request.
- **Challenge every addition.** Before adding a section, ask whether an existing page already owns the topic. Shorter and clearer beats complete.

A test (`tests/unit/test_docs_style.py`) checks what a script can check.

### Commit messages and pull requests

Never write another project's issue or pull request as `owner/repo#123`, or paste its link, in a commit message, PR title, or PR body. GitHub posts a notice on that issue for every push of the commit, so its maintainers hear from this project each time you rebase, and the squash merge copies the PR body onto `main`. Describe it in words instead ("SymPy issue 30671"). This repository's own `#123` is fine.

Never commit tokens or personal data. `.env` is ignored by Git for that reason.

### AI tools

You are welcome to use AI assistants while contributing. You are responsible for every line you submit: understand it, test it, and be able to explain it in review. If an AI tool wrote a substantial part of a change, say so in the pull request so reviewers know where to look closely. No special commit trailers or badges are needed. Assistants that open this repository read [AGENTS.md](AGENTS.md), which points them back here.

## Where things live

| Path | What is there |
|---|---|
| `src/git_into_gsoc/` | The Python package: `cli.py`, `mcp_server.py`, and `service.py` on top of modules for GitHub, GSoC data, scoring, matching, progress, and assistant setup |
| `skills/git-into-gsoc/` | The Agent Skill, the only tracked copy; `git-into-gsoc setup` writes the others |
| `docs/` | The beginner guide and the references for people using the tool, plus `architecture.md`, `releasing.md`, and `distribution.md` for people changing it |
| `tests/` | Unit and integration tests with fixtures; no live network |
| `evals/` | Benchmarks for the organization ranking ([evals/README.md](evals/README.md)) |
| `scripts/` | Maintainer scripts: generated files, assistant checks, live journeys, the benchmark, the brand kit |
| `examples/`, `brand/`, `site/` | A sample terminal session and prompts; the logo; the project website |
| `install.sh`, `install.ps1` | The installers people run |
| `.github/` | CI workflows, issue and PR templates, Dependabot |

[docs/architecture.md](docs/architecture.md) explains how the pieces fit together and how to add a command, an MCP tool, a scoring signal, or a skill change. It also lists the generated files (plugin manifests, `server.json`, the install buttons), which are never edited by hand.

## Community and security

Everyone participating agrees to the [Code of Conduct](CODE_OF_CONDUCT.md). To report a security problem, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
