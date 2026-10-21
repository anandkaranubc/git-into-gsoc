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
- **GitHub's advanced issue search treats repeated qualifiers as AND.** Checked live: `org:a org:b` returns 0 results under `advanced_search=true` and `(org:a OR org:b)` returns the union. All multi-org searches now use grouped qualifiers.

## Ideas we rejected

- **Competition scores.** Sites that rank organizations by "competition level" could not show their evidence. We show slot history, mentor counts, and the ratio Google publishes (about one accepted project per twenty proposals in 2026) instead.
- **Generated wikis and whole-repository dumps.** Maintainers of OpenWrt and Scala publicly rejected AI-written wikis for inventing details, and packing a repository into a prompt costs more than it teaches. Orientation output contains facts and paths only.
- **Daily streaks.** Weekly notes with no penalty for a missed week match what mentors ask for; streak mechanics add guilt without adding evidence.
- **Counting pull requests as progress.** Hacktoberfest stopped counting them in 2026 because low-effort submissions became trivial to produce. Nothing here rewards volume.
- **Cloning repositories for symbol analysis.** The tree, timeline, and files endpoints already answer a beginner's questions; a local mode can come later if people ask.

## Findings by stream, checked

Each stream's report was long; these are the facts that shaped decisions, with the ones re-checked directly by the maintainer session marked "re-checked".

**GSoC tools and data.** The official site's own JSON covers programs, organizations and an archive of completed projects with mentor names, code URLs and tags (re-checked: 1,191 completed projects for 2025). The community archive mirrors it by hand with a lag of days to weeks and without mentors. Of 183 GSoC 2026 ideas pages, 168 fetched; a heading-plus-label parser extracts clean blocks from about a third (re-checked live on MDAnalysis, KDE, CNCF, PSF, Dart, OpenStreetMap). 75 pages carry an AI-use policy sentence. No GSoC-specific command-line tool, bot, MCP server or Agent Skill exists on GitHub: searches for "gsoc mcp", "summer of code mcp server" and "gsoc skill" on 2026-10-21 return only this project and one unrelated application repository (re-checked).

**Beginner-issue finders.** Every shipping finder is a cron-fed label crawl with no availability check; several are dead or pivoted (goodfirstissues.com, contribute.dev, Quine, gfibot.io). Claims in large organizations are bot commands with expiry (`@zulipbot claim`, `/assign`, `.take`, pandas `/take` with a seven-day release). GitHub's advanced issue search treats repeated qualifiers as AND (re-checked: repeated `org:` returns 0, `(org:a OR org:b)` returns 120). 48 organization repositories use 38 spellings of "good first issue" plus difficulty, effort and size ladders.

**Repository health.** `author_association` is evaluated at query time, so a merged author becomes CONTRIBUTOR and "first-time contributors merged" was zero by construction (re-checked on sympy: 23 CONTRIBUTOR plus 8 MEMBER among merged, zero first-timers). Time to first human response explains most of a pull request's lifetime; stars reduce acceptance odds. CLA and DCO requirements are detectable from check names (`cla/google`, `EasyCLA`, `DCO`) and commit trailers. ecosyste.ms offers a generous zero-token data source but no response-time data.

**Codebase onboarding.** No existing tool addresses "I picked a repository, now what?"; packers dump everything and generated wikis draw public complaints from maintainers. One recursive tree call, one timeline call and one pull-request-files call are enough to find what a fix touched (re-checked on matplotlib: five of six similar closed issues had a traceable fix pull request, all touching tests). Full paths beat trees for avoiding invented files.

**MCP and Agent Skills.** The server spoke the current protocol but used none of it: no annotations or titles, every response sent twice through a wrapped output schema, errors as result JSON. Clients skip confirmation for read-only tools. Local stdio servers are distributed as plugins; the skill format allows `license`, `compatibility` and `metadata` fields. Untrusted text should be cleaned of hidden Unicode and structurally separated from server output. (All re-checked over stdio after the changes: 22 tools with titles and annotations, four prompts, four resources, errors flagged.)

**Onboarding science.** Prior engagement is what organizations score; about one proposal in twenty succeeds. First patches land when they are small bug fixes with tests and the author answers review promptly. "Unclear how to start" and "no response" are the top newcomer barriers. Community contact belongs before claiming an issue, which is now the order of the journey. Weekly notes with no streak mechanics match what organizations ask for.

## Full research notes

The complete notes behind this page, one file per stream, with every URL, number, and probe result, live in [docs/research/](research/). They are working notes rather than a guide:

- [GSoC tools](research/gsoc-tools.md): GSoC tools, the official site's API, ideas pages, proposal archives, and what organizations score.
- [Beginner-issue finders](research/issue-finders.md): Beginner-issue finders, claim conventions, label taxonomies, and newcomer-issue research.
- [Repository health metrics](research/repo-health.md): Repository health metrics, GraphQL costs, ecosyste.ms, and what predicts a merged newcomer pull request.
- [Codebase understanding and onboarding tools](research/codebase-onboarding.md): Codebase understanding and onboarding tools, and the GitHub API toolbox behind orient and pointers.
- [MCP servers](research/mcp-and-skills.md): MCP servers, the Agent Skills specification, distribution channels, and untrusted-content handling.
- [The research on newcomer onboarding](research/onboarding-science.md): The research on newcomer onboarding, what maintainers say they want, and adjacent programs.

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
| Smaller label crawlers ([cutenode/good-first-issue](https://github.com/cutenode/good-first-issue), [EddieHubCommunity/good-first-issue-finder](https://github.com/EddieHubCommunity/good-first-issue-finder), [arshadkazmi42/first-issues](https://github.com/arshadkazmi42/first-issues), [ohbarye/goofi](https://github.com/ohbarye/goofi), [yankeexe/good-first-issues](https://github.com/yankeexe/good-first-issues), [youzi-forge/good-first-issue-autoUpdate](https://github.com/youzi-forge/good-first-issue-autoUpdate)) | MIT and similar | Command-line and web label searches | Rolling date windows to beat the 1,000-result cap; showing license and code of conduct next to each issue | Verified from GitHub search on 2026-10-21; none checks availability |
| Sourcegraph Cody | Apache-2.0 (snapshot) | Context engine | Nothing | Verified on 2026-10-21: the code now lives in the archived `sourcegraph/cody-public-snapshot`; the product is retired |
| ossrank.com | n/a | Ranking site | Nothing | Domain resolves but the site refused connections over HTTP and HTTPS on 2026-10-21; treated as offline |
| grep.app API | n/a | Code search | Nothing | Bot-gated (HTTP 429 with and without browser headers) on 2026-10-21 |
| r/GSoC | n/a | Community forum | Nothing | The default feed is readable (two newest posts), but the top and search feeds are rate-limited for automated readers; advice came from blogs, mailing lists, and organization retrospectives instead |

[Guide contents](README.md) · [Sources and limitations](sources.md)
