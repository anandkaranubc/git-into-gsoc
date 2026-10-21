# Command reference

New here? Follow the [beginner guide](README.md) first. Run these commands in your activated environment. `gsoc` is a shorter alias for `git-into-gsoc`.

```bash
git-into-gsoc --help          # commands grouped by journey step
git-into-gsoc issues --help
git-into-gsoc --version
git-into-gsoc --install-completion     # tab completion for your shell
```

Options belong after their command, except the top-level `--version`. All data commands accept `--output rich` (the default, tables and panels) or `--output json` (for scripts and assistants). `doctor`, `cache`, `mcp`, and `--version` do not accept `--output`.

Repositories can be written as `owner/name`, as any GitHub URL, or as the `git@github.com:owner/name.git` form that `git remote -v` prints. Issues can be written as `owner/name#123`, `owner/name 123`, or any issue or pull request URL, including a link copied from a single comment.

## Learn and plan

| Command | Options | Result |
|---|---|---|
| `program` | `--year` (default 2027), `--size small\|medium\|large` | Current phase and advice, timeline with official or estimated dates, good contributor habits, and your next command |
| `next` | `--year`, `--no-check` | What to do right now: phase and deadlines, a time budget when your profile has hours per week (hours until the next milestone, split by what the phase needs), your tracked issues re-checked live with any status changes, your open pull requests in other people's repositories sorted into "needs you" (a merge conflict, a failing check, requested changes with no commit since, a comment with no reply, a draft) and "waiting" (with a nudge to follow up once after five quiet days) when your profile has a GitHub username, new beginner issues in places you follow, posts about the coming GSoC in your shortlisted organizations' repositories (an organization whose maintainers say it will not take part becomes the first action), and up to six actions with the exact command for each |
| `journey` | none | All ten phases with goals and actions |
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
git-into-gsoc ideas "SymPy" --skills python
git-into-gsoc mentors "SymPy"
git-into-gsoc projects "graph neural networks" --since 2024
```

| Command | Arguments and options |
|---|---|
| `orgs` | `--query` / `-q`, `--tech` / `-t`, `--topics`, `--category` / `-c`, `--year`, `--limit` / `-n` (default 10) |
| `org NAME` | Organization name or a whole word of it, such as `mailman` (quote names with spaces). A word that fits several organizations lists them so you can pick one; a misspelled name suggests close matches. `--year`; `--shortlist` saves it to your progress. Also lists issues in the organization's repositories whose title names GSoC and the coming year, such as a preparation tracker or a notice that it will not take part, and says when a maintainer wrote that it will not take part or has not decided |
| `ideas ORG` | `--skills` / `-s` (default: your profile), `--size small\|medium\|large`, `--difficulty easy\|medium\|hard`, `--limit` / `-n` (default 20), `--no-follow` |
| `mentors ORG` | `--years` (default 3), `--limit` / `-n` (default 25) |
| `projects [KEYWORDS]` | `--org`, `--since` (earliest year), `--limit` / `-n` (default 15) |

`--tech` and `--topics` take comma-separated lists and understand aliases (`js`, `golang`, `ml`, `k8s`). They decide whether an organization matches; continuity, slot counts, and trend decide the order. Without filters, all organizations are listed by continuity.

`mentors` reads the official GSoC archive of completed projects for the last three archived years, the only public source that names who mentored which project. It lists each mentor with years and project count, how many mentors return, the GitHub repositories past projects touched, and the tags on past projects. Names show past mentors, not next year's; make contact in the organization's public channel.

`ideas` reads the organization's ideas page in its most structured form (raw markdown for GitHub wikis and files, an HTML export for Google Docs) and splits it into project ideas with size in hours, difficulty, mentors, skills, expected outcome, and links. Empty fields were not on the page. A `?` marks a block with no labelled fields, which is often a section heading rather than an idea. Umbrella organizations whose page only links to sub-projects are detected and up to eight linked pages are read; organizations that list ideas as GitHub issues are read through the issue search. The panel also quotes any sentence on the page about using AI tools, because policies differ by organization. Ideas are ranked by the skills you give or the technologies in your saved profile. Below the table, `ideas` links folders in community archives of accepted proposals that match the organization, so you can calibrate scope and structure. Read them; never copy, and remember they contain personal details.

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
| `orient OWNER/REPO` | Repository or URL; `--codetour FILE` also writes a CodeTour file (a VS Code extension that walks you through files step by step) pinned to the inspected commit | Code map with purpose guesses, entry points, the test command CI runs, docs to read first, who merges and CODEOWNERS, rules before a PR (sign-off, CLA, commit style, checklist, AI disclosure), policy sentences, channels, an example merged outsider PR, and a reading plan |
| `pointers REF [NUMBER]` | Issue reference as for `issue`; `--similar N` (default 5), `--no-search` | Files the issue text names, resolved against the tree with a confidence label; code-search hits or search links for identifiers; closed issues with the same beginner label and the PRs that fixed them; the repository's fix norm |

`repos` resolves a GSoC organization to its GitHub organizations and reads its ideas page when possible. When that page is an umbrella index that only links to member projects (NumFOCUS, for example), it follows up to eight GitHub links and ranks those projects' repositories too, each marked with the page it came from; the JSON output lists them under `linked_projects`. Some umbrellas, such as the Python Software Foundation, list no GitHub organization at all; their repositories come only from the GitHub projects the ideas page links to. An organization whose page links to no GitHub project, because its code lives on GitLab or its own servers, gets an error with a link to the ideas page. `repo` samples recent closed pull requests to compute merge rates excluding bots, and separately for outside contributors; it needs about six API calls, plus one commit listing when some outside pull requests were closed without merging, to find those a maintainer committed another way.

`orient` makes about twenty cached GitHub calls and prints facts and paths only: every line names a real file, commit, or check, and the purpose labels on the code map are marked as guesses. Next to the test command it shows the environment CI really sets up, read from the same workflow: runtime versions including matrix values, service containers such as a database, and the systems the jobs run on. Use those versions locally; a README's setup section can be years older than the workflow. That section also says when the repository expects a changelog, news or release-notes entry, from a news-fragment folder such as `changelog/` or `upcoming_changes/` or from the contributing guide and pull request template. Its "Before you open a PR" section also lists the gates GitHub enforces that CONTRIBUTING often leaves out, read from the default branch's active rules (required approvals and code-owner review, required checks, staying up to date, signed commits, linear history, a merge queue) and from workflows that close pull requests without a linked or assigned issue or that check the title. `draft pr` repeats the branch-rule gates. Classic branch protection is visible only to admins, so an empty list means no rulesets were found, not that there are no rules. `pointers` never proposes a fix. It extracts links to files in the repository, stack-trace frames, paths, and identifiers from the issue, matches them against the repository tree, and learns from history: for closed issues with the same beginner label it finds the pull request merged within seconds of the close (or, with lower confidence, the most recent earlier merge) and lists the files it touched, then summarises how many files a typical fix changes and how often fixes touch tests and docs. GitHub code search needs a token and is limited to two calls per run; without a token you get ready-made search links instead.

`issues` searches open issues labelled "good first issue" or "help wanted", or the label given with `--label`. With `--repo` and no `--label`, it also uses that repository's own beginner label (for example "Difficulty: Easy" or "🌱 Good first issue") and says so; the labels used are in the JSON output as `labels_used`. It excludes assigned issues, issues with linked PRs, archived repositories, and anything not updated in a year. An issue filed by a maintainer (owner, member, or collaborator) is marked "filed by a maintainer" and scores a little higher, because such issues reflect real priorities and get merged more often. A label such as `in progress`, `claimed`, `taken`, `wip`, or `has-pr` counts as a claim even without an assignee. With the default `--scope gsoc` and no `--org` or `--repo`, it searches only repositories owned by GSoC organizations that use the given language. With no `--language`, `--org`, or `--repo`, it uses the first language in your saved profile and says so. No single organization fills more than three places in a search across several. Only a beginner label (such as "good first issue" or "easy") lifts an issue to the top; an issue labelled only "help wanted" scores at most 75, because those are often larger than they look. The top candidates are verified against their timelines. Statuses: `available`, `claimed`, `contested`, `likely_taken`, `assigned`, `stale`, `closed`, `unknown`; see [choosing an issue](guide/05-choose-an-issue.md). The tool never posts comments or claims.

## Get recommendations

```bash
git-into-gsoc profile --github YOUR_USERNAME --tech python,c++ --interests science --hours 10 --tz Asia/Kolkata
git-into-gsoc recommend
git-into-gsoc recommend --tech python --interests science
```

`profile` saves the facts recommendations are built from: your GitHub username, the languages and tools you know, the topics you care about, the hours per week you can give, and your timezone. Run it with no options to see what is saved. Short forms are `-g`, `-t`, and `-i`.

`recommend` uses the saved profile when you give no flags, and saves the flags you give so the next run matches. With a GitHub username it reads your recent public repositories to infer your main language. It prints the organizations that fit with their fit reasons, then starter issues from those same organizations (and, when they have fewer than three, from other GSoC organizations that use your first language). Issues someone already claimed or is working on are left out, and the table says how many. It also says which source the match came from.

## Write and keep evidence

```bash
git-into-gsoc contributions --github YOUR_USERNAME --org "SymPy"
git-into-gsoc draft claim --issue sympy/sympy#12345
git-into-gsoc log --goal "Reproduce #12345" --done "Reproduced on main" --stuck "Flaky test" --next "Ask in Zulip"
```

| Command | Arguments and options | Result |
|---|---|---|
| `contributions` | `--github` / `-g` (defaults to the username saved with `profile --github`); `--org` (GSoC org name or GitHub org) or `--repo OWNER/REPO` | Your merged, open, and closed PRs, issues opened, threads joined, and reviews given in that scope; paste-ready markdown lines for a proposal; a standing from `none` to `strong`; honest gaps to close |
| `diagnose FILE` | A file with the failing output, or `-` to read standard input; `--repo OWNER/REPO` | The likely cause of a failed setup or test run, quoting the line it matched: a missing module, the wrong runtime version, a missing compiler or C headers, a service such as a database not running, a missing environment variable, a missing command, permissions, the network, a port in use, a lock-file mismatch, memory, or failing tests. Each comes with what to try. With `--repo`, it adds what the project's CI sets up: runtime versions, services, install and test commands |
| `pr-check OWNER/REPO#N` | A pull request reference or URL | Your pull request checked against the repository's own rules before a reviewer sees it: merge conflict, failing checks, a linked issue (a failure when a workflow closes pull requests without one), description, the template checklist, AI disclosure when the template asks, commit sign-off when the project requires it, commit style, tests changed alongside code, a changelog entry when one is expected, and size; then the branch rules still ahead, such as required approvals |
| `draft KIND` | `intro`, `question`, `claim`, `pr`, `review-reply`, `status`, or `final`; `--org`, `--repo`, `--issue`; `--check FILE` checks a message you wrote instead | A skeleton with placeholders, the fields that must hold your own observations, and the rules maintainers and the official guide state, each with its source. With `--check`, the message you wrote is checked against the same rules: leftover placeholders, phrases that read as machine-written, a greeting with nothing else, a question with no question, a bare "can I work on this", a pull request description with no linked issue or testing note |
| `log` | `--goal`, `--done`, `--links` (comma-separated), `--learned`, `--stuck`, `--next`; `--limit` / `-n` when listing | Saves a weekly note, or lists recent notes when you give no fields |

`contributions` runs four scoped GitHub searches (pull requests you authored, issues you opened, threads you commented in, pull requests you reviewed). `draft` fills in real context when you give it: the organization's channels, the project's claim convention read from its CONTRIBUTING (a `/assign` command, a `.take` command, or "we do not assign issues"), whether commits need a sign-off or the PR template asks for an AI disclosure, the issue's availability, and your latest note for a status post. The `pr` draft ends with the exact commands for a first pull request (clone your fork, add the upstream remote, branch from the real default branch, run the tests, push). It never fills placeholders with observations you have not made. `log` follows the three questions GSoC organizations ask for in weekly updates; `next` reminds you when the last note is a week old.

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
| `track_repo` | `--value OWNER/REPO` | Save a repository as `owner/repo`, once whatever the spelling |
| `track_issue` | `--value URL` | Save an issue or pull request as one GitHub link; `owner/repo#123` works too |
| `note` | `--value "TEXT"` | Append a note |

`-v` is short for `--value`. `summary` shows the phases as a checklist with the next one marked, then your shortlist, tracked repositories and issues, and how recent your weekly notes are. Saving actions print `Saved.` and the same view. With `--output json`, `summary` prints the summary and a saving action prints the whole saved state. A value that is not a repository or an issue is refused rather than saved. A note, and each field of a `log` entry, holds up to 2,000 characters, and `log` links must be web addresses. No action changes anything on GitHub. See [tracking progress](guide/08-track-progress.md).

## Setup and maintenance

| Command | Purpose |
|---|---|
| `setup` | Copy the Agent Skill and register the MCP server with your assistants (see below) |
| `doctor` | Version, Python, cache and data paths, GitHub token source, remaining API requests, whether each data source (official site, organization archive, commit statistics) answers, skill source, which assistants have the skill, and where the MCP server is registered |
| `cache` | Size of the HTTP cache and its limits; `cache --prune` deletes old entries now, `cache --clear` deletes it all |
| `mcp` | Start the MCP server on stdio; it waits for a client until stopped |

```bash
git-into-gsoc setup                               # detect assistants, user scope
git-into-gsoc setup --dry-run --assistant all     # preview every assistant
git-into-gsoc setup --scope project --assistant claude-code --assistant cursor
```

| `setup` option | Effect |
|---|---|
| `--assistant` / `-a NAME` | `claude-code`, `cursor`, `codex`, `gemini`, `antigravity`, `windsurf` (Devin Desktop), `vscode` (VS Code and Copilot CLI), or `all`; repeatable. Default: every assistant with a config folder or executable on this machine |
| `--scope user` (default) | One shared skill copy in `~/.agents/skills`, which Codex, Cursor, Gemini CLI, Devin Desktop, VS Code, and Copilot CLI all read, plus `~/.claude/skills` for Claude Code and `~/.gemini/config/skills` for Antigravity. MCP into each assistant's user config (Claude Code via `claude mcp add` when available). Copies older versions left in `~/.cursor/skills`, `~/.codex/skills`, `~/.gemini/skills`, or `~/.codeium/windsurf/skills` are removed so the skill is listed once. An assistant that already has the git-into-gsoc plugin or extension is left to it |
| `--scope project` | The same inside the current repository (`.agents/skills`, `.claude/skills`, `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.codex/config.toml`, ...); `--project-dir` picks another folder |
| `--no-skill`, `--no-mcp` | Do only one of the two jobs |
| `--dry-run` | Print the plan without writing |
| `--remove` | Undo: delete the skill copies and remove the MCP registrations for the same scope and assistants, keeping every other entry in those files |

Setup merges into existing JSON and TOML files rather than replacing them, writes a `.bak` copy first, refuses to touch a file it cannot parse, and reports `unchanged` on re-runs. Assistants it cannot configure automatically get a printed manual command. The doctor reports connection errors in its output but may still exit with code zero. See [configuration](configuration.md) for tokens and settings.

## Use output in a script

```bash
git-into-gsoc issues --language rust -n 5 --output json > issues.json
git-into-gsoc repo sympy/sympy --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['health']['grade'])"
```

Successful JSON goes to standard output. Expected failures print `error: ...` and usually a `hint: ...` line to standard error and exit with code 1. Invalid command syntax exits with code 2. Errors are not JSON. A successful command can still return data such as `found: false` or availability `unknown`, so inspect the result as well as the exit code.

[Configuration](configuration.md) · [Troubleshooting](troubleshooting.md) · [Guide contents](README.md)
