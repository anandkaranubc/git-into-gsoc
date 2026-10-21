<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/readme/banner-dark.svg">
    <img src="brand/readme/banner-light.svg" alt="git into gsoc. open source has a door. git in." width="100%">
  </picture>
</p>

# git-into-gsoc

Find your first open-source contribution and prepare for [Google Summer of Code (GSoC)](https://summerofcode.withgoogle.com), using real evidence instead of guesses.

Many beginners pick an inactive project, ask to work on a task that others already claimed, or send a generic proposal. git-into-gsoc helps you avoid that. It reads the official program site, the GSoC organization archive, and GitHub, and tells you which organizations fit you, which of their repositories (project folders on GitHub) mentors actually work in, whether a newcomer's pull request (a proposed change) is likely to be accepted there, and which beginner issues (reported bugs or tasks) are still free.

You can use it in a terminal or let an AI assistant use it for you. It never fabricates organizations, issues, or deadlines, and it never helps produce spam contributions.

**[Start the beginner guide](docs/README.md)** for setup and a step-by-step path from your first search to a proposal.

## Try it

You need an internet connection. These commands work on macOS, Linux, and Linux on Windows through WSL. For Windows PowerShell steps, see [installation](docs/guide/02-install.md).

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
```

Open a new terminal so it can find the new command, then run:

```bash
git-into-gsoc program
```

The installer downloads the newest release and installs it with [uv](https://docs.astral.sh/uv/), pipx, or Python 3.11 or newer, whichever you have. If you have none of them, it offers to install uv, which brings its own Python. Then it runs `git-into-gsoc setup`, which copies the Agent Skill and registers the MCP server for every assistant it finds on your machine (Claude Code, Codex, Cursor, VS Code and Copilot CLI, Gemini CLI, Antigravity, Windsurf). Prefer explicit steps? These do the same thing:

```bash
uv tool install git+https://github.com/anandkaranubc/git-into-gsoc   # needs Git; or: pipx install git+https://...
git-into-gsoc setup
```

On Windows, run `irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex` in PowerShell. To work from a clone instead, see [installation](docs/guide/02-install.md).

`program` shows the current GSoC phase and timeline with no GitHub token needed. Then tell the tool about yourself once and ask it what to do:

```bash
git-into-gsoc profile --tech python --interests science --hours 10   # saved locally
git-into-gsoc next                                                   # your next few actions, with the commands to run
```

If you use the GitHub CLI and have run `gh auth login`, the tool picks up that token automatically for higher API limits. `git-into-gsoc doctor` shows what is configured.

Then explore:

```bash
git-into-gsoc orgs --tech python --topics science -n 5     # which orgs fit me?
git-into-gsoc org "SymPy"                                  # ideas page, channels, slot history
git-into-gsoc repos "SymPy"                                # which of its repos should I start in?
git-into-gsoc repo sympy/sympy                             # will a newcomer's PR land here?
git-into-gsoc issues --language python -n 5                # beginner issues that are actually free
git-into-gsoc issue owner/repo#123 --track                 # claims, PRs, what to do before commenting; save it
git-into-gsoc contributions --org "SymPy"                  # your PRs, issues, and reviews there, as proposal evidence
git-into-gsoc proposal draft.md --github YOUR_USERNAME     # what organizations reject on, with evidence
```

## Use it inside your AI assistant

Each line installs the Agent Skill and the MCP server together, and updates with the assistant's own update command. You need [uv](https://docs.astral.sh/uv/), a free tool that starts the server.

| Assistant | Command |
|---|---|
| Claude Code | `claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc` |
| Codex | `codex plugin marketplace add anandkaranubc/git-into-gsoc`, then `codex plugin add git-into-gsoc@git-into-gsoc` |
| GitHub Copilot CLI | `copilot plugin marketplace add anandkaranubc/git-into-gsoc`, then `copilot plugin install git-into-gsoc@git-into-gsoc` |
| Gemini CLI | `gemini extensions install https://github.com/anandkaranubc/git-into-gsoc --auto-update` |
| Antigravity | `agy plugin install https://github.com/anandkaranubc/git-into-gsoc` |
| VS Code, Cursor, Windsurf, and others | See [use git-into-gsoc in your AI assistant](docs/assistants.md) |

One-click buttons for the MCP server alone (they also need [Git](https://git-scm.com/downloads)):

<!-- generated:install-links -->
[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=git-into-gsoc&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJnaXQraHR0cHM6Ly9naXRodWIuY29tL2FuYW5ka2FyYW51YmMvZ2l0LWludG8tZ3NvY0BtYWluIiwiZ2l0LWludG8tZ3NvYyIsIm1jcCJdfQ%3D%3D) [![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_server-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=git-into-gsoc&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A%2F%2Fgithub.com%2Fanandkaranubc%2Fgit-into-gsoc%40main%22%2C%22git-into-gsoc%22%2C%22mcp%22%5D%7D) [![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install_server-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=git-into-gsoc&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A%2F%2Fgithub.com%2Fanandkaranubc%2Fgit-into-gsoc%40main%22%2C%22git-into-gsoc%22%2C%22mcp%22%5D%7D&quality=insiders) [![Add to Kiro](https://img.shields.io/badge/Kiro-Add_server-7138CC?style=flat-square&logo=kiro&logoColor=white)](https://kiro.dev/launch/mcp/add?name=git-into-gsoc&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A%2F%2Fgithub.com%2Fanandkaranubc%2Fgit-into-gsoc%40main%22%2C%22git-into-gsoc%22%2C%22mcp%22%5D%7D)
<!-- /generated:install-links -->

## What you get

| Layer | What it does |
|-------|--------------|
| **CLI** (`git-into-gsoc`, alias `gsoc`) | Every feature in the terminal, with `--output json` for scripts |
| **MCP server** (`git-into-gsoc mcp`) | The same features as tools for Claude Code, Cursor, Codex, Gemini CLI, and any MCP client |
| **Agent Skill** (`skills/git-into-gsoc`) | A portable playbook that teaches an assistant how to coach a GSoC contributor without fabricating or spamming |
| **Journey coach** (`profile`, `next`, `log`) | A saved profile, a daily "what should I do now" that re-checks your tracked issues live, and weekly notes |
| **Progress store** | A local record of your phases, shortlist, tracked repos and issues, and notes |

### Where the results come from

- **Organizations** come from the official accepted-org list for the year, merged with the public archive for multi-year history, slot counts (how many contributor projects Google funded for the organization), and past project titles. When next year's list is not out yet, the tool says so and shows the latest official list.
- **Timelines** come from the official site when published. Unpublished years are projected from the last official year and clearly labelled as estimates.
- **Repository ranking** reads the org's GSoC ideas page and counts open, unassigned beginner issues per repository.
- **Repository health** measures what matters to newcomers: whether outside contributors' PRs get merged, review speed, open beginner issues, community files, and CI.
- **Issue availability** reads each issue's timeline: linked PRs, assignees, "can I work on this?" claims with dates, maintainer approvals, and contested threads.

The tool only reads. It contacts summerofcode.withgoogle.com, api.gsocorganizations.dev, api.github.com, commits.ecosyste.ms, and the ideas page each organization published, and it never posts anywhere. Your profile and progress stay in a file on your computer. Details are in [sources and limitations](docs/sources.md).

## Where to go next

| I want to... | Start here |
|---|---|
| Understand GSoC and open source | [Beginner guide](docs/README.md) |
| Connect my AI assistant | [Assistant setup](docs/guide/03-connect-your-ai-assistant.md) |
| Look up a command | [Command reference](docs/cli.md) |
| See the MCP tools | [MCP reference](docs/mcp.md) |
| Fix a setup or connection problem | [Troubleshooting](docs/troubleshooting.md) |
| Know where results come from | [Sources and limitations](docs/sources.md) |
| Improve this project | [Contributing](CONTRIBUTING.md) and [architecture](docs/architecture.md) |

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
ruff check src tests && ruff format --check src tests
mypy src
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for Conventional Commits, squash-merge PRs, and the release process.

## License and disclaimer

MIT, see [LICENSE](LICENSE).

This independent project is not affiliated with or endorsed by Google. Google Summer of Code and GSoC are trademarks of Google LLC. Always verify dates, organizations, and rules on the [official program site](https://summerofcode.withgoogle.com), and follow each organization's [AI policy](https://developers.google.com/open-source/gsoc/resources/ai_guidance).

<!-- mcp-name: io.github.anandkaranubc/git-into-gsoc -->
