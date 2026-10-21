# Command reference

New here? Follow the [beginner guide](README.md) first. Run these commands in your activated environment. `gsoc` is a shorter alias for `git-into-gsoc`.

```bash
git-into-gsoc --help
git-into-gsoc issues --help
git-into-gsoc --version
git-into-gsoc --install-completion     # tab completion for your shell
```

Options belong after their command, except the top-level `--version`. All data commands accept `--output rich` (the default, tables and panels) or `--output json` (for scripts and assistants). `doctor`, `cache`, `mcp`, and `--version` do not accept `--output`.

Repositories can be written as `owner/name` or as any GitHub URL. Issues can be written as `owner/name#123`, an issue URL, or `owner/name 123`.

## Learn and plan

| Command | Options | Result |
|---|---|---|
| `program` | `--year` (default 2027), `--size small\|medium\|large` | Current phase and advice, timeline with official or estimated dates, anti-spam rules |
| `journey` | none | All eight phases with goals and actions |
| `proposal` | none | Proposal checklist, suggested structure, and warnings |

`program` fetches the year's milestones from the official site. If Google has not published that year, it projects the previous official year forward and marks every date as an estimate with an uncertainty window. Offline, it uses an embedded snapshot. `--size` selects which evaluation deadlines to show, because they differ by project size.

## Discover organizations

```bash
git-into-gsoc orgs --tech python,javascript --topics education -n 5
git-into-gsoc orgs --query "symbolic math"
git-into-gsoc org "SymPy"
git-into-gsoc projects "graph neural networks" --since 2024
```

| Command | Arguments and options |
|---|---|
| `orgs` | `--query` / `-q`, `--tech` / `-t`, `--topics`, `--category` / `-c`, `--year`, `--limit` / `-n` (default 10) |
| `org NAME` | Full or partial organization name (quote names with spaces); `--year` |
| `projects [KEYWORDS]` | `--org`, `--since` (earliest year), `--limit` / `-n` (default 15) |

`--tech` and `--topics` take comma-separated lists and understand aliases (`js`, `golang`, `ml`, `k8s`). They decide whether an organization matches; continuity, slot counts, and trend decide the order. Without filters, all organizations are listed by continuity.

`--year` defaults to the configured target year. When that year's organizations are not announced, the most recent official list is used and the table caption says so. `org` shows ideas page, contributor guide, source, website, GitHub organizations, contact channels, projects per year, and recent accepted project titles. `projects` searches every accepted project in the archive by keyword and organization.

## Explore repositories and issues

```bash
git-into-gsoc repos "SymPy" --language python
git-into-gsoc repo sympy/sympy
git-into-gsoc issues --language python -n 10
git-into-gsoc issues --repo sympy/sympy
git-into-gsoc issue sympy/sympy#12345
```

| Command | Arguments and options | Result |
|---|---|---|
| `repos ORG` | GSoC org name or GitHub login; `--language` / `-l`, `--limit` / `-n` | The org's active repositories ranked by ideas-page mentions, open beginner issues, activity, stars, and language |
| `repo OWNER/REPO` | Repository or URL | Grade A to F with evidence, warnings, and setup hints |
| `issues` | `--language` / `-l`, `--org`, `--repo`, `--label`, `--scope gsoc\|all`, `--limit` / `-n` | Beginner issues with a verified availability status |
| `issue REF [NUMBER]` | `owner/repo#123`, a URL, or `owner/repo` plus a number | Linked PRs, claims with dates, approvals, caveats, and a before-you-comment checklist |

`repos` resolves a GSoC organization to its GitHub organizations and reads its ideas page when possible. `repo` samples recent closed pull requests to compute merge rates excluding bots, and separately for outside contributors; it needs about six API calls.

`issues` searches open issues labelled "good first issue", falling back to "help wanted" when results are thin, or the label given with `--label`. It excludes assigned issues, issues with linked PRs, archived repositories, and anything not updated in a year. With the default `--scope gsoc` and no `--org` or `--repo`, it searches only repositories owned by GSoC organizations that use the given language. The top candidates are verified against their timelines. Statuses: `available`, `claimed`, `contested`, `likely_taken`, `assigned`, `stale`, `closed`, `unknown`; see [choosing an issue](guide/05-choose-an-issue.md). The tool never posts comments or claims.

## Get recommendations

```bash
git-into-gsoc recommend --tech python --interests science
git-into-gsoc recommend --github YOUR_USERNAME
```

With `--github`, this reads your recent public repositories to infer your main language and saves the profile locally. It then ranks organizations and lists starter issues from GSoC organizations that use that language.

## Save local progress

```bash
git-into-gsoc progress summary
git-into-gsoc progress note --value "Next: read the contribution guide."
```

| Action after `progress` | Required value | Effect |
|---|---|---|
| `summary` (default) | none | Phases, shortlist, tracked links, and profile |
| `complete_phase` | `--phase NAME` | Mark a phase complete |
| `shortlist_org` | `--value "NAME"` | Save an organization name |
| `track_repo` | `--value OWNER/REPO` | Save a repository name |
| `track_issue` | `--value URL` | Save an issue reference |
| `note` | `--value "TEXT"` | Append a note |

`-v` is short for `--value`. Saving actions print the saved state. Saved links are not validated, and no action changes anything on GitHub. See [tracking progress](guide/08-track-progress.md).

## Setup and maintenance

| Command | Purpose |
|---|---|
| `setup` | Copy the Agent Skill and register the MCP server with your assistants (see below) |
| `doctor` | Version, Python, cache and data paths, GitHub token source, remaining API requests, skill source, which assistants have the skill, and where the MCP server is registered |
| `cache` | Size of the HTTP cache; `cache --clear` deletes it |
| `mcp` | Start the MCP server on stdio; it waits for a client until stopped |

```bash
git-into-gsoc setup                               # detect assistants, user scope
git-into-gsoc setup --dry-run --assistant all     # preview every assistant
git-into-gsoc setup --scope project --assistant claude-code --assistant cursor
```

| `setup` option | Effect |
|---|---|
| `--assistant` / `-a NAME` | `claude-code`, `cursor`, `codex`, `gemini`, `windsurf`, `vscode`, or `all`; repeatable. Default: every assistant with a config folder or executable on this machine |
| `--scope user` (default) | Skill into `~/.<assistant>/skills` and `~/.agents/skills`; MCP into each assistant's user config (Claude Code via `claude mcp add` when available) |
| `--scope project` | The same inside the current repository (`.claude/skills`, `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, ...); `--project-dir` picks another folder |
| `--no-skill`, `--no-mcp` | Do only one of the two jobs |
| `--dry-run` | Print the plan without writing |

Setup merges into existing JSON and TOML files rather than replacing them, writes a `.bak` copy first, refuses to touch a file it cannot parse, and reports `unchanged` on re-runs. Assistants it cannot configure automatically get a printed manual command. The doctor reports connection errors in its output but may still exit with code zero. See [configuration](configuration.md) for tokens and settings.

## Use output in a script

```bash
git-into-gsoc issues --language rust -n 5 --output json > issues.json
git-into-gsoc repo sympy/sympy --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['health']['grade'])"
```

Successful JSON goes to standard output. Expected failures print `error: ...` and usually a `hint: ...` line to standard error and exit with code 1. Invalid command syntax exits with code 2. Errors are not JSON. A successful command can still return data such as `found: false` or availability `unknown`, so inspect the result as well as the exit code.

[Configuration](configuration.md) · [Troubleshooting](troubleshooting.md) · [Guide contents](README.md)
