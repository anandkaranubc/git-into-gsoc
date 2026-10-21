# MCP reference

## Run

```bash
git-into-gsoc mcp
# or
python -m git_into_gsoc.mcp_server
```

## Tool catalog

All tools return JSON strings for maximum client compatibility.

### `gsoc_program_info(year=2027)`

Timeline, disclaimer, official URLs, anti-spam rules.

### `gsoc_journey_guide(phase?)`

Full overview or a single phase playbook.

### `gsoc_search_orgs(query, technologies, topics, category, year=2026, limit=10)`

Comma-separated `technologies` / `topics`. Uses archive data.

### `gsoc_org_details(name)`

Exact or fuzzy org lookup.

### `gsoc_discover_repos(org, language?, limit=10)`

Rank a GSoC org's repositories for a first contribution: ideas-page mentions, open beginner issues, recent activity, preferred language.

### `gsoc_evaluate_repo(full_name)`

Health grade (A-F) with evidence: activity, community files, CI, open beginner issues, bot-free merge rate, outside-contributor merge rate, review speed, toolchain and dev-container hints.

### `gsoc_find_issues(language, org, repo, max_results=10)`

Beginner-labeled issues with availability classification.

### `gsoc_issue_status(full_name, number)`

`available` | `likely_taken` | `assigned` | `stale` | `closed` | `unknown`.

### `gsoc_recommend_path(github_username, technologies, interests)`

Profile languages + ranked orgs + sample issues.

### `gsoc_proposal_checklist()`

Checklist, structure, warnings.

### `gsoc_progress(action, phase, value)`

Actions: `summary`, `complete_phase`, `shortlist_org`, `track_repo`, `track_issue`, `note`.

### `gsoc_rate_limit()`

GitHub API remaining quota.

## Auth

```bash
export GITHUB_TOKEN=...   # or GH_TOKEN
```

Unauthenticated use works with severe rate limits.

## Client config

See `skills/git-into-gsoc/assets/mcp.example.json` and `references/install.md`.
