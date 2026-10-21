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
| `next` | `--year`, `--no-check` | What to do right now: phase and deadlines, your tracked issues re-checked live with any status changes, new beginner issues in places you follow, and up to six actions with the exact command for each |
| `journey` | none | All eight phases with goals and actions |
| `proposal [FILE]` | `--github`, `--verify/--no-verify`, `--ideas-file` | Without a file: the checklist and suggested structure. With a draft: pass/warn/fail findings on sections, contribution links, timeline detail, specificity, generic phrasing, placeholders, and length |

```bash
git-into-gsoc proposal draft.md --github YOUR_USERNAME --ideas-file ideas.txt
```

The check never rewrites your draft. It verifies linked pull requests on GitHub (and flags ones authored by someone else when `--github` is given), counts week-by-week timeline entries and buffer time, looks for concrete references to files, functions, and issues, lists generic phrases and leftover template placeholders that [Google's spam guidance](https://developers.google.com/open-source/gsoc/resources/spam_proposals) warns about, and, with `--ideas-file`, measures how much of the text is copied from the organization's ideas page. `--no-verify` skips the GitHub lookups.

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
| `org NAME` | Full or partial organization name (quote names with spaces); `--year`; `--shortlist` saves it to your progress |
| `projects [KEYWORDS]` | `--org`, `--since` (earliest year), `--limit` / `-n` (default 15) |

`--tech` and `--topics` take comma-separated lists and understand aliases (`js`, `golang`, `ml`, `k8s`). They decide whether an organization matches; continuity, slot counts, and trend decide the order. Without filters, all organizations are listed by continuity.

`mentors` reads the official GSoC archive of completed projects for the last three archived years, the only public source that names who mentored which project. It lists each mentor with years and project count, how many mentors return, the GitHub repositories past projects touched, and the tags on past projects. Names show past mentors, not next year's; make contact in the organization's public channel.

`ideas` reads the organization's ideas page in its most structured form (raw markdown for GitHub wikis and files, an HTML export for Google Docs) and splits it into project ideas with size in hours, difficulty, mentors, skills, expected outcome, and links. Empty fields were not on the page. A `?` marks a block with no labelled fields, which is often a section heading rather than an idea. Umbrella organizations whose page only links to sub-projects are detected and up to eight linked pages are read; organizations that list ideas as GitHub issues are read through the issue search. The panel also quotes any sentence on the page about using AI tools, because policies differ by organization. Ideas are ranked by the skills you give or the technologies in your saved profile.

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
| `repo OWNER/REPO` | Repository or URL; `--track` saves it to your progress | Grade A to F with evidence, warnings, and setup hints |
| `issues` | `--language` / `-l`, `--org`, `--repo`, `--label`, `--scope gsoc\|all`, `--limit` / `-n` | Beginner issues with a verified availability status |
| `issue REF [NUMBER]` | `owner/repo#123`, a URL, or `owner/repo` plus a number; `--track` saves it to your progress | Linked PRs, claims with dates, approvals, caveats, and a before-you-comment checklist |
| `orient OWNER/REPO` | Repository or URL | Code map with purpose guesses, entry points, the test command CI runs, docs to read first, who merges and CODEOWNERS, rules before a PR (sign-off, CLA, commit style, checklist, AI disclosure), policy sentences, channels, an example merged outsider PR, and a reading plan |
| `pointers REF [NUMBER]` | Issue reference as for `issue`; `--similar N` (default 5), `--no-search` | Files the issue text names, resolved against the tree with a confidence label; code-search hits or search links for identifiers; closed issues with the same beginner label and the PRs that fixed them; the repository's fix norm |

`repos` resolves a GSoC organization to its GitHub organizations and reads its ideas page when possible. `repo` samples recent closed pull requests to compute merge rates excluding bots, and separately for outside contributors; it needs about six API calls.

`orient` makes about sixteen cached GitHub calls and prints facts and paths only: every line names a real file, commit, or check, and the purpose labels on the code map are marked as guesses. `pointers` never proposes a fix. It extracts links to files in the repository, stack-trace frames, paths, and identifiers from the issue, matches them against the repository tree, and learns from history: for closed issues with the same beginner label it finds the pull request merged within seconds of the close (or, with lower confidence, the most recent earlier merge) and lists the files it touched, then summarises how many files a typical fix changes and how often fixes touch tests and docs. GitHub code search needs a token and is limited to two calls per run; without a token you get ready-made search links instead.

`issues` searches open issues labelled "good first issue", falling back to "help wanted" when results are thin, or the label given with `--label`. It excludes assigned issues, issues with linked PRs, archived repositories, and anything not updated in a year. With the default `--scope gsoc` and no `--org` or `--repo`, it searches only repositories owned by GSoC organizations that use the given language. The top candidates are verified against their timelines. Statuses: `available`, `claimed`, `contested`, `likely_taken`, `assigned`, `stale`, `closed`, `unknown`; see [choosing an issue](guide/05-choose-an-issue.md). The tool never posts comments or claims.

## Get recommendations

```bash
git-into-gsoc profile --github YOUR_USERNAME --tech python,c++ --interests science --hours 10 --tz Asia/Kolkata
git-into-gsoc recommend
git-into-gsoc recommend --tech python --interests science
```

`profile` saves the facts recommendations are built from: your GitHub username, the languages and tools you know, the topics you care about, the hours per week you can give, and your timezone. Run it with no options to see what is saved. Short forms are `-g`, `-t`, and `-i`.

`recommend` uses the saved profile when you give no flags, and saves the flags you give so the next run matches. With a GitHub username it reads your recent public repositories to infer your main language. It prints the organizations that fit with their fit reasons and a table of starter issues with verified availability, and says which source the match came from.

## Write and keep evidence

```bash
git-into-gsoc contributions --github YOUR_USERNAME --org "SymPy"
git-into-gsoc draft claim --issue sympy/sympy#12345
git-into-gsoc log --goal "Reproduce #12345" --done "Reproduced on main" --stuck "Flaky test" --next "Ask in Zulip"
```

| Command | Arguments and options | Result |
|---|---|---|
| `contributions` | `--github` / `-g` (required); `--org` (GSoC org name or GitHub org) or `--repo OWNER/REPO` | Your merged, open, and closed PRs, issues opened, threads joined, and reviews given in that scope; paste-ready markdown lines for a proposal; a standing from `none` to `strong`; honest gaps to close |
| `draft KIND` | `intro`, `question`, `claim`, `pr`, `review-reply`, `status`, or `final`; `--org`, `--repo`, `--issue` | A skeleton with placeholders, the fields that must hold your own observations, and the rules maintainers and the official guide state, each with its source |
| `log` | `--goal`, `--done`, `--links` (comma-separated), `--learned`, `--stuck`, `--next`; `--limit` / `-n` when listing | Saves a weekly note, or lists recent notes when you give no fields |

`contributions` runs four scoped GitHub searches (pull requests you authored, issues you opened, threads you commented in, pull requests you reviewed). `draft` fills in real context when you give it: the organization's channels, the project's claim convention read from its CONTRIBUTING (a `/assign` command, a `.take` command, or "we do not assign issues"), whether commits need a sign-off or the PR template asks for an AI disclosure, the issue's availability, and your latest note for a status post. It never fills placeholders with observations you have not made. `log` follows the three questions GSoC organizations ask for in weekly updates; `next` reminds you when the last note is a week old.

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
