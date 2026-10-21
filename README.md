<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/readme/banner-dark.svg">
    <img src="brand/readme/banner-light.svg" alt="git into gsoc. open source has a door. git in." width="100%">
  </picture>
</p>

# git-into-gsoc

Find your first open-source contribution and prepare for [Google Summer of Code (GSoC)](https://summerofcode.withgoogle.com), using real evidence instead of guesses.

GSoC season has a familiar failure mode: beginners pick an abandoned repository, comment "can I work on this?" under an issue that five people already claimed, and submit a generic proposal that organizations reject. git-into-gsoc is built to prevent exactly that. It reads the official program site, the GSoC organization archive, and GitHub, and tells you which organizations fit you, which of their repositories mentors actually work in, whether a newcomer's pull request is likely to land there, and which beginner issues are genuinely free.

You can use it in a terminal or let an AI assistant use it for you. It never fabricates organizations, issues, or deadlines, and it never helps produce spam contributions.

**[Start the beginner guide](docs/README.md)** for setup and a step-by-step path from your first search to a proposal.

## Try it

You need Git and Python 3.11 or newer. These commands work on macOS, Linux, and Linux on Windows through WSL. For Windows PowerShell steps, see [installation](docs/guide/02-install.md).

```bash
curl -fsSL https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.sh | bash
git-into-gsoc program
```

The installer uses [uv](https://docs.astral.sh/uv/) or pipx when you have one, installs the tool, and runs `git-into-gsoc setup`, which copies the Agent Skill and registers the MCP server for every assistant it finds on your machine (Claude Code, Cursor, Codex, Gemini CLI, Windsurf, VS Code). Prefer explicit steps? These do the same thing:

```bash
uv tool install git+https://github.com/anandkaranubc/git-into-gsoc   # or: pipx install git+https://...
git-into-gsoc setup
```

On Windows, run `irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex` in PowerShell. To work from a clone instead, see [installation](docs/guide/02-install.md).

Claude Code users can install the skill and the MCP server together as a plugin: `/plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc`. It needs [uv](https://docs.astral.sh/uv/) and runs the server straight from this repository.

`program` shows the current GSoC phase and timeline with no GitHub token needed. If you use the GitHub CLI and have run `gh auth login`, the tool picks up that token automatically for higher API limits. `git-into-gsoc doctor` shows what is configured.

Then explore:

```bash
git-into-gsoc orgs --tech python --topics science -n 5     # which orgs fit me?
git-into-gsoc org "SymPy"                                  # ideas page, channels, slot history
git-into-gsoc repos "SymPy"                                # which of its repos should I start in?
git-into-gsoc repo sympy/sympy                             # will a newcomer's PR land here?
git-into-gsoc issues --language python -n 5                # beginner issues that are actually free
git-into-gsoc issue owner/repo#123 --track                 # claims, PRs, what to do before commenting; save it
git-into-gsoc proposal draft.md --github YOUR_USERNAME     # what organizations reject on, with evidence
```

## What you get

| Layer | What it does |
|-------|--------------|
| **CLI** (`git-into-gsoc`, alias `gsoc`) | Every feature in the terminal, with `--output json` for scripts |
| **MCP server** (`git-into-gsoc mcp`) | The same features as tools for Claude Code, Cursor, Codex, Gemini CLI, and any MCP client |
| **Agent Skill** (`skills/git-into-gsoc`) | A portable playbook that teaches an assistant how to coach a GSoC contributor without fabricating or spamming |
| **Progress store** | A local record of your phases, shortlist, tracked repos and issues, and notes |

### Evidence, not vibes

- **Organizations** come from the official accepted-org list for the year, merged with the public archive for multi-year history, slot counts, and past project titles. When next year's list is not out yet, the tool says so and shows the latest official list.
- **Timelines** come from the official site when published. Unpublished years are projected from the last official year and clearly labelled as estimates.
- **Repository ranking** reads the org's GSoC ideas page and counts open, unassigned beginner issues per repository.
- **Repository health** measures what matters to newcomers: whether outside contributors' PRs get merged, review speed, open beginner issues, community files, and CI.
- **Issue availability** reads each issue's timeline: linked PRs, assignees, "can I work on this?" claims with dates, maintainer approvals, and contested threads.

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
