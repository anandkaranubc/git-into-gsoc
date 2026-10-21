# What we learned from other tools, and what we built

In October 2026 we surveyed the tools, data sources, and research around open source onboarding and Google Summer of Code, read the strongest projects' source code, and turned the findings into features. This page keeps the useful part: where ideas came from, why we adopted or rejected them, and which commands they became. No code was copied; licenses are noted where an idea came from a specific project.

## Data sources

| Source | What we use it for | Notes |
|---|---|---|
| [summerofcode.withgoogle.com public JSON](https://summerofcode.withgoogle.com/api/program/2026/) | Program timeline, accepted organizations | The same endpoints the official site's own front end calls. Only completed projects are exposed in the archive. |
| [GSoC Organizations archive](https://api.gsocorganizations.dev/) | Multi-year history, slot counts, past project titles | A hand-updated snapshot that lags announcements by days to weeks and drops mentor names and per-project tags, so we treat the official site as primary. |
| [GitHub REST API](https://docs.github.com/en/rest) | Repositories, issues, timelines, trees, commits, pull request files, code search | One recursive tree call returns a whole repository; an issue's timeline reveals the pull request that closed it. |

## Ideas we adopted

- **Ideas pages have a small, stable vocabulary.** We fetched the ideas pages of all 183 GSoC 2026 organizations. 168 loaded; of those, 118 state a size or hours, 129 name mentors, 113 list skills, 97 state difficulty. A heading-plus-label parser extracts clean idea blocks from about a third of pages and partial fields from another third. This became `ideas ORG`, which reports its confidence per idea and says when a page is an index or unreadable. Google Docs are read through their HTML export so headings survive; the plain-text export flattens them.
- **Organizations publish AI-use policies, and they differ.** 75 of the fetched pages contain a sentence about AI or language-model use, from outright bans to disclosure templates. `ideas` and `orient` quote them verbatim with their source instead of stating one global rule.
- **Prior public engagement is what reviewers score.** Google's organization-admin guidance, and 2025 to 2026 posts from OpenStreetMap, Rust, Jenkins, INCF, and Wikimedia, converge on contact before applying, contributions during the application phase, and template adherence. `contributions --github USER --org ORG` collects the evidence reviewers look for, and `next` asks for one public introduction before suggesting an issue.
- **The weekly note has a known shape.** The Python Software Foundation's GSoC blogs ask three questions every week: what did you do, what is next, where are you stuck. `log` uses those fields plus links and what you learned, and `draft status` turns the latest note into a post.
- **Newcomers' first patches land when they are small bug fixes with tests, and when the author answers review promptly.** Turzo, Sultana and Bosu (2025, 1,155 GitHub projects and five Gerrit projects) found good-first-issue labels, few files, few added lines, and prompt, patient responses to review predict acceptance; longer or prettier descriptions do not. `pointers` shows the repository's real fix norm (median files, how often fixes touch tests) and `draft pr` and `draft review-reply` carry the rules.
- **"Unclear how to start" and "no response" are the top newcomer barriers** (Tan, Zhou and Sun, ICSE 2023, 48,402 good first issues). `orient` answers the first with facts and paths: where the code lives, how CI runs the tests, who merges, and what the rules are before a pull request. `draft question` and `next` address the second by prompting a public, well-formed question after a few days of silence.
- **The pull request that closed an issue is findable from the timeline.** On matplotlib, four of six closed good-first-issues had a same-repository pull request merged within one second of the close, and every fix touched the tests directory. `pointers` uses that rule to learn from past fixes without cloning.
- **Full paths beat trees for machines and people.** The Agentless project reported that listing full file paths, at most five, stopped language models from inventing paths. `orient` and `pointers` print full repository-relative paths and never a nested tree or generated prose.
- **Sanitise what strangers wrote.** The GitHub MCP server sanitises every issue body by default; Unicode tag characters can hide text that models read and people cannot. All titles, descriptions, and quotes we show pass through one cleaner.
- **Protocol hints change how assistants treat tools.** Clients skip confirmation for read-only tools and prompt for everything else. Every tool now carries annotations and a title; four prompts expose the coaching flows as one-click commands.

- **The official archive names mentors.** `/api/archive/programs/{year}/projects/` lists every completed project with its mentors, code URL, and tags; the community archive we also use drops those fields. `mentors ORG` turns three archived years into a list of who mentors, who returns, and which repositories past work lives in.
- **Claims are commands, not prose.** Zulip, Rust, Kubernetes, pandas, Beam and others claim issues with `@zulipbot claim`, `@rustbot claim`, `/assign`, `.take` and similar, and bots release them after a week or two of silence. Availability now reads those commands and releases.
- **GitHub's advanced issue search ANDs repeated qualifiers.** Checked live: `org:a org:b` returns 0 results under `advanced_search=true` and `(org:a OR org:b)` returns the union. All multi-org searches now use grouped qualifiers.

## Ideas we rejected

- **Competition scores.** Sites that rank organizations by "competition level" could not show their evidence. We show slot history, mentor counts, and the ratio Google publishes (about one accepted project per twenty proposals in 2026) instead.
- **Generated wikis and whole-repository dumps.** Maintainers of OpenWrt and Scala publicly rejected AI-written wikis for inventing details, and packing a repository into a prompt costs more than it teaches. Orientation output contains facts and paths only.
- **Daily streaks.** Weekly notes with no penalty for a missed week match what mentors ask for; streak mechanics add guilt without adding evidence.
- **Counting pull requests as progress.** Hacktoberfest stopped counting them in 2026 because low-effort submissions became trivial to produce. Nothing here rewards volume.
- **Cloning repositories for symbol analysis.** The tree, timeline, and files endpoints already answer a beginner's questions; a local mode can come later if people ask.

## Evidence worth reading

- Turzo, Sultana, Bosu, "From First Patch to Long-Term Contributor" (2025): https://arxiv.org/pdf/2407.04159
- Tan, Zhou, Sun, "Is It Enough to Recommend Tasks to Newcomers?" (ICSE 2023): https://arxiv.org/pdf/2302.05058
- Hoshikawa et al., "A Longitudinal Analysis of Good First Issue Practices" (EASE 2026): https://arxiv.org/abs/2604.27532
- Xiao et al., "Recommending Good First Issues in GitHub OSS Projects" (ICSE 2022): https://hehao98.github.io/files/2022-recgfi.pdf
- Steinmacher, Pinto, Wiese, Gerosa, "Almost There" (ICSE 2018): https://www.ime.usp.br/~gerosa/papers/icse2018-Pinto.pdf
- Google, how organizations filter low-quality proposals: https://developers.google.com/open-source/gsoc/resources/spam_proposals
- Google, GSoC contributor guide, making first contact: https://google.github.io/gsocguides/student/making-first-contact
- Google, AI tooling guidance: https://developers.google.com/open-source/gsoc/resources/ai_guidance

## Projects and sources examined

Checked on 2026-10-20 and 2026-10-21 by reading source, documentation, issues, or live endpoints. "Status" records what could and could not be verified. Ideas only; no code was reused.

| Project or source | License | What it is | What we took | Status |
|---|---|---|---|---|
| [summerofcode.withgoogle.com API](https://summerofcode.withgoogle.com/api/program/2026/) | Google terms | The official site's own JSON: programs, organizations, archive of completed projects with mentors | Timeline, organizations, `mentors` | Verified live; 1,191 completed projects in the 2025 archive |
| [nishantwrp/gsoc-organizations](https://github.com/nishantwrp/gsoc-organizations) | GPL-3.0 | Community archive site and JSON API | Multi-year history and slot counts (JSON only) | Verified: hand-updated snapshot, days to weeks behind announcements, no mentor names |
| [github/github-mcp-server](https://github.com/github/github-mcp-server) | MIT | GitHub's official MCP server | Content sanitising by default, tool annotations, compact results | Verified from source |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | MIT (transitioning to Apache-2.0) | Reference servers | Annotation constants, `structured_output=False` for text results, `ToolError` with hints | Verified from source |
| [agentskills.io specification](https://agentskills.io/specification) | Apache-2.0 / CC-BY-4.0 | Agent Skills format | Frontmatter fields, `.agents/skills` convention | Verified |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | Apache-2.0 | Repository map for an editing assistant | Identifier weighting, special files first, token budgets | Verified from `aider/repomap.py`; not adopted as a dependency |
| [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless) | MIT | Issue localisation without agents | Full paths, at most a few, never a nested tree | Verified from source and the follow-up survey |
| [microsoft/codetour](https://github.com/microsoft/codetour) | MIT | Guided code tours in VS Code | Reading plan pinned to a commit | Verified; export not built yet |
| [yamadashy/repomix](https://github.com/yamadashy/repomix), [coderamp-labs/gitingest](https://github.com/coderamp-labs/gitingest) | MIT | Repository packers | Rejected: whole-repository dumps | Verified |
| DeepWiki ([deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open)) | MIT (open version) | Generated wikis | Citation discipline; rejected generated prose | Verified, including maintainer complaints on the OpenWrt and Scala forums |
| [idosal/git-mcp](https://github.com/idosal/git-mcp), [upstash/context7](https://github.com/upstash/context7) | Apache-2.0, MIT | Documentation retrieval servers | Fallback chains, cache hints; rejected unbounded fallbacks | Verified from source |
| [ossf/scorecard](https://github.com/ossf/scorecard) | Apache-2.0 | Security and maintenance checks | Reasons with counts; the Maintained rule | Verified; public API covers only scanned repositories |
| [CHAOSS metrics](https://chaoss.community/) | CC-BY | Community health definitions | Time to first response, acceptance ratio, absence factor | Verified |
| [ecosyste.ms](https://repos.ecosyste.ms/docs/api/v1/openapi.yaml) | AGPL-3.0 (services) | Open data about repositories, issues, commits | Candidate zero-token enrichment source | Verified; not adopted yet |
| [codetriage/codetriage](https://github.com/codetriage/codetriage) | MIT | One issue a day by email | The digest in `next` | Verified |
| [deepsourcelabs/good-first-issue](https://github.com/deepsourcelabs/good-first-issue), [up-for-grabs.net](https://github.com/up-for-grabs/up-for-grabs.net), [forgoodfirstissue](https://github.com/forgoodfirstissue/forgoodfirstissue.github.com) | MIT, NOASSERTION, GitHub | Label crawlers | Confirmed none checks availability | Verified from source |
| [osslab-pku/gfi-bot](https://github.com/osslab-pku/gfi-bot) | GPL-3.0 | Research recommender (RecGFI) | Feature ideas from the paper only | Verified on 2026-10-21: 57 stars, last push 2026-04 |
| [Outreachy](https://www.outreachy.org/docs/applicant/) | GPL-3.0 (site) | Internship applicant process | Recorded contributions, two-project cap | Verified from docs and models |
| [cncf/mentoring](https://github.com/cncf/mentoring) | Apache-2.0 | GSoC and LFX ideas in one template | Idea template vocabulary | Verified |
| [OWASP/Nest](https://github.com/OWASP/Nest) | MIT | Organization-side contributor platform | Assignment-before-PR enforcement exists; availability checks matter | Verified from source |
| GSoC proposal archives ([SammanSarkar/GSoC_archive_2025](https://github.com/SammanSarkar/GSoC_archive_2025) and others) | MIT (repositories) | Accepted proposals as PDFs | Section census only; never bundled (personal data) | Verified; 43 PDFs read |
| Sourcegraph Cody | n/a | Context engine | Nothing | Repository returns 404 as of 2026-10-21; product retired |
| ossrank.com | n/a | Ranking site | Nothing | Unreachable on 2026-10-21 |
| grep.app API | n/a | Code search | Nothing | Bot-gated (HTTP 429) on 2026-10-21 |
| r/GSoC | n/a | Community forum | Nothing | Blocked for automated reads (HTTP 403); advice came from blogs, mailing lists, and org retrospectives instead |

[Guide contents](README.md) · [Sources and limitations](sources.md)
