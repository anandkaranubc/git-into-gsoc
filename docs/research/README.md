# Research notes

This folder holds the raw notes from the research behind git-into-gsoc. They record what was tested, the numbers that came back, and where every fact came from, so later decisions can be checked against the evidence.

**You do not need anything in this folder to use the tool or to prepare for GSoC.** If you are getting started, go to the [beginner guide](../README.md) instead. If you want to know why the tool works the way it does, read the [research summary](../research.md), which states the conclusions in plain language.

## Who these notes are for

- People improving git-into-gsoc who want the evidence behind a design choice.
- Anyone checking a claim the summary makes. Every number here has a link to its source.

The notes were written quickly while the research was happening, so they use more technical words than the rest of the docs. The glossary at the end of this page explains the ones that come up most.

## The notes

| Note | What it covers |
|---|---|
| [GSoC tools](gsoc-tools.md) | The official GSoC site's data, organizations' ideas pages, accepted proposals, and what organizations look for in applicants |
| [Beginner-issue finders](issue-finders.md) | Existing websites that list beginner issues, how projects let people claim an issue, and which labels projects use |
| [Repository health](repo-health.md) | Which signals predict that a newcomer's pull request gets merged, and how to measure them cheaply |
| [Codebase onboarding](codebase-onboarding.md) | Tools that help someone understand an unfamiliar codebase, and what `orient` and `pointers` borrowed from them |
| [MCP and Agent Skills](mcp-and-skills.md) | How the best assistant integrations are built and published, and how to handle text written by strangers safely |
| [Onboarding science](onboarding-science.md) | Published studies on why newcomers succeed or give up, and what maintainers say they want |
| [Search census](census-2026-10-21.md) | Every repository the searches turned up, all 292 of them, each with a one-line verdict |

Items marked **unverified** in the notes could not be confirmed from a primary source and were not used to make decisions.

## Glossary

**API.** A way for one program to ask another for data. The tool reads GitHub's API and the GSoC site's API instead of scraping web pages.

**REST and GraphQL.** Two styles of API that GitHub offers. With REST, each request returns one kind of thing, such as a list of pull requests. With GraphQL, one request can ask for several related things at once. The notes compare how many requests each style needs.

**Endpoint.** One specific address in an API, such as the one that returns a repository's issues.

**Token.** A private password-like string that proves who you are to GitHub. With one, GitHub allows many more requests per hour. A token is optional; see [configuration](../configuration.md).

**Rate limit.** The maximum number of requests GitHub allows in a period of time. Search has its own, lower limit.

**PR (pull request).** A proposed change to a repository, waiting for maintainers to review it and merge it in.

**CI (continuous integration).** Automated checks, usually tests, that run every time someone pushes a change.

**Label.** A tag on an issue, such as `good first issue`. Projects spell beginner labels in many different ways, which the notes count.

**Claim.** Saying in an issue that you will work on it. Some projects use a bot command such as `/assign`, and the bot releases the claim if nothing happens for a while.

**Timeline.** GitHub's record of everything that happened to an issue: comments, labels, assignments, and pull requests that mention it.

**`author_association`.** A field GitHub attaches to every pull request saying how the author relates to the repository, for example a member or a first-time contributor. The notes show where it is misleading.

**Archive.** Records of past GSoC years. The official site publishes completed projects with mentor names; a separate community site publishes organizations and project counts.

**Ideas page.** The page where each organization lists the projects it would like contributors to propose.

**Schema.** The exact shape of some data: which fields it has and what type each one is.

**MCP (Model Context Protocol).** The standard way an AI assistant calls outside tools. git-into-gsoc includes an MCP server; see the [MCP reference](../mcp.md).

**Agent Skill.** A folder of written instructions an AI assistant loads to learn a task. git-into-gsoc ships one in `skills/git-into-gsoc/`.

**Plugin and registry.** Two ways to share an assistant integration: a plugin installs from a repository, and a registry is a public catalog that assistants can search.

**PyPI and wheel.** PyPI is the public catalog of Python packages. A wheel is Python's ready-to-install package file.

**Prompt injection.** Text hidden in an issue or web page that tries to give instructions to an AI assistant reading it. The notes explain how the tool cleans such text before showing it.

**Bus factor.** How many people would have to leave before a project stalls. A bus factor of one means a single person does most of the work.

**CHAOSS and OpenSSF Scorecard.** Two community projects that define ways to measure the health of open source projects. The notes reuse some of their definitions.

**Heuristic.** A rule of thumb that is usually right but not always, such as treating a pull request merged within seconds of an issue closing as the fix for that issue.

**Cron.** A schedule that runs a job automatically, for example once a day.

**Census and verdict.** The census lists every repository the searches found; the verdict is the one-line judgment written for each one.

[Research summary](../research.md) · [Beginner guide](../README.md)
