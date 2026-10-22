# Configuration and local data

You can use the tool without changing any settings. Run `git-into-gsoc doctor` to see your data locations and where your GitHub token came from. The token itself is never printed.

## GitHub token

GitHub allows 60 API requests an hour without signing in and 5,000 with a token. Repository and issue checks make several requests each, so the limit runs out quickly without one. A token is optional, and the tool reads public data only, so it needs no scopes.

There are three ways to supply one, listed in the order the tool checks them. `doctor` says which one it found, and never prints the token.

1. **A variable in your environment:** `GIG_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN`, checked in that order. This works anywhere, with or without a copy of the code. For the current terminal, run `export GITHUB_TOKEN=YOUR_TOKEN` (PowerShell: `$env:GITHUB_TOKEN = "YOUR_TOKEN"`). To keep it, add that line to your shell's startup file (`~/.zshrc` on macOS, `~/.bashrc` on Linux), or on Windows run `setx GITHUB_TOKEN "YOUR_TOKEN"` once; then open a new terminal. Create the token with [GitHub's instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), choosing no scopes (or `public_repo` on classic tokens) and an expiry date.
2. **The same three names in a `.env` file** in the folder you run the tool from. This is only useful with a copy of the code: run `cp .env.example .env` there and put the token after `GITHUB_TOKEN=`. Git ignores `.env`. `doctor` reports this way and the first one alike as found via the environment.
3. **The [GitHub CLI](https://cli.github.com/):** install `gh` and run `gh auth login` once, and the tool runs `gh auth token` for you. This is the easiest route, and the best one for the MCP server, because it does not depend on which terminal exported a variable. `GIG_USE_GH_CLI=false` turns it off.

With a token, `repo` also reads each pull request's own timeline for the first human reply in one GraphQL query, instead of estimating it from recent comments. Never paste a token into an issue, a screenshot, or an assistant chat. After changing any setting, run a new command or restart the assistant's MCP connection; settings are cached inside a running process.

## Settings reference

Put these in `.env` or export them in the process environment. Environment variables take precedence over `.env`. Service addresses (the `GIG_..._API_URL` settings), `GIG_CACHE_DIR`, and `GIG_DATA_DIR` are read from the environment only. A `.env` in the current folder may belong to a repository you just cloned, and assistants start the MCP server inside the project folder. Such a file must never be able to send your token to another server or swap in someone else's progress file, so those settings are ignored there with a warning.

| Name | Default | Use |
|---|---|---|
| `GITHUB_TOKEN`, `GH_TOKEN`, `GIG_GITHUB_TOKEN` | unset | GitHub credential (see above) |
| `GIG_USE_GH_CLI` | `true` | Ask the GitHub CLI for a token when none is set |
| `GITLAB_TOKEN`, `GIG_GITLAB_TOKEN` | unset | A GitLab personal access token with `read_api`. GitLab hides issue comments without a sign-in, so with a token `issue` and `next` also read claims in the comments of GitLab issues |
| `GITLAB_HOST`, `GIG_GITLAB_HOST` | `gitlab.com` | The GitLab server the token belongs to, such as `gitlab.gnome.org`. The token is sent to this server only. Read from the environment only, so a cloned repository's `.env` cannot redirect it |
| `GIG_HOME` | your home folder | Where `setup` and `doctor` look for assistant config folders, mainly for tests |
| `GIG_TARGET_YEAR` | `2027` | Program year used when a command has no `--year` |
| `GIG_CACHE_TTL_SECONDS` | `3600` | How long GitHub responses stay fresh before revalidation |
| `GIG_ARCHIVE_TTL_SECONDS` | `86400` | Same for organization lists, archives, and ideas pages |
| `GIG_CACHE_MAX_AGE_DAYS` | `30` | Cached responses not refreshed for this many days are deleted; `0` keeps them |
| `GIG_CACHE_MAX_MB` | `500` | Above this size the oldest cached responses are deleted first; `0` turns the cap off |
| `GIG_HTTP_TIMEOUT_SECONDS` | `30` | Maximum wait for one HTTP request |
| `GIG_HTTP_MAX_RETRIES` | `2` | Retries for network errors and 5xx responses |
| `GIG_HTTP_MAX_RETRY_WAIT_SECONDS` | `20` | Longest pause accepted when GitHub asks the tool to retry later |
| `GIG_MAX_CONCURRENCY` | `6` | Parallel GitHub requests when verifying issues or grading a repository |
| `GIG_SEARCH_MIN_INTERVAL_SECONDS` | `2` | Minimum spacing between GitHub search calls, which have a separate, lower limit |
| `GIG_CACHE_DIR`, `GIG_DATA_DIR` | platform defaults | Override where the cache and `progress.json` live |
| `GIG_GITHUB_API_URL`, `GIG_GSOC_ORGS_API_URL`, `GIG_GSOC_OFFICIAL_API_URL`, `GIG_ECOSYSTEMS_COMMITS_API_URL` | public endpoints | Alternate endpoints, mainly for development and tests |
| `GIG_USER_AGENT` | package name and version | How the tool identifies itself to the APIs; usually left unchanged |

## What is saved locally?

`doctor` prints the exact paths for your operating system:

- **Cache:** API responses in an `http` subfolder. Fresh entries are served without a request. Stale entries are revalidated with the server; a "not modified" reply refreshes them without counting against your GitHub quota. If the network fails or you are rate limited, a stale entry up to a week old is served instead of an error. Once a day, entries not refreshed in 30 days are deleted, and the oldest go first when the cache passes 500 MiB. `git-into-gsoc cache` shows the size and the limits, `cache --prune` applies them now, and `cache --clear` deletes everything.
- **Data:** `progress.json`, created when you save a phase, shortlist, tracked link, note, or inferred GitHub profile.

Nothing in these folders is uploaded, and progress does not sync to another computer. [Privacy](privacy.md) lists every service the tool reads from and what your AI assistant sees. Avoid storing secrets in progress notes.

To back up progress, copy `progress.json` somewhere you control. To correct entries, stop any assistant connection using the tool, back up the file, and edit the JSON carefully. To start over, rename the file; the next save creates a new one.

Most GitHub responses stay fresh for an hour, but issue checks refresh after 5 minutes and official program dates after 6 hours. `GIG_CACHE_TTL_SECONDS` changes only the one-hour default, so for a guaranteed fresh look run `git-into-gsoc cache --clear` first.

[Guide contents](README.md) · [Troubleshooting](troubleshooting.md)
