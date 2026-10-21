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

## Projects studied

GitHub MCP server (MIT) for content sanitising and tool annotations; the Agentless project (MIT) for path discipline; CodeTour (MIT) for the idea of a reading plan pinned to a commit; CodeTriage (MIT) for the one-issue-at-a-time digest that became part of `next`; Outreachy's applicant process for the recorded-contribution ledger behind `contributions`; the GSoC Organizations archive (GPL-3.0, data consumed as JSON only) for its organization schema; OpenSSF Scorecard (Apache-2.0) for explainable "reason with counts" output; CHAOSS metric definitions for the vocabulary of responsiveness. Ideas only; no code was reused.

[Guide contents](README.md) · [Sources and limitations](sources.md)
