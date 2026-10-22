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

- Set up with `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.
- Before you finish, run `ruff check src tests scripts`, `ruff format src tests scripts`, `mypy src`, and `pytest`. All four must pass. CI also requires 85% test coverage.
- Tests block real network access. Mock HTTP with `respx` and keep sample responses in `tests/fixtures/`.
- Put shared logic in `src/git_into_gsoc/service.py` or a focused module. `cli.py` and `mcp_server.py` are thin layers over it.
- Every CLI option needs help text. Errors should say what happened and what to try next.
- Write docs and messages in plain language with short sentences. Define a term when it first appears. Do not use em dashes.
- Edit the skill in `skills/git-into-gsoc/` only. The copies under `.agents/skills/` and `.claude/skills/` are written by `git-into-gsoc setup` (which the installers run) and ignored by Git, like the project config files it writes.
- Plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `gemini-extension.json`) and the install buttons in `README.md` and `docs/assistants.md` are generated. Edit `src/git_into_gsoc/install/distribution.py`, then run `python scripts/sync_integrations.py`.
- Use Conventional Commits (`feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`, `chore`) and keep each change focused. Pull requests are squash-merged with the PR title as the commit message.
- Never name another project's issue or pull request as `owner/repo#123`, or by its URL, in a commit message, a PR title, or a PR body. GitHub posts a "referenced this issue" notice on that project's issue for every pushed commit that names it, so each rebase or force-push notifies its maintainers again, and a squash merge copies the PR body into the commit on `main`, where the notice stays. Describe it in words ("SymPy issue 30671"), or put it in backticks in an issue or PR body, where GitHub does not link it. This repository's own `#123` is fine.
- Never commit tokens or personal data. `.env` is ignored for that reason.
