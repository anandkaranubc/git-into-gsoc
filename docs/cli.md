# Command reference

Every command and option, briefly. New here? The [beginner guide](README.md) explains when to use each command and what to do with the result. `gsoc` is a shorter alias for `git-into-gsoc`.

```bash
git-into-gsoc --help                   # commands grouped by journey step
git-into-gsoc issues --help            # one command's options
git-into-gsoc --version
git-into-gsoc --install-completion     # tab completion for your shell
```

How to read the commands:

- Options come after the command, except the top-level `--version`.
- Data commands accept `--output rich` (the default, tables and panels) or `--output json` (for scripts and assistants). `doctor`, `cache`, `mcp`, and `--version` do not take `--output`.
- A repository can be written as `owner/name`, as any GitHub URL, or as the `git@github.com:owner/name.git` form that `git remote -v` prints. An issue can be written as `owner/name#123`, `owner/name 123`, or any issue or pull request URL, including a link copied from a single comment.
- Uppercase words such as `OWNER/REPO` and `YOUR_USERNAME` are placeholders for your own values.
- Nothing here posts to GitHub or submits anything to GSoC. Commands that save do so in a file on your computer, and say so.

## Get started

```bash
git-into-gsoc            # home: where the program is, your progress, and what to run next
git-into-gsoc start      # four questions, then organizations that fit you
```

| Command | Options | Result |
|---|---|---|
| (no command) | none | A short home screen: the current GSoC phase and the next date, then a pointer to `start` the first time, or your progress in six steps (profile, shortlist, repository, issue, weekly note, merged pull request) with the command for what to do now |
| `start` | `--github` / `-g`, `--tech` / `-t`, `--interests` / `-i` (words, or numbers from the start menu), `--hours`, `--no-input` | Asks four questions and saves the answers as your profile, then shows the three organizations that fit best with their reasons, lets you shortlist any by number, and prints your next steps with exact commands. Press Enter to skip a question; with options or `--no-input` it asks nothing. Without a terminal, it prints the options to use, and `--output json` lists the questions for an assistant to ask |

The four questions: your GitHub username (optional; it reads the languages of your public repositories and suggests them), the languages and tools you know, the topics you would enjoy (numbers from a list, or your own words), and hours per week. Run `start` again whenever your answers change.

## Learn and plan

| Command | Options | Result |
|---|---|---|
| `program` | `--year` (default 2027), `--size small\|medium\|large` | The current phase and what to do in it, the timeline with official or estimated dates, good contributor habits, and your next command. `--size` picks which evaluation deadlines to show, since they differ by project size |
| `next` | `--year`, `--no-check` | What to do right now, with up to six actions and the exact command for each. See below |
| `journey` | none | All ten phases with goals and actions |
| `proposal [FILE]` | `--github`, `--verify` / `--no-verify`, `--ideas-file` | Without a file: the proposal checklist and a suggested structure. With a draft (`proposal check FILE` works too): pass, warn, and fail findings. See below |

```bash
git-into-gsoc proposal draft.md --github YOUR_USERNAME --ideas-file ideas.txt
```

Notes:

- `program` reads the year's milestones from the official site. When Google has not published that year, it projects the previous official year forward and marks every date as an estimate with an uncertainty window. Offline, it uses an embedded snapshot.
- `next` combines the program phase and its deadlines, a time budget when your profile has hours per week (hours until the next milestone, split by what the phase needs), your tracked issues re-checked live with any status changes, pull requests of yours merged since your last check (recorded in your progress, with a word for the first one), new beginner issues in the places you follow, and posts about the coming GSoC in your shortlisted organizations' repositories (an organization whose maintainers say it will not take part becomes the first action). When your profile has a GitHub username, it also sorts your open pull requests in other people's repositories into "needs you" (a merge conflict, a failing check, requested changes with no commit since, a comment with no reply, a draft) and "waiting" (with a nudge to follow up once after five quiet days). `--no-check` skips the live re-checks.
- `proposal FILE` never rewrites your draft. It checks for the required sections, counts week-by-week timeline entries and buffer time, looks for concrete references to files, functions, and issues, and lists the generic phrases and leftover placeholders that [Google's spam guidance](https://developers.google.com/open-source/gsoc/resources/spam_proposals) warns about. Linked GitHub pull requests and GitLab merge requests (on gitlab.com or a project's own GitLab) are looked up, so one written by someone else is flagged with `--github`, and one the draft calls merged but that is open or was closed without merging is flagged too. `--ideas-file` measures how much of the text is copied from the organization's ideas page. `--no-verify` skips the lookups.

## Discover organizations

```bash
git-into-gsoc orgs --tech python,javascript --topics education -n 5
git-into-gsoc orgs --query "symbolic math"
git-into-gsoc org "SymPy"
git-into-gsoc ideas "SymPy" --skills python
git-into-gsoc mentors "SymPy"
git-into-gsoc projects "graph neural networks" --since 2024
```

| Command | Arguments and options | Result |
|---|---|---|
| `orgs` | `--query` / `-q`, `--tech` / `-t`, `--topics`, `--category` / `-c`, `--year`, `--limit` / `-n` (default 10) | Organizations ranked by fit (strong, good, or partial), with why each matched, years active, and projects per year. With none of the first four options, it ranks by your saved profile and says so; with no profile either, it lists every organization by continuity |
| `org NAME` | A name or a whole word of it, such as `mailman` (quote names with spaces); `--year`; `--shortlist` saves it to your progress | One organization: ideas page, contributor guide, source, website, GitHub organizations, contact channels, projects per year, recent accepted project titles, and what it has said about the coming GSoC. A word that fits several organizations lists them; a misspelling suggests close matches |
| `ideas ORG` | `--skills` / `-s` (default: your profile), `--size small\|medium\|large`, `--difficulty easy\|medium\|hard`, `--limit` / `-n` (default 20), `--no-follow` | The organization's ideas page read into a table: size in hours, difficulty, mentors, skills, expected outcome, and links, ranked by the skills you give |
| `mentors ORG` | `--years` (default 3), `--limit` / `-n` (default 25) | Who mentored the organization's completed projects in recent archived years, with years and project counts, how many return, the repositories past projects touched, and their tags |
| `projects [KEYWORDS]` | `--org`, `--since` (earliest year), `--limit` / `-n` (default 15) | Accepted projects from past years that match the keywords or organization |

Notes:

- `--tech` and `--topics` take comma-separated lists in your own words. Synonyms (`healthcare` finds `radiology`; `web dev`, `k8s`) and common misspellings (`pyhton`) are understood, and the output says when a word was corrected. Under the table, the top three organizations show their evidence with its source, readiness facts (such as how many ideas state an easy or medium difficulty), caveats, and skills their ideas often ask for that you did not list. When a word matches dozens of organizations ("ai", or "python" alone), a tip suggests narrower words with the count each matches. Fit is not a chance of acceptance; [how recommendations work](recommendations.md) explains the ranking.
- `--year` defaults to the configured target year. When that year's organizations are not announced, the most recent official list is used and the caption says so. A name that took part in earlier years but is not on the current list gets an explanation instead of an empty table.
- `org` also lists issues in the organization's repositories whose title names GSoC and the coming year (a preparation tracker, or a notice that it will not take part) and says when a maintainer wrote that it will not take part or has not decided. When GitHub's search limit stops that check, it says so and still shows what the project wiki says, and it shows, with its date, what the monthly check found the organization said.
- `ideas` reads the page in its most structured form: raw markdown for GitHub wikis and files, the HTML export for Google Docs, the wikitext of a MediaWiki page whose ideas are templates. A table of ideas is read row by row; a table of past years' accepted projects is not. Empty fields were not on the page, and a `?` marks a block with no labelled fields, often a section heading rather than an idea. An umbrella page that only links to sub-projects is followed, up to eight pages (`--no-follow` stops that); ideas kept as GitHub issues are read through the issue search; a link that redirects to a wiki's home page is reported as unreachable. The panel quotes any sentence on the page about using AI tools, because policies differ. Ideas are matched to your skills by meaning (`reactjs` is React; `c` matches C, not every word with the letter c), each lists the skills it would teach you, and ideas that need more hours than the longest coding period allows (22 weeks) at your hours per week are marked "too big" and listed last. Below the table are links to folders in community archives of accepted proposals for the organization; read them for scope, never copy, and remember they contain personal details.
- `mentors` reads the official GSoC archive of completed projects, the only public source that names who mentored which project. Names show past mentors, not next year's; make contact in the organization's public channel.

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
| `repos ORG` | GSoC organization name or GitHub login; `--language` / `-l`, `--limit` / `-n` | The organization's active repositories ranked by ideas-page mentions, open beginner issues, activity, stars, and language, with the project's main repository first |
| `repo OWNER/REPO` | Repository or URL; `--track` saves it to your progress | A grade from A to F with the evidence, warnings, plain notes, where it lost points, setup hints, and the command to run next. A read-only mirror is not graded; it names where the project really lives |
| `issues` | `--language` / `-l`, `--org`, `--repo`, `--label`, `--scope gsoc\|all`, `--limit` / `-n` | Beginner issues with a verified availability status and, where one applies, a caution |
| `issue REF [NUMBER]` | `owner/repo#123`, a URL, or `owner/repo` plus a number; `--track` saves it to your progress | One issue: linked pull requests, claims with dates, maintainer approvals, caveats, the caution a search would give it, and a before-you-comment checklist |
| `orient OWNER/REPO` | Repository or URL; `--codetour FILE` also writes a CodeTour file (a VS Code extension that walks you through files step by step) pinned to the inspected commit | A code map with purpose guesses, entry points, the test command CI runs and the environment it sets up, docs to read first, the most active commit authors and CODEOWNERS, the rules before a pull request with their sources, policy sentences, channels, an example merged outsider pull request, and a reading plan |
| `pointers REF [NUMBER]` | Issue reference as for `issue`; `--similar N` (default 5), `--no-search` | Files the issue names, resolved against the tree with a confidence label; code-search hits or ready-made search links for identifiers; closed issues with the same beginner label and the pull requests that fixed them; how big a typical fix is |

Notes on `repos` and `repo`:

- `repos` resolves a GSoC organization to its GitHub organizations and reads its ideas page when it can. When the page is an umbrella index (NumFOCUS, for example), it follows up to eight GitHub links and ranks those projects' repositories too, each marked with the page it came from (`linked_projects` in JSON). An umbrella with no GitHub organization of its own, such as the Python Software Foundation, gets only the projects its ideas page links to. An organization whose code lives on GitLab or its own servers gets an error with a link to the ideas page.
- `repo` samples recent closed pull requests to compute merge rates without bots, and separately for outside contributors. It needs about six API calls, plus one commit listing when some outside pull requests were closed without merging, to find the ones a maintainer committed another way. [Pick a repository](guide/05-choose-an-issue.md) explains the grade.
- When GitHub does not answer a read, often because of a rate limit, `repo` leaves the signals that come from it out of the grade and says to run it again later; it does not count them as missing. `draft claim` then says the project's rule for claiming was not read, instead of saying the project has no contributing guide.

Notes on `issues` and `issue`:

- Where it searches: with `--repo`, that repository; with `--org`, a GSoC organization's name or a GitHub login (with a name, also the organizations whose repositories its ideas page names, marked "named on the ... ideas page" and listed after the organization's own; with neither, as for GNOME on gitlab.gnome.org, it says where the code lives). With the default `--scope gsoc` and neither option, only repositories owned by GSoC organizations that use the language, the organizations whose work matches your interests first; `--scope all` searches every public repository. With no `--language`, `--org`, or `--repo`, it uses the first language in your saved profile and says so. `--language html` or `css` also searches CSS, Vue, JavaScript, and TypeScript repositories, because GitHub tags few web projects as mostly HTML or CSS.
- Which labels: "good first issue" and "help wanted", or the label given with `--label`. With `--repo`, also that repository's own beginner labels, up to three ("Easy", "Starter", "🌱 Good first issue"); with `--org`, also common names such as "starter", "easy", and "beginner". The labels used are `labels_used` in JSON. A label that only looks like a beginner label does not count: "Good First Issue (Taken)", or Oppia's "Impact: Low -- ONLY DO IF GOOD FIRST ISSUE", which postpones issues.
- What is left out: assigned issues, issues with a linked pull request, archived repositories, and anything not updated in a year. A label such as `in progress`, `claimed`, `taken`, `wip`, or `has-pr` counts as a claim even without an assignee. For an issue imported from Jira, as many Jenkins and Apache issues are, a pull request that names the old Jira key (such as `JENKINS-43785`) counts as linked, at the cost of one extra search. A link to a pull request or commit given as an example does not count.
- How results are ordered: only a beginner label lifts an issue to the top; an issue labelled only "help wanted" scores at most 75, because those are often larger than they look. An issue filed by a maintainer is marked and scores a little higher, since such issues reflect real priorities. Issues open more than two years or labelled `backlog` score lower. No single organization fills more than three places in a search across several. Each issue says what in it fits your profile ("Names CSS, which you know").
- Cautions: an issue that may not suit a first contribution (a tracker or call for testing, one open for years, one with no beginner label, one several people asked for, one whose label says the project wants no AI-generated work) shows a caution saying why and comes after the issues without one.
- Statuses: the top candidates are verified against their timelines and get a status from `available` to `unknown`; [find an issue that is free](guide/05-choose-an-issue.md#find-an-issue-that-is-actually-free) defines each one and says what to do.
- `issue` adds a caveat when a pull request opened since the issue looks like the same work but never links the issue (one extra search), and names first a label saying the project wants no AI-generated work. A GitLab issue link from any GitLab server (gitlab.com, gitlab.gnome.org, invent.kde.org) is checked through GitLab's public API for state, assignees, labels, and merge requests; its comments need a sign-in, so it says to read them yourself.
- An issue that a merged pull request says it fixes ("Fixes issue #12", "This should resolve #12") is `likely_taken` even while it stays open, because GitHub closes an issue only for a few exact phrases merged into the default branch. A merged pull request that only mentions the issue stays a caveat.
- `recommend` marks a starter issue that someone asked to work on before, with no pull request since, as "asked before", as `issues` does.
- When nothing turns up, `issues` says what to try next instead of printing an empty table.

Notes on `orient` and `pointers`:

- `orient` makes about twenty cached GitHub calls and prints facts and paths only: every line names a real file, commit, or check, and the purpose labels on the code map are marked as guesses. Next to the test command it shows the environment CI really sets up, read from the same workflow: runtime versions including matrix values, service containers such as a database, and the systems the jobs run on. Use those versions locally; a README's setup section can be years older than the workflow. It also says when the repository expects a changelog or news entry, from a news-fragment folder such as `changelog/` or from the contributing guide and pull request template.
- "Before you open a PR" lists the gates GitHub enforces that CONTRIBUTING often leaves out, read from the default branch's active rules (required approvals and code-owner review, required checks, staying up to date, signed commits, linear history, a merge queue) and from workflows that close pull requests without a linked or assigned issue or that check the title. `draft pr` repeats them. Classic branch protection is visible only to admins, so an empty list means no rulesets were found, not that there are no rules.
- `pointers` never proposes a fix. It extracts file links, stack-trace frames, paths, and identifiers from the issue and matches them against the repository tree; when the issue names no file, it searches the code for the title's most distinctive words (marked "title words"). Among closed issues with the same beginner label it prefers ones whose titles share words with this issue (the table says "recent" instead of "similar" when none do), finds the pull request merged within seconds of the close (or, with lower confidence, the most recent earlier merge), lists the files it touched, and summarises how many files a typical fix changes and how often fixes touch tests and docs. GitHub code search needs a token and is limited to two calls per run; without a token you get ready-made search links instead.

## Get recommendations

```bash
git-into-gsoc profile --github YOUR_USERNAME --tech python,c++ --interests science --hours 10 --experience new --tz Asia/Kolkata
git-into-gsoc recommend
git-into-gsoc recommend --tech html,css --interests accessibility --experience new --hours 8
```

| Command | Options | Result |
|---|---|---|
| `profile` | `--github` / `-g`, `--tech` / `-t`, `--interests` / `-i`, `--hours`, `--experience` / `-e` (`new`, `some`, or `experienced`), `--tz` | Saves the facts recommendations are built from, or shows what is saved when you give no options |
| `recommend` | `--tech`, `--interests`, `--experience`, `--hours`, `--github` | Organizations that fit, with evidence; ideas that fit you; starter issues; and a short path with a command for each step |

Notes:

- `profile --experience new` means no pull request merged in someone else's project yet. With `--github` and no `--experience`, the level is read from how many of your pull requests were merged in other people's repositories (one GitHub search), and the panel says where it came from. GSoC projects are about 90, 175, or 350 hours over 8 to 22 weeks ([GSoC FAQ](https://developers.google.com/open-source/gsoc/faq)); when your hours per week are too few for a size, `profile` and `next` say which sizes fit.
- `recommend` uses the saved profile when you give no options, saves the skills and interests you give so the next run matches, and takes `--experience` and `--hours` as one-run overrides. With a GitHub username it reads your recent public repositories to infer your main language. It prints whether the organizations are confirmed for the coming year (until Google announces the list, none is); the organizations that fit, with evidence, readiness facts, caveats, and skills to learn for the top three; ideas that fit you from each top organization's latest ideas page, leaving out ideas too big for your hours; starter issues from those organizations (and, when they have fewer than three, from other GSoC organizations that use your first language), leaving out issues someone is already working on and saying how many; and a path from where you are that changes with your experience and hours. The top five organizations (three without a GitHub token) are checked for posts about the coming year, and one that says it will not take part is marked "sitting out" and moved last. [How recommendations work](recommendations.md) has the sources, the ranking, and how it was measured.

## Write and keep evidence

```bash
git-into-gsoc contributions --github YOUR_USERNAME --org "SymPy"
git-into-gsoc draft claim --issue sympy/sympy#12345
git-into-gsoc log --goal "Reproduce #12345" --done "Reproduced on main" --stuck "Flaky test" --next "Ask in Zulip"
```

| Command | Arguments and options | Result |
|---|---|---|
| `contributions` | `--github` / `-g` (default: the username saved with `profile`); `--org` (GSoC organization name or GitHub organization) or `--repo OWNER/REPO` | Your merged, open, and closed pull requests, issues opened, threads joined, and reviews given in that scope; paste-ready lines for a proposal; a standing from `none` to `strong`; honest gaps to close |
| `diagnose FILE` | A file with the failing output, or `-` for standard input; `--repo OWNER/REPO` | The likely cause of a failed setup or test run, quoting the line it matched, and what to try. With `--repo`, what the project's CI sets up: runtime versions, services, install and test commands |
| `pr-check OWNER/REPO#N` | A pull request reference or URL | Your pull request checked against the repository's own rules before a reviewer sees it, each finding with its source, then the branch rules still ahead |
| `draft KIND` | `intro`, `question`, `claim`, `pr`, `review-reply`, `status`, or `final`; `--org`, `--repo`, `--issue`; `--check FILE` checks a message you wrote instead | A skeleton with placeholders, the fields that must hold your own observations, and the rules maintainers and the official guide state, each with its source |
| `log` | `--goal`, `--done`, `--links` (comma-separated), `--learned`, `--stuck`, `--next`; `--limit` / `-n` when listing | Saves a weekly note, or lists recent notes when you give no fields |

Notes:

- `contributions` runs four scoped GitHub searches: pull requests you authored, issues you opened, threads you commented in, pull requests you reviewed. Counts cover public activity, and the search index can lag by minutes.
- `diagnose` knows these shapes: a missing module, a name missing from an installed module (a build left behind after a pull, or a dependency at another version), the wrong runtime version, a missing compiler or C headers, a service such as a database not running, a missing environment variable, a missing command, permissions, the network, a port in use, a lock-file mismatch, memory, a failed style or lint check, and failing tests. It reads logs copied from GitHub Actions or `gh run view --log` as they are.
- `pr-check` looks for a merge conflict, failing checks, a linked issue (a failure when a workflow closes pull requests without one), a description, the template checklist, AI disclosure when the template asks, commit sign-off when the project requires it, commit style, tests changed alongside code, a changelog entry when one is expected, and size.
- `diagnose` given a GitHub Actions log also quotes what the failing step printed, its red lines first, because projects often explain their own checks there.
- `pr-check` with a GitHub token reads the end of up to two failed CI logs and quotes what the failing step printed, such as a project's own explanation and the link it gives. Without a token, or when GitHub no longer keeps a log, it says why the log was not read.
- `draft` fills in real context when you give it: the organization's channels; the project's claim convention read from its CONTRIBUTING (a `/assign` command, a `.take` command, "we do not assign issues", or "wait until you are assigned"), shown as the first rule with the link, or a plain note when the guide says nothing about claiming; whether commits need a sign-off or the pull request template asks for an AI disclosure; the issue's availability; and your latest note for a status post. The general rules after the project's own come from projects that wrote them down, such as pandas and Kubernetes. The `pr` draft ends with the exact commands for a first pull request (clone your fork, add the upstream remote, branch from the real default branch, run the tests, push). It never fills placeholders with observations you have not made. With `--check`, the message you wrote is checked for leftover placeholders, phrases that read as machine-written, a greeting with nothing else, a question with no question, a bare "can I work on this", and a pull request description with no linked issue or testing note.
- `draft claim` for an issue that someone asked to work on before, with no pull request since, opens by asking that person whether they are still on it. With three or more earlier requests, it warns you to lead with a plan instead of another request.
- `log` follows the three questions GSoC organizations ask for in weekly updates. Each field holds up to 2,000 characters, and links must be web addresses. `next` reminds you when the last note is a week old.

## Save local progress

```bash
git-into-gsoc progress summary
git-into-gsoc progress note --value "Next: read the contribution guide."
```

| Action after `progress` | Required value | Effect |
|---|---|---|
| `summary` (default) | none | The phases as a checklist with the next one marked, your shortlist, tracked repositories and issues, and how recent your weekly notes are |
| `complete_phase` | `--phase NAME` | Mark a phase complete. Names: `learn`, `discover`, `evaluate`, `orient`, `community`, `find_issues`, `contribute`, `iterate`, `proposal`, `track` |
| `shortlist_org` | `--value "NAME"` | Save an organization name |
| `track_repo` | `--value OWNER/REPO` | Save a repository as `owner/repo`, once whatever the spelling. A project link on GitLab or another host is saved as it is |
| `track_issue` | `--value URL` | Save an issue or pull request as one GitHub link; `owner/repo#123` works too. An issue link on GitLab or another host is saved as it is; `next` re-checks a GitLab issue through GitLab's public API and lists others without re-checking them |
| `note` | `--value "TEXT"` | Append a note of up to 2,000 characters |

`-v` is short for `--value`. Saving actions print `Saved.` and the summary; with `--output json`, a saving action prints the whole saved state. A value that is not a repository or an issue is refused rather than saved. See [keep track of your progress](guide/08-track-progress.md).

## Setup and maintenance

| Command | Options | Result |
|---|---|---|
| `setup` | `--assistant` / `-a NAME` (repeatable), `--scope user\|project`, `--project-dir`, `--no-skill`, `--no-mcp`, `--dry-run`, `--remove` | Copies the Agent Skill and registers the MCP server with your AI assistants. See below |
| `doctor` | none | Version, Python, cache and data paths, GitHub token source (never the token), remaining API requests, whether each data source (official site, organization archive, commit statistics) answers, the skill source, which assistants have the skill, and where the MCP server is registered. It reports connection errors in its output but may still exit with code zero |
| `cache` | `--prune`, `--clear` | The size of the HTTP cache and its limits; `--prune` deletes old entries now, `--clear` deletes everything |
| `mcp` | none | Starts the MCP server on standard input and output. It waits for an assistant and shows nothing; press Ctrl+C to stop it |
| `feedback` | `--bug`, `--no-open` | Opens the feedback form (or the bug report form with `--bug`) in your browser with the tool version, Python version, and operating system filled in. Nothing is sent until you press Submit; `--no-open` only prints the link |

```bash
git-into-gsoc setup                               # every assistant found, user scope
git-into-gsoc setup --dry-run --assistant all     # preview every assistant
git-into-gsoc setup --scope project --assistant claude-code --assistant cursor
```

| `setup` option | Effect |
|---|---|
| `--assistant` / `-a NAME` | `claude-code`, `cursor`, `codex`, `gemini`, `antigravity`, `windsurf` (Devin Desktop), `vscode` (VS Code and Copilot CLI), or `all`. Default: every assistant with a config folder or executable on this machine |
| `--scope user` (default) | One shared skill copy in `~/.agents/skills`, which Codex, Cursor, Gemini CLI, Devin Desktop, VS Code, and Copilot CLI all read, plus `~/.claude/skills` for Claude Code and `~/.gemini/config/skills` for Antigravity. The MCP server goes into each assistant's user config (Claude Code via `claude mcp add` when available). Copies that older versions left in `~/.cursor/skills`, `~/.codex/skills`, `~/.gemini/skills`, or `~/.codeium/windsurf/skills` are removed, so the skill is listed once. An assistant that already has the git-into-gsoc plugin or extension is left to it |
| `--scope project` | The same inside the current repository (`.agents/skills`, `.claude/skills`, `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.codex/config.toml`, and so on); `--project-dir` picks another folder |
| `--no-skill`, `--no-mcp` | Do only one of the two jobs |
| `--dry-run` | Print the plan without writing |
| `--remove` | Undo: delete the skill copies and remove the MCP registrations for the same scope and assistants, keeping every other entry in those files |

Setup merges into existing JSON and TOML files rather than replacing them, writes a `.bak` copy first, refuses to touch a file it cannot parse, and reports `unchanged` on re-runs. An assistant it cannot configure gets a printed manual command. [Use it in your AI assistant](assistants.md) covers each assistant; [configuration](configuration.md) covers tokens and settings.

## Use output in a script

```bash
git-into-gsoc issues --language rust -n 5 --output json > issues.json
git-into-gsoc repo sympy/sympy --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['health']['grade'])"
```

Successful JSON goes to standard output. Expected failures print `error: ...` and usually a `hint: ...` line to standard error and exit with code 1. Invalid command syntax exits with code 2. Errors are not JSON. A successful command can still return data such as `found: false` or availability `unknown`, so inspect the result as well as the exit code.

[Configuration](configuration.md) · [Troubleshooting](troubleshooting.md) · [Guide contents](README.md)
