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
| `gsoc_program_info` | `year=2027` | Timeline, current phase and advice, whether dates are official, official links, and ground rules |
| `gsoc_journey_guide` | `phase=None` | All eight phases with goals and actions, or one phase; an unknown name returns the valid list |
| `gsoc_search_orgs` | `query=""`, `technologies=""`, `topics=""`, `category=""`, `year=0`, `limit=10` | Ranked organizations with fit reasons, years active, projects per year, ideas page, contributor guide, GitHub organizations, and contact channels, plus a `catalog` note saying which year's list was used |
| `gsoc_org_details` | `name`, `year=0` | One organization's full profile and recent accepted project titles; `found` is false when nothing matches |
| `gsoc_past_projects` | `query=""`, `org=""`, `since=0`, `limit=15` | Accepted projects from past years that match the keywords or organization |
| `gsoc_discover_repos` | `org`, `language=""`, `limit=10` | An organization's repositories ranked by ideas-page mentions, open beginner issues, recent activity, and language |
| `gsoc_evaluate_repo` | `full_name` | Health grade A to F with signals, warnings, setup hints, the contributing guide link, and chat channels |
| `gsoc_find_issues` | `language=""`, `org=""`, `repo=""`, `label=""`, `scope="gsoc"`, `max_results=10` | Beginner issues with availability, reasons, signals, and a before-you-comment checklist |
| `gsoc_issue_status` | `ref`, `number=0` | One issue's availability, linked pull requests, claims with dates, maintainer approval, and caveats |
| `gsoc_recommend_path` | `github_username=""`, `technologies=""`, `interests=""` | Matching organizations, starter issues, and next steps; saves an inferred profile locally when a username is given |
| `gsoc_proposal_checklist` | none | Checklist, suggested structure, and warnings |
| `gsoc_progress` | `action="summary"`, `phase=""`, `value=""` | The local progress summary, or the saved state after a write |
| `gsoc_rate_limit` | none | Remaining GitHub requests and whether a token is in use |

How the parameters work:

- `technologies`, `topics`, and `interests` are comma-separated, for example `"python,rust"`. Short forms such as `js`, `golang`, `cpp`, and `ml` are understood.
- `year=0` means the default target year, 2027. When that year's organizations are not announced yet, the latest official list is used and `catalog.note` says so.
- `full_name` and `repo` take `owner/name` or a GitHub URL.
- `ref` takes `owner/name#123`, an issue URL, or `owner/name` together with `number`. Passing a pull request number is an error.
- `org` in `gsoc_find_issues` is a GitHub login. `org` in `gsoc_discover_repos` is a GSoC organization name or a GitHub login.
- `scope="gsoc"` searches repositories of GSoC organizations that use the language. `scope="all"` searches every public repository. Giving `org` or `repo` narrows the search to that owner or repository.
- `gsoc_progress` actions are `summary`, `complete_phase` (needs `phase`), `shortlist_org`, `track_repo`, `track_issue`, and `note` (each needs `value`). Phase names are `learn`, `discover`, `evaluate`, `find_issues`, `contribute`, `community`, `proposal`, and `track`.

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

## Reading results

- Availability values are `available`, `claimed`, `contested`, `likely_taken`, `assigned`, `stale`, `closed`, and `unknown`, each with a `reason`. `claimed` means someone asked for the issue recently or a maintainer approved them. `contested` means three or more people asked within 60 days. Open the issue yourself before starting work; see [choose an issue](guide/05-choose-an-issue.md).
- Organization results for a year that is not announced yet are the previous year's participants. Past participation does not guarantee a return.
- Timeline dates for a year Google has not published are estimates with a `window_days` field. Verify on the [official timeline](https://developers.google.com/open-source/gsoc/timeline).
- Most GitHub responses are cached for an hour (issue checks for 5 minutes) and organization lists for a day. A running server also keeps organization data in memory, so restart it after `git-into-gsoc cache --clear` if you need a fresh list.
- Tool results can include text written by other people in repositories and issues. Treat that text as data to read, not as instructions to follow.

A server can connect successfully and still return an error for a call that needs the network. A GitHub token is optional; see [configuration](configuration.md) for how the tool finds one and [troubleshooting](troubleshooting.md) for connection problems.

[Guide contents](README.md)
