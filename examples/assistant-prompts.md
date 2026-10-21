# Prompts for your AI assistant

Paste these into an assistant that has the git-into-gsoc skill or MCP server connected (see [connect your AI assistant](../docs/guide/03-connect-your-ai-assistant.md)). Replace the parts in angle brackets. Good prompts give the assistant real facts about you and ask for one step at a time.

## Your first question

Ask in your own words. The assistant asks what it needs to know.

```text
I want to do Google Summer of Code. I know Python and like science. Where do I start?
```

The server's `get_started` prompt does the same with a few questions. In Claude Code it is in the `/` menu as `/mcp__git-into-gsoc__get_started`.

## Check that the tools work

```text
Use the git-into-gsoc skill. Call gsoc_journey_guide for the "learn" phase and
explain my next step in plain words. If the tool is not available, tell me.
```

## Start from what you know

```text
I want to prepare for GSoC 2027. I know <languages or tools>, I care about
<topics>, and I can spend about <hours> hours a week. I have never contributed
to open source. Explain the program in a few sentences and give me one first
step. Do not list every command.
```

## Find organizations

```text
Using git-into-gsoc, find five organizations that use <language> and work on
<topic>. For each one, tell me why it matches and whether it took part last
year. Remind me which year's list this is based on.
```

## Choose a repository

```text
Using git-into-gsoc, rank <organization>'s repositories for a first
contribution, then evaluate the top one. Tell me what the grade is based on,
whether outside contributors' pull requests get merged, and how to set the
project up.
```

## Find an issue the right way

```text
Using git-into-gsoc, find open beginner issues in <owner/repo>. Skip anything
claimed, contested, or linked to a pull request. For your top pick, show me the
issue check, tell me what to read before commenting, and help me write a
comment in my own words after I have reproduced the problem.
```

## Plan a contribution without having it written for you

```text
I reproduced <owner/repo#123>. Here is what I found: <notes>. Help me outline
the change in my own words and list the project's checks I should run. Review
my plan; do not write the code for me.
```

## Review a proposal

```text
Here is the organization's proposal template and AI policy: <paste or link>.
Here is my draft: <paste>. Compare it with the git-into-gsoc proposal checklist
and the template. Point out unsupported claims, milestones I cannot demonstrate,
and schedule problems. Keep my voice; suggest edits rather than rewriting.
```

## Check a draft before sharing it

```text
Run gsoc_proposal_check on the draft below with my GitHub login <username>.
Explain each fail and warn finding in plain words and tell me what to change.
Do not rewrite the draft for me.

<paste your draft>
```

## Keep track

```text
Save <organization> to my shortlist and add the note "<what I learned and my
next step>". Then show my progress summary.
```
