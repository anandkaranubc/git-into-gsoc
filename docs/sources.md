# Sources and limitations

The tool combines public data with transparent ranking rules. It cannot confirm that a project will accept you, that an issue is reserved for you, or that an organization will participate next year.

## Official program information

| Source | What it provides |
|---|---|
| [summerofcode.withgoogle.com](https://summerofcode.withgoogle.com) | The year's milestones and the accepted-organization list, read from the public endpoints behind the official site |
| [Timeline](https://developers.google.com/open-source/gsoc/timeline) | The page to verify dates, times, and time zones on |
| [FAQ](https://developers.google.com/open-source/gsoc/faq) | Eligibility and how the program works |
| [Contributor guide](https://google.github.io/gsocguides/student/) | Community participation and proposal advice |
| [AI guidance](https://developers.google.com/open-source/gsoc/resources/ai_guidance) | Responsibilities when using AI, alongside organization-specific rules |
| [Proposal quality guidance](https://developers.google.com/open-source/gsoc/resources/spam_proposals) | Why generic proposals and missing preparation cause problems |

`program` shows official dates when Google has published the year. For an unpublished year it projects the latest official year forward by 52 weeks and attaches an uncertainty window measured from how much each milestone moved between the two most recent years. Those are planning estimates, labelled as such in every output. The official endpoints are undocumented, so when they change or are unreachable the tool falls back to an embedded snapshot and says so.

## Organizations

The accepted-organization list for a year comes from the official site. Multi-year history (which years each organization mentored and how many projects it ran) comes from a compact snapshot embedded in the package, generated from the [community GSoC Organizations archive](https://api.gsocorganizations.dev/), a separate service that mirrors public GSoC pages. Past accepted project titles are fetched from that archive on demand (`org`, `projects`), which is a large download cached for a day. When the official site is unavailable the archive copy of the list is used; when both are unreachable, the embedded snapshot of the latest official list is used and the catalog note names its date and tells you to verify on the official site. The snapshot is refreshed with each release, so an organization that joined after the release appears only once the live sources are reachable.

Rankings require a technology or topic match when filters are given, then order by continuity, recent project counts, and slot trend. A score is not an acceptance probability, and past project counts do not predict future places or competition. Ideas pages are fetched from the URL each organization published; some hosts block automated readers, in which case the tool reports that rather than guessing.

## GitHub data and scores

Repository grades read the repository's metadata, community profile (CONTRIBUTING, Code of Conduct, templates), workflow count, labels, up to 100 open issues under its beginner label, and the 60 most recently updated closed pull requests. Merge rates exclude bots and are split by `author_association`, so "outside contributors" means authors without write access. GitHub assigns that field when the list is fetched, so anyone whose PR merged shows as a contributor and "first-time contributor" never appears on a merged PR; the tool therefore counts distinct outside authors merged instead, and scores the outside merge rate only when at least ten outside PRs are in the sample. Stars add no points, because larger projects reject a higher share of newcomer PRs. Review time is the median from opening to merging among human PRs in that sample, not the time until a newcomer gets a first reply. Missing files can reflect a different project layout or an API failure.

Issue searches ask GitHub for open, unassigned issues without linked PRs in non-archived repositories, updated in the last year, with the chosen label. A search returns at most 30 issues and keeps at most two per repository. With `--scope gsoc`, it covers the first GitHub organization of up to 12 top-ranked GSoC organizations for the language, fewer when the search query would get too long. The top candidates' timelines are read (up to 100 events each) for linked PRs, claims matching common phrasings ("can I work on this", "assign me"), maintainer approvals, and engagement. Claims phrased unusually, coordination in chat, and very long threads are not visible to the tool. Read the discussion yourself.

Organization scoping uses the GitHub organizations linked from each GSoC organization's official listing. Organizations whose code lives outside GitHub, or under a personal account, are not covered by `issues --scope gsoc`. `repos` reads up to 100 repositories from each of the first three GitHub owners linked to an organization and skips forks, archived repositories, repositories with issues disabled, and anything not pushed in the last year.

## Ideas pages, orientation, pointers, and evidence

Where these features came from, and which ideas from other tools were adopted or rejected, is in the [research notes](research.md).

`ideas` fetches the URL each organization published, in the most structured form available: raw markdown for GitHub wikis and repository files, the HTML export for Google Docs, and the page itself otherwise. The parser looks for the small vocabulary organizations use (difficulty, size or duration, mentors, skills, expected outcome, links) under the heading level that carries the ideas. It reports a confidence per idea, marks a page as an index when it only links onward, follows up to eight linked sub-project pages, reads ideas kept as GitHub issues through the issue search, and says when a page could not be fetched. Roughly a third of organizations publish pages with full labels, a third give partial fields, and the rest are prose, tables, or indexes; the tool says which it found rather than guessing fields.

`orient` reads the repository tree, languages, community profile, commits from the last 90 days, the 30 most recent closed pull requests, the check names on one merged pull request, and the raw CONTRIBUTING, pull request template, CODEOWNERS, the package manifest (pyproject.toml, package.json, and similar), and up to two workflow files. Purpose labels on the code map are guesses from directory names and are marked as such; everything else names a real path, commit, or check. Committer counts come from commits, so maintainers who review without committing are not shown.

`pointers` reads the issue, the tree, the repository labels, one search for closed issues with the same beginner label, their timelines, and the changed files of the pull request merged within seconds of each close (or, marked as a likely fix, the most recent earlier merge in the same repository). Code search runs only with a token and at most twice per run because GitHub allows ten code searches a minute. Identifier matching is text matching, not program analysis.

`contributions` uses four GitHub searches scoped to the organization's GitHub owners or one repository: pull requests you authored, issues you opened, threads you commented in, and pull requests you reviewed. Counts cover public activity only and the search index can lag by minutes.

Text written by other people (issue and pull request titles, idea descriptions, policy sentences, repository descriptions) is cleaned before it is shown: hidden Unicode characters, HTML comments and risky tags are removed and length is capped. It is still data written by strangers; read it as such.

## Caching

Most GitHub responses are cached for an hour and revalidated with the server afterwards. Issue details and timelines are cached for 5 minutes, beginner-issue counts for 15 minutes, and official program dates for 6 hours. Organization lists, archives, and ideas pages are cached for a day. When a source fails, a cached copy up to a week old is served and a warning is logged. See [configuration](configuration.md) for refreshing results.

## If a source is unavailable

Say what could not be checked. Use official organization pages and GitHub directly, or try again later. Do not fill gaps with invented organizations, issues, deadlines, or claims about your likelihood of acceptance.

[Guide contents](README.md) · [Architecture](architecture.md)
