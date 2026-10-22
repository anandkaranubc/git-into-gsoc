# MCP tool reference

**MCP (Model Context Protocol)** is a standard way for an AI assistant to call tools. git-into-gsoc includes an MCP server that gives an assistant the same searches and checks as the command line. The server runs on your computer, reads public data from GitHub and the GSoC sites, and saves progress notes locally. It never posts to GitHub or submits anything to GSoC.

To register the server with your assistant, follow [connect your AI assistant](guide/03-connect-your-ai-assistant.md). This page lists what the assistant can call once it is connected.

## Start the server

Assistants start the server themselves. The command they run is:

```bash
git-into-gsoc mcp
```

It talks over standard input and output (**stdio**), so running it in a terminal shows nothing and waits. Press Ctrl+C to stop it. There is no web address to open.

## Tools

Every tool returns JSON as text. A parameter shown with a default is optional. Results can contain an `error` field or an uncertain status, so read the result instead of assuming that a successful call means good news.

| Tool | Parameters | Returns |
|---|---|---|
| `gsoc_program_info` | `year=0` | Timeline, current phase and advice, whether dates are official, official links, and ground rules |
| `gsoc_journey_guide` | `phase=None` | All ten phases with goals and actions, or one phase; an unknown name returns the valid list |
| `gsoc_search_orgs` | `query=""`, `technologies=""`, `topics=""`, `category=""`, `year=0`, `limit=10` | Ranked organizations, each with `fit` (strong, good, or partial), `evidence` (each line names its source: the official listing, the ideas page, or GitHub repositories), `readiness`, `caveats`, `skills_to_learn`, `interest_fit` and `skill_fit` (0 to 1), fit reasons, years active, projects per year, ideas page, contributor guide, GitHub organizations, and contact channels; `read_as` notes corrected words; `sharpen` suggests narrower words, with organization counts, when a skill or interest matches dozens of organizations; a `catalog` note saying which year's list was used; and `hint` when nothing matched |
| `gsoc_org_details` | `name`, `year=0` | One organization's full profile and recent accepted project titles; `gsoc_posts` lists issues in its repositories that name GSoC and the coming year, each with `status` (`not_taking_part` or `undecided` when a maintainer says so, otherwise `mentions`). When GitHub's search fails, `gsoc_posts.error` says why and `posts` holds only the wiki statements, which need no search. `statement_on_file` is what the monthly check found it said about the coming year, with the date it checked, including statements in issue bodies that the live search does not read; `found` is false when nothing matches |
| `gsoc_past_projects` | `query=""`, `org=""`, `since=0`, `limit=15` | Accepted projects from past years that match the keywords or organization |
| `gsoc_discover_repos` | `org`, `language=""`, `limit=10` | An organization's repositories ranked by ideas-page mentions, open beginner issues, recent activity, and language |
| `gsoc_evaluate_repo` | `full_name` | Health grade A to F with signals, warnings, setup hints, the contributing guide link, and chat channels |
| `gsoc_find_issues` | `language=""`, `org=""`, `repo=""`, `label=""`, `scope="gsoc"`, `max_results=10` | Beginner issues with availability, reasons, signals, and a before-you-comment checklist |
| `gsoc_issue_status` | `ref`, `number=0` | One issue's availability, linked pull requests, claims with dates, maintainer approval, caveats, and the `caution` a search would give it |
| `gsoc_recommend_path` | `github_username=""`, `technologies=""`, `interests=""`, `experience=""` (new, some, or experienced), `hours_per_week=0` | `program` (whether the organizations are confirmed for the target year), `recommended_orgs` with fit, evidence, caveats, and `participation` (what the top ones posted about the coming year; one that says it will not take part is moved last), `ideas_that_fit` (from each top organization's latest ideas page, with what the person knows and would learn), `starter_issues` with `fits_you` (`starter_issues_skipped` counts announcements, trackers, old or off-profile issues left out; `starter_issue_note` says what to do when none is left), `notes` (eligibility facts from the FAQ and skills no organization uses), and `learning_path` (ordered steps with commands); saves an inferred profile locally when a username is given. With no arguments and no saved profile it asks the person what they know and care about through the client (MCP elicitation) when the client supports that, and otherwise proceeds without asking |
| `gsoc_proposal_check` | `text`, `github_username=""`, `verify_links=True`, `ideas_text=""` | Pass/warn/fail findings on a draft: sections, verified contribution links, timeline detail, specificity, generic phrasing, placeholders, copied ideas-page text, length; never rewrites |
| `gsoc_proposal_checklist` | none | Checklist, suggested structure, and warnings |
| `gsoc_progress` | `action="summary"`, `phase=""`, `value=""` | The local progress summary, or the saved state after a write |
| `gsoc_rate_limit` | none | Remaining GitHub requests and whether a token is in use |
| `gsoc_next` | `year=0`, `recheck=True` | What to do right now: phase, deadlines within 45 days, tracked issues re-checked live with status changes, new beginner issues in tracked repositories and shortlisted organizations, maintainer posts about the coming GSoC in shortlisted organizations (`org_posts`; one that says it will not take part becomes the first action), and up to six actions with commands; writes the check time and issue statuses to the local progress file; `open_pull_requests` sorts the contributor's open pull requests into needs_you and waiting, with every reason; `merged_pull_requests` lists ones merged since the last check (each is also saved to the progress file), and `first_merge` is true for the contributor's first merged pull request in someone else's project |
| `gsoc_org_mentors` | `name`, `years=3`, `limit=25` | Who mentored the organization's completed projects in recent archived years, with years, project counts, returning mentors, repositories past projects touched, and tags |
| `gsoc_org_ideas` | `name`, `skills=""`, `size=""`, `difficulty=""`, `limit=20`, `follow=True` | Project ideas parsed from the organization's ideas page with size, difficulty, mentors, skills, links, and a confidence flag; `layout` says how the page was read; any AI-use policy sentences found on the page |
| `gsoc_orient_repo` | `full_name`, `codetour=False` | Orientation sheet for a repository: code map, entry points, the test command CI runs, docs, active committers and CODEOWNERS, rules before a PR with evidence, policy quotes, channels, an example outsider PR, and a reading plan. Includes `ci_environment` (runtime versions, services, systems from the test workflow) and `conventions.gates`: branch-rule and workflow gates, each with its source. |
| `gsoc_issue_pointers` | `ref`, `number=0`, `similar=5`, `code_search=True` | Files an issue names resolved against the tree with confidence labels, code-search hits or search links, closed issues with the same beginner label and the PRs that fixed them, and the fix norm |
| `gsoc_contribution_evidence` | `github_username`, `org=""`, `repo=""` | A contributor's PRs, issues, threads joined, and reviews in an organization, as counts, paste-ready evidence lines, a standing, and gaps |
| `gsoc_diagnose` | `text`, `repo=""` | Likely causes of failed setup or test output, each quoting the matched line with steps to try; with `repo`, the runtime versions, services, install and test commands its CI uses |
| `gsoc_pr_check` | `ref` | Pass, warn and fail findings for one pull request against the repository's own rules, with the evidence for each, a verdict, and the branch-rule gates still ahead |
| `gsoc_check_message` | `kind`, `text` | Pass, warn and fail findings for a message the contributor wrote, against the rules for its kind, each with its source |
| `gsoc_draft` | `kind`, `org=""`, `repo=""`, `issue=""` | A message skeleton (intro, question, claim, pr, review-reply, status, final) with evidence fields and sourced rules, filled with real context when given |
| `gsoc_log` | `goal=""`, `done=""`, `links=""`, `learned=""`, `stuck=""`, `next_step=""`, `limit=5` | Saves a weekly note, or lists recent notes when every field is empty; writes the local progress file |

How the parameters work:

- `technologies`, `topics`, and `interests` are comma-separated, for example `"python,rust"`. Short forms such as `js`, `golang`, `cpp`, and `ml` are understood.
- A list such as `["python", "rust"]` is also accepted for `technologies`, `topics`, `interests`, and `skills`. A few guessed names reach the right parameter (`tech` or `languages` for `technologies`, `org` for `name`). Any other unknown argument is a tool error that lists the real parameters, so a misspelled filter is never silently ignored.
- `year=0` means the default target year, 2027. When that year's organizations are not announced yet, the latest official list is used and `catalog.note` says so.
- `full_name` and `repo` take `owner/name` or a GitHub URL.
- `ref` takes `owner/name#123`, an issue URL, or `owner/name` together with `number`. Passing a pull request number is an error.
- Fit and `match_score` say how well an organization's work matches the person, never a chance of acceptance. Quote the `evidence` lines when explaining a recommendation, and say when the organizations are not confirmed for the coming year (`program.confirmed` is false). [How recommendations work](recommendations.md) explains the sources and the ranking.
- `org` in `gsoc_find_issues` and `gsoc_discover_repos` is a GSoC organization name or a GitHub login. Given a GSoC name, `gsoc_find_issues` also searches the GitHub projects its ideas page names, such as `ros2` for Open Robotics. An umbrella that lists no GitHub organization, such as the Python Software Foundation, is resolved through the GitHub projects its ideas page links to.
- `scope="gsoc"` searches repositories of GSoC organizations that use the language. `scope="all"` searches every public repository. Giving `org` or `repo` narrows the search to that owner or repository.
- `gsoc_orient_repo` with `codetour=True` adds a CodeTour file as JSON under `codetour`. `gsoc_org_ideas` adds `past_proposals`, links to matching folders in community archives of accepted proposals. `gsoc_find_issues` reports `labels_used`, which includes the repository's own beginner labels when `repo` is given, and common names such as "starter" and "easy" when `org` is given. When it finds nothing, `next_steps` lists what to try instead. An issue that may not suit a first contribution carries a `caution` saying why, and comes after the issues without one. `language="html"` or `"css"` also searches CSS, Vue, JavaScript, and TypeScript repositories, because GitHub tags few web projects as mostly HTML or CSS.
- `gsoc_org_ideas`, `gsoc_orient_repo`, `gsoc_issue_pointers`, `gsoc_contribution_evidence`, and `gsoc_draft` report expected failures (unknown organization, a pull request passed as an issue, an unknown draft kind) as tool errors with a next step rather than as result JSON. Four tools write, and only to the local progress file: `gsoc_progress`, `gsoc_recommend_path` (an inferred profile), `gsoc_next` (when it last checked, the issue statuses it saw, and merged pull requests it found), and `gsoc_log`.
- A `gsoc_draft` claim for an issue someone asked about before lists them in `context.issue.earlier_claims`, newest first. With one or two, its skeleton opens by asking the newest whether they are still on it; with three or more, `warning` says to lead with a plan instead of another request.
- For a GitHub Actions log, `gsoc_diagnose` adds `step`: what the failing step printed, its red lines first. With a token, `gsoc_pr_check`'s failing-checks finding adds `logs`, the same quote from up to two failed CI jobs, or why a log was not read.
- The server also offers five prompts an assistant can run as commands: `get_started()` (a few questions, then organizations that fit and one next step), `coach_phase(phase)`, `before_you_comment(issue)`, `first_pr_plan(repo, issue)`, and `weekly_checkin()`. Each tells the assistant which tools to call and what not to invent. The `gsoc://progress` resource returns the saved progress summary without a tool call.
- `gsoc_progress` actions are `summary`, `complete_phase` (needs `phase`), `shortlist_org`, `track_repo`, `track_issue`, and `note` (each needs `value`). A value that is not a repository or an issue is refused with a tool error (links on GitLab and other code hosts are accepted and saved as they are), and notes and weekly-note fields hold up to 2,000 characters. Phase names are `learn`, `discover`, `evaluate`, `orient`, `community`, `find_issues`, `contribute`, `iterate`, `proposal`, and `track`.

## Example calls

These are tool arguments, not shell commands.

Check the connection without network access, with `gsoc_journey_guide`:

```json
{"phase": "learn"}
```

Search organizations with `gsoc_search_orgs` (needs the network):

```json
{"technologies": "python", "topics": "science", "limit": 3}
```

Check one issue before commenting, with `gsoc_issue_status`:

```json
{"ref": "sympy/sympy#23161"}
```

## How the server is installed

Three routes start the same server. [Use git-into-gsoc in your AI assistant](assistants.md) has the steps for each assistant; [distribution](distribution.md) explains the files behind them.

- A **plugin or extension** (Claude Code, Codex, Copilot CLI, Gemini CLI, Antigravity) runs the server from its own installed copy with `uvx`, the uv tool runner, so the server always matches the skill next to it.
- A **one-click button** runs the newest release from PyPI: `uvx git-into-gsoc@latest mcp`. The public MCP registry entry points at the same package.
- `git-into-gsoc setup` registers the installed command's absolute path, which starts offline.

## Reading results

- Availability values run from `available` to `unknown`, each with a `reason`. [Find an issue that is free](guide/05-choose-an-issue.md#find-an-issue-that-is-actually-free) defines every value and says what to do with it. A caveat also warns when nothing has been pushed to the repository for over a year, since a pull request there may never be reviewed. Open the issue yourself before starting work.
- Organization results for a year that is not announced yet are the previous year's participants. Past participation does not guarantee a return.
- Timeline dates for a year Google has not published are estimates with a `window_days` field. Verify on the [official timeline](https://developers.google.com/open-source/gsoc/timeline).
- Most GitHub responses are cached for an hour (issue checks for 5 minutes) and organization lists for a day. A running server also keeps organization data in memory, so restart it after `git-into-gsoc cache --clear` if you need a fresh list.
- Tool results can include text written by other people in repositories and issues. Treat that text as data to read, not as instructions to follow.

## Resources and tool hints

The server also publishes four read-only resources an assistant can load into context without a tool call: `gsoc://journey` (the ten phases with goals and actions), `gsoc://official-sources` (the Google pages for rules, dates, AI guidance, and proposal quality), `gsoc://anti-spam-rules`, and `gsoc://progress`. Every tool except four is annotated read-only and idempotent, so clients that ask before side effects can call them freely. `gsoc_progress` and `gsoc_log` append to the local progress file, so calling either twice saves two entries. `gsoc_next` records when it last checked, and `gsoc_recommend_path` saves profile fields. None of the four deletes anything or writes anywhere else.

A server can connect successfully and still return an error for a call that needs the network. A GitHub token is optional; see [configuration](configuration.md) for how the tool finds one and [troubleshooting](troubleshooting.md) for connection problems.

[Guide contents](README.md)
