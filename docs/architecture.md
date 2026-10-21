# Architecture

This page is for people changing git-into-gsoc. It explains what each part does, where data comes from, and how to add things. For using the tool, start with the [project README](../README.md) and the guide in this folder.

## Goals

1. Give assistants portable, written guidance (the Agent Skill) that works even without the Python package.
2. Give the terminal and assistants the same live data (the CLI and the MCP server) through one shared layer, so they never disagree.
3. Prefer official sources, say where every number comes from, and never invent organizations, issues, or dates.
4. Keep beginners safe by default: availability checks before claiming an issue, estimates labeled as estimates, and no actions taken on their behalf.

## The pieces

```
Assistant (Cursor, Claude Code, Codex, Gemini CLI)        Terminal
        │ reads                        │ MCP (stdio)        │
        ▼                              ▼                    ▼
skills/git-into-gsoc/SKILL.md     mcp_server.py          cli.py
                                        └──────┬───────────┘
                                               ▼
                                     service.py  GSoCToolkit
                 ┌───────────────┬─────────────┼────────────────┬──────────────┐
                 ▼               ▼             ▼                ▼              ▼
          gsoc/official.py  gsoc/client.py  github/client.py  progress/   guidance.py
          official site     org archive     GitHub API        store.py    timeline.py
                 └───────────────┴──────┬──────┘
                                        ▼
                                 http_client.py  (one pooled, cached, retrying client)
```

Scoring lives in `scoring/` and is pure Python with no network, so it is easy to test and adjust.

### Entry points

| Module | Role |
|---|---|
| `cli.py` | Typer commands. Renders tables and panels with Rich, or JSON with `--output json`. Expected failures (`GigError`) print one line plus a hint instead of a traceback. |
| `mcp_server.py` | Model Context Protocol server over standard input and output. Each tool calls the same facade and returns a JSON string. |
| `service.py` | `GSoCToolkit`, the facade both entry points use. It wires the clients together and returns plain dictionaries. |

### Data sources and clients

| Module | Source | Used for |
|---|---|---|
| `gsoc/official.py` | Public JSON behind summerofcode.withgoogle.com | Program milestones for a year and the accepted organization list. Unofficial endpoints, so every caller has a fallback. |
| `gsoc/client.py` | Community archive at api.gsocorganizations.dev plus the official list | Organization catalog for a year, multi-year history, past accepted projects, name lookup |
| `gsoc/timeline.py` | Official milestones or the embedded snapshot in `data/program_history.json` | Current phase and advice; for unpublished years, dates projected from the last official year with an uncertainty window |
| `gsoc/ideas.py` | An organization's ideas page | Plain text of the page, used to find which repositories an organization mentors in |
| `github/client.py` | GitHub REST API, and GraphQL through `github/graphql.py` when a token is set | Repository health, contribution guide detection, beginner-issue search, issue timelines, profile languages |
| `github/availability.py` | Issue payload plus timeline | Decides whether an issue is `available`, `claimed`, `contested`, `likely_taken`, `assigned`, `stale`, `closed`, or `unknown`, with the evidence behind the decision |
| `github/repos.py` | Pull request samples and ideas-page text | Pure helpers that rank an organization's repositories and grade how newcomer pull requests fare |
| `github/graphql.py` | GitHub GraphQL API (token only) | One query for repository health: recent closed pull requests, the insider set, and each pull request's first human reply |
| `github/ecosystems.py` | commits.ecosyste.ms | Token-free committer statistics: single-commit authors and bus factor |
| `github/search.py` | GitHub search syntax | Builds issue search queries that keep working with GitHub's advanced search |
| `github/orientation.py` | Repository tree, workflows, CODEOWNERS, branch rules | `orient`: code map, test command, environment CI sets up, who merges, rules before a pull request |
| `github/pointers.py` | Issue text, repository tree, past fixes | `pointers`: where to start reading for one issue and how similar issues were fixed |
| `github/evidence.py` | Scoped GitHub searches | `contributions`: what a contributor has done in an organization's repositories |
| `github/pulls.py` | A contributor's open pull requests | The part of `next` that says which pull requests need the person and which are waiting |
| `gsoc/archive.py` | Official archive of completed projects | `mentors`: who mentored which project, per year |
| `gsoc/project_ideas.py` | An organization's ideas page | `ideas`: the page split into structured project ideas with a confidence per idea |
| `gsoc/snapshot.py` | Embedded organization data in `data/` | Organization history that works offline and without downloading the full archive |
| `progress/store.py` | Local `progress.json` in the user's data directory | Phases, shortlist, tracked links, notes, inferred profile. Nothing leaves the machine. |
| `guidance.py` | Static | Official links, anti-spam rules, journey phases, proposal checklist |

### Shared plumbing

| Module | What it does |
|---|---|
| `config.py` | `Settings` from environment variables and `.env` (prefix `GIG_`). Resolves the GitHub token from `GIG_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, then the GitHub CLI. Also the official URLs and the default and latest archived years. |
| `http_client.py` | One `httpx` client with a disk cache. Fresh entries are served without a request; stale ones are revalidated with ETags; on network errors or rate limits, a stale entry up to seven days old is served instead of failing. Retries transient errors, spaces out GitHub search calls, and turns HTTP failures into `GigError`s with hints. |
| `errors.py` | `GigError` and subclasses (`InputError`, `HttpError`, `NotFoundError`, `RateLimitError`). Every error carries an optional hint that the CLI prints. |
| `validation.py` | Parses and validates repository names, issue references, GitHub logins, and search terms so user or model input cannot reach other endpoints or inject search qualifiers. |
| `models.py` | Pydantic models shared by everything: organizations, repositories, issues, assessments, milestones, progress state. |
| `text.py` | Cleans text written by strangers (hidden characters, markup, length) before it is shown or returned |
| `coach.py` | `next`: turns the program phase, saved progress, and live checks into the next few actions |
| `drafts.py` | `draft`: message skeletons grounded in maintainers' own rules |
| `proposal.py` | `proposal FILE`: the draft check for what organizations reject on |
| `install/` | `setup`: where each assistant keeps skills and MCP settings, and the plan that writes or removes them. `distribution.py` defines the plugin and extension manifests, launch commands, and install links, which `scripts/sync_integrations.py` writes ([distribution](distribution.md)) |
| `programs.py` | Finds external programs (`gh`, `claude`, and the other assistants' commands) on absolute PATH entries only, never in the current folder, which may be a cloned repository. On Windows it also stops the system from searching the current folder first. |

## Design choices

| Choice | Why |
|---|---|
| One facade for CLI and MCP | A fix or feature reaches both at once; the docs describe one behavior. |
| Rules-based scoring, not machine learning | Scores are explainable. Every result lists its reasons, and tests can pin them. |
| Disk cache with revalidation | Assistants retry and loop. Caching keeps the GitHub rate limit usable and makes repeated commands fast. |
| Official list first, archive second | The official site is authoritative for a year; the archive adds history and project titles. The `catalog.note` field always says which one you got. |
| Estimates are labeled | Future program dates are projections. The data says `dates_are_official: false` and the CLI shows a window. |
| No write actions | The tool never comments, assigns, opens pull requests, or submits proposals. People do those steps themselves. |
| Hermetic tests | `tests/conftest.py` blocks sockets and isolates the cache, data directory, and tokens. HTTP is mocked with `respx` and fixtures. |

## How to add things

**A command or MCP tool.** Add a method to `GSoCToolkit` in `service.py` that returns a dictionary. Expose it in `mcp_server.py` with a docstring that explains the parameters, because assistants read that text. Add a CLI command in `cli.py` with help text on every option. Write tests with fixtures, then update `docs/cli.md`, `docs/mcp.md`, and the skill references.

**A scoring signal.** Edit the relevant function in `scoring/` (`org_match.py`, `health.py`, `issues.py`) or the helpers in `github/repos.py`. Append a human-readable reason whenever you change a score, and add a unit test for the new case.

**A journey phase.** Add it to `JourneyPhase` in `models.py` and `PHASE_GUIDES` in `guidance.py`, then update the phase table in the skill and the docs.

**A data source.** Put the client in `gsoc/` or `github/`, give it the shared `CachedHttpClient`, choose a cache TTL, and make sure the caller degrades gracefully when the source is unavailable. Record the provenance in the returned data so docs and assistants can say where a fact came from.

## Non-goals

- Guaranteeing GSoC acceptance or predicting selection odds
- Submitting proposals, commenting on issues, or opening pull requests for the user
- Writing large changes the user cannot explain
- Replacing an organization's own mentor and contributor instructions

[Contributing guide](../CONTRIBUTING.md) · [Project README](../README.md)
