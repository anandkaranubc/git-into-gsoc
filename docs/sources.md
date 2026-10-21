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

The accepted-organization list for a year comes from the official site. Multi-year history, project counts per year, and past accepted project titles come from the [community GSoC Organizations archive](https://api.gsocorganizations.dev/), a separate service that mirrors public GSoC pages. When the official site is unavailable the archive copy of the list is used, and the catalog note says so.

Rankings require a technology or topic match when filters are given, then order by continuity, recent project counts, and slot trend. A score is not an acceptance probability, and past project counts do not predict future places or competition. Ideas pages are fetched from the URL each organization published; some hosts block automated readers, in which case the tool reports that rather than guessing.

## GitHub data and scores

Repository grades read the repository's metadata, community profile (CONTRIBUTING, Code of Conduct, templates), workflow count, labels, up to 100 open issues under its beginner label, and the 60 most recently updated closed pull requests. Merge rates exclude bots and are split by `author_association`, so "outside contributors" means authors without write access. Review time is the median from opening to merging among human PRs in that sample, not the time until a newcomer gets a first reply. Missing files can reflect a different project layout or an API failure.

Issue searches ask GitHub for open, unassigned issues without linked PRs in non-archived repositories, updated in the last year, with the chosen label. The top candidates' timelines are read (up to 100 events each) for linked PRs, claims matching common phrasings ("can I work on this", "assign me"), maintainer approvals, and engagement. Claims phrased unusually, coordination in chat, and very long threads are not visible to the tool. Read the discussion yourself.

Organization scoping uses the GitHub organizations linked from each GSoC organization's official listing. Organizations whose code lives outside GitHub, or under a personal account, are not covered by `issues --scope gsoc`.

## Caching

GitHub responses are cached for an hour and revalidated with the server afterwards. Organization lists, archives, and ideas pages are cached for a day. When a source fails, a cached copy up to a week old is served and a warning is logged. See [configuration](configuration.md) for refreshing results.

## If a source is unavailable

Say what could not be checked. Use official organization pages and GitHub directly, or try again later. Do not fill gaps with invented organizations, issues, deadlines, or claims about your likelihood of acceptance.

[Guide contents](README.md) · [Architecture](architecture.md)
