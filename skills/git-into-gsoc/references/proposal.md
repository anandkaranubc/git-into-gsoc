# Reviewing a proposal

A proposal is a plan for a specific project: the problem, the approach, what
will be delivered, and how the weeks will be used. Start from the
organization's template, required questions, and AI policy. The tool's
checklist is a reminder, not a substitute:

```bash
git-into-gsoc proposal
```

It prints a checklist and a suggested structure. It does not save or submit
anything.

## Ground the proposal in evidence

Before drafting, collect the project idea, the person's real contributions and
discussions (with links), relevant code they have read, and the organization's
requested project size. `git-into-gsoc org "<name>"` lists recent accepted
project titles for a sense of scope, and `git-into-gsoc projects "<keywords>"`
searches past projects. Use them to calibrate, never to copy.

## Questions to ask about a draft

- Is the problem clear, and does the person understand how things work today?
- Does the approach explain tradeoffs, not just intentions?
- Can each milestone be demonstrated and tested?
- Does the schedule match the project size and the person's real availability, with time for learning, reviews, tests, and surprises?
- What would be cut first if time runs short?
- Are experience, contributions, and community conversations backed by links?
- Are all required sections present, including any AI disclosure the organization asks for?

Point out specific gaps. Help the person revise in their own words. Do not
invent experience, mentor conversations, or contribution links, and do not
make the proposal sound more impressive than the work behind it.

## Check the draft before anyone else reads it

```bash
git-into-gsoc proposal draft.md --github USER --ideas-file ideas.txt
```

Replace `USER` with the person's GitHub login and point `--ideas-file` at a
text copy of the organization's ideas page if they have one. The check reads
a Markdown or plain-text draft and reports pass, warn, and fail findings with
reasons: whether the required sections are present, whether linked pull
requests exist on GitHub and belong to the person, whether the timeline is
week by week with spare time, whether the text names real files, functions,
and issues, and whether it contains generic phrases, leftover template
placeholders, or long passages copied from the ideas page. `--no-verify`
skips the GitHub lookups. Over MCP the same check is `gsoc_proposal_check`
with the draft passed as `text`.

Help the person fix failures first, then warnings, in their own words. The
check never rewrites anything, and a clean result means the skeleton is
right, not that the plan is good.

## Common reasons proposals fail

- Generic praise with no detail specific to this project
- The same text sent to several organizations
- No prior interaction with the community or links to real work
- An unrealistic rewrite of a core system in a few weeks
- Missing required questions or sections
- Long prose with no design decisions

A writing style alone is not proof that AI wrote something. Judge the content:
specifics, evidence, and a realistic plan.

## Feedback and submission

1. Share a draft through the organization's requested channel when it accepts drafts.
2. Ask focused questions about the approach and the schedule.
3. Revise, then check every required section once more.
4. Submit on the [official GSoC site](https://summerofcode.withgoogle.com) before the deadline on the [official timeline](https://developers.google.com/open-source/gsoc/timeline), and confirm the submission is recorded.

Sending a document to a mentor is not an application. Only the official site
counts.

See [Google's proposal advice](https://google.github.io/gsocguides/student/writing-a-proposal.html)
and [official sources](official-sources.md).
