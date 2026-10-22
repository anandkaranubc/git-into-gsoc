# Notes for AI coding assistants

This file is for assistants such as Codex, Cursor, Claude Code, and Gemini CLI that open this repository. If you are a person, start with [CONTRIBUTING.md](CONTRIBUTING.md).

## When someone asks about Google Summer of Code

Load and follow the skill in `skills/git-into-gsoc/SKILL.md`. It explains how to guide a contributor through the program, which official sources to cite, and what not to do. Prefer live data from the tool over memory:

```bash
git-into-gsoc program --year 2027
git-into-gsoc orgs --tech python --topics science
git-into-gsoc repo owner/repo
git-into-gsoc issues --language python
git-into-gsoc mcp
```

Never invent organizations, issues, mentors, or deadlines. Never encourage bulk, low-effort contributions or generic AI-written proposals. Point people to the [official GSoC site](https://summerofcode.withgoogle.com) for rules and dates.

## When working on this codebase

[CONTRIBUTING.md](CONTRIBUTING.md) is the rulebook; follow it. The points assistants most often miss:

- Set up with `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.
- Before you finish, run `ruff check src tests scripts`, `ruff format src tests scripts`, `mypy src`, and `pytest`. All four must pass, and test coverage must stay at 85% or more.
- Tests block real network access. Mock HTTP with `respx` and keep sample responses in `tests/fixtures/`.
- Shared logic goes in `src/git_into_gsoc/service.py` or a focused module. `cli.py` and `mcp_server.py` stay thin layers over it.
- Every CLI option needs help text. Errors say what happened and what to try next.
- Comments say why, not what, and name the real case that made a rule necessary. A public function gets a docstring when its name does not say what it returns or raises. The MCP tool docstrings and the skill are text for models; change them only with before-and-after runs.
- Docs and messages use plain language and short sentences, define a term where it first appears, and never use em dashes. Each fact has one home (CONTRIBUTING, "Writing docs"); link to it instead of repeating it. When behavior changes, update `docs/cli.md` or `docs/mcp.md` in the same change, or a test fails.
- Edit the skill in `skills/git-into-gsoc/` only. The copies under `.agents/skills/` and `.claude/skills/`, and the project config files next to them, are written by `git-into-gsoc setup` and ignored by Git.
- Plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.github/plugin/`, `gemini-extension.json`), the registry entry `server.json`, and the install buttons in `README.md` and `docs/assistants.md` are generated from `src/git_into_gsoc/install/distribution.py`. Edit that file, then run `python scripts/sync_integrations.py`.
- Use Conventional Commits (`feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`, `chore`) and keep each change focused. Pull requests are squash-merged with the PR title as the commit message.
- Never write another project's issue or pull request as `owner/repo#123`, or paste its link, in a commit message, PR title, or PR body. GitHub notifies that project on every push of the commit. Describe it in words ("SymPy issue 30671"). This repository's own `#123` is fine.
- Never commit tokens or personal data. `.env` is ignored for that reason.
