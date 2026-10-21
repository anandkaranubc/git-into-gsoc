# git-into-gsoc

**AI-native toolkit for aspiring [Google Summer of Code](https://summerofcode.withgoogle.com) contributors** — starting with GSoC 2027.

One-shot installable **Agent Skill** + **MCP server** + **CLI** that works with Claude Code, Codex, Cursor, Gemini CLI, and other assistants that load portable skills / MCP.

It guides the full journey: understand the program → discover orgs → evaluate repos → find *available* beginner issues → make high-quality contributions → engage communities → prepare proposals → track progress.

> **Never fabricates opportunities. Never encourages spammy AI-generated contributions.** Evidence from GitHub and GSoC archives, grounded in [official GSoC guidance](https://developers.google.com/open-source/gsoc/resources).

## Why this exists

Generic “good first issue” finders and unconstrained coding agents often push beginners toward:

* abandoned repos and already-claimed issues  
* typo-farm PRs mentors hate  
* AI-written proposals orgs auto-reject  

**git-into-gsoc** is opinionated the other way: mentor-trusted contributors, official sources, availability checks, and a journey skill that refuses spam workflows.

## Features

| Layer | What you get |
|-------|----------------|
| **Agent Skill** | Portable `SKILL.md` playbooks for every journey phase |
| **MCP tools** | Live org search, repo health, issue availability, recommendations, progress |
| **CLI** | Same power in the terminal (`git-into-gsoc` / `gsoc`) |
| **Progress store** | Local phase tracking, shortlists, contribution log |
| **Ethics baked in** | Anti-spam rules + AI policy pointers in skill & `program` output |

## Quick start

```bash
git clone https://github.com/anandkaranubc/git-into-gsoc.git
cd git-into-gsoc
./install.sh
export GITHUB_TOKEN=ghp_...   # recommended for GitHub API rate limits

git-into-gsoc doctor
git-into-gsoc program --year 2027
git-into-gsoc recommend --github YOUR_USER --tech python --interests science
```

Then in Cursor / Claude Code / Codex / Gemini CLI:

> Use the **git-into-gsoc** skill. I want to prepare for GSoC 2027; I know Python and care about scientific computing.

See [skills/git-into-gsoc/references/install.md](skills/git-into-gsoc/references/install.md) for MCP JSON snippets.

## CLI cheatsheet

```bash
git-into-gsoc program --year 2027
git-into-gsoc orgs --tech python --topics science --year 2026
git-into-gsoc org "SymPy"
git-into-gsoc repo sympy/sympy
git-into-gsoc issues --language python --org sympy
git-into-gsoc issue sympy/sympy 123
git-into-gsoc recommend --github alice --tech python
git-into-gsoc proposal
git-into-gsoc progress summary
git-into-gsoc journey
git-into-gsoc mcp          # stdio MCP server
```

JSON output: add `--output json` to most commands.

## MCP tools

| Tool | Purpose |
|------|---------|
| `gsoc_program_info` | Timeline, official links, anti-spam rules |
| `gsoc_journey_guide` | Phase playbooks |
| `gsoc_search_orgs` | Rank mentoring orgs from archive data |
| `gsoc_org_details` | Single org profile |
| `gsoc_evaluate_repo` | Health grade + CONTRIBUTING signals |
| `gsoc_find_issues` | Beginner issues + availability |
| `gsoc_issue_status` | Claimability check |
| `gsoc_recommend_path` | Personalized orgs + starter issues |
| `gsoc_proposal_checklist` | Proposal quality bar |
| `gsoc_progress` | Local journey tracking |
| `gsoc_rate_limit` | GitHub API budget |

## Architecture

```
skills/git-into-gsoc/     # portable Agent Skill (progressive disclosure)
src/git_into_gsoc/
  cli.py                  # Typer CLI
  mcp_server.py           # FastMCP stdio server
  service.py              # shared facade
  github/                 # GitHub REST intelligence
  gsoc/                   # org archive + timeline
  scoring/                # org / repo / issue scores
  progress/               # local progress.json
  guidance.py             # official sources + ethics
```

**Data sources**

* Official GSoC site & Google developer docs (cited, not scraped for auth-gated content)
* [GSoC Organizations API](https://api.gsocorganizations.dev/) (community archive of public GSoC pages)
* GitHub REST API (optional `GITHUB_TOKEN`)

**GSoC 2027:** org lists and dates may be unpublished. The toolkit defaults research to the latest archived year (**2026**) and labels 2027 timeline entries as estimates until Google publishes them.

## Differentiation

Compared with generic OSS issue MCP servers or multi-skill OSS packs:

1. **GSoC-native journey** (proposal, bonding, org continuity) — not only “find an issue”
2. **Archive-aware org matching** with technologies/topics/years
3. **Skill + MCP + CLI** one-shot install across assistants
4. **Explicit anti-spam / anti-fabrication** product stance aligned with [official AI](https://developers.google.com/open-source/gsoc/resources/ai_guidance) and [spam](https://developers.google.com/open-source/gsoc/resources/spam_proposals) guidance

## Documentation

* [Contributor guide (this repo)](CONTRIBUTING.md)
* [Architecture](docs/architecture.md)
* [Journey map](docs/journey.md)
* [MCP reference](docs/mcp.md)
* [Examples](examples/)
* Skill references under `skills/git-into-gsoc/references/`

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
ruff check src tests && ruff format --check src tests
mypy src
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for Conventional Commits, squash-merge PRs, and release process.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Google Summer of Code and GSoC are trademarks of Google LLC. This project is **not** affiliated with or endorsed by Google. Always verify dates, orgs, and rules on the [official program site](https://summerofcode.withgoogle.com).
