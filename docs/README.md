# Your path to a first contribution

This guide takes you from "what is GSoC?" to a reviewed pull request and a proposal, one step at a time. You do not need to understand everything on day one. If you already know a topic, skip ahead.

| Step | You leave with |
|---|---|
| [1. Understand GSoC](guide/01-understand-gsoc.md) | The basics, where the official rules are, and a note on what you know and want |
| [2. Install the tool](guide/02-install.md) | A working `git-into-gsoc` command |
| [3. Connect your AI assistant (optional)](guide/03-connect-your-ai-assistant.md) | An assistant that uses the same live data |
| [4. Find organizations](guide/04-find-organizations.md) | Two or three communities you want to learn about, with a reason for each |
| [5. Pick a repository and an issue](guide/05-choose-an-issue.md) | One task you understand and can reproduce |
| [6. Make your first contribution](guide/06-first-contribution.md) | A pull request you can explain |
| [7. Prepare your proposal](guide/07-prepare-a-proposal.md) | A plan built on real work and feedback |
| [8. Keep track of your progress](guide/08-track-progress.md) | A weekly note and a clear next step |

The steps are a guide, not a checklist to pass. Loop back whenever you need to.

## Not sure what to do next?

`git-into-gsoc` on its own shows your progress. `git-into-gsoc next` reads the program calendar, your profile, and the issues you track, and prints the next few actions with the exact commands. The [journey map](journey.md) shows every phase with its commands and guide page.

## Just trying the tool?

[Install it](guide/02-install.md), run `git-into-gsoc start`, then jump to [find organizations](guide/04-find-organizations.md). You can do the whole journey in a terminal, without an AI assistant.

## Reference

- [Command reference](cli.md): every command and option.
- [MCP reference](mcp.md): the tools your AI assistant gets.
- [Use it in your AI assistant](assistants.md): install, update, and remove the plugin for each assistant.
- [Configuration and local data](configuration.md): the GitHub token, settings, the cache, and your progress file.
- [Troubleshooting](troubleshooting.md): common errors, by symptom.
- [Sources and limitations](sources.md): where results come from and what they cannot tell you.
- [How recommendations work](recommendations.md): how fit is decided, the evidence behind it, and how well it works.
- [Privacy](privacy.md): what the tool reads, what it saves, and what it never sends.
- [Examples](../examples/README.md): a sample terminal session and prompts for an assistant.

## Improving git-into-gsoc itself

These pages are for people changing the tool, not using it.

- [Contributing](../CONTRIBUTING.md): setup, your first change, and our standards.
- [Watch someone try it](watch-someone-try-it.md): a 30-minute session with a newcomer. It needs no code, and it is the most useful test we have.
- [Architecture](architecture.md): how the terminal tool, the assistant server, and the skill share one core, and how to add things.
- [Releasing](releasing.md) and [distribution](distribution.md): how releases, plugins, and directory listings work.
- [What we learned from other tools](research.md): ideas adopted and rejected, with sources.
- [Ranking benchmarks](../evals/README.md) and the [brand kit](../brand/README.md).

[Back to the project README](../README.md)
