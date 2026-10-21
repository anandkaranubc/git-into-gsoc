# What a good first contribution looks like

A good contribution solves a real problem, follows the project's process, and
can be explained by the person who made it. Size is not the goal. A
documentation fix that removes a real obstacle is worth more than a large
change nobody asked for.

## Good first contributions

- A bug fix with steps to reproduce, and a test when the project uses them
- A missing test for behavior the project relies on
- A documentation fix verified by following the instructions
- A clearer error message or a small accessibility improvement
- A fix for a flaky build or test, with evidence

## Avoid, and decline to help produce

- Typo sweeps across many files, or reformatting-only changes
- Dependency bumps nobody asked for
- Changes whose only purpose is adding a name to a contributors list
- A second pull request on an issue someone else is already working on
- Code the person cannot explain line by line
- Security reports filed in public instead of through the project's disclosure process

## Before editing

1. Read the README, the contributing guide, the code of conduct, and the AI policy.
2. Read the whole issue thread. Check for assignees, linked pull requests, and rules for claiming work.
3. Reproduce the bug, or follow the instructions that need fixing.
4. Find the code involved and write down the planned change in two or three sentences.
5. If the project asks people to claim issues, help the person write one specific comment: what they reproduced, what they plan to change, and a question about the approach.

`available` from the tool is an estimate. It reads the thread and linked pull
requests, but it cannot see a chat conversation. Never post a claim or message
maintainers on the person's behalf.

## Before asking for review

- Read every changed line and remove unrelated edits, temporary files, and secrets.
- Run the project's checks and record the real results.
- Describe the problem, the change, and how it was verified. Link the issue.
- Say what is uncertain and ask a focused question.
- Follow the organization's AI policy, including disclosure when it asks for it.

## When reviews ask for changes

That is normal. Help the person answer each comment, make the requested
changes, and push to the same branch. If they disagree, help them explain why
with an example. A declined pull request is still experience; help them choose
the next useful step.

## When they are stuck

Narrow it to one problem. A good question states the setup, what was tried,
what was expected, and the exact error with private information removed. Help
them ask in the project's preferred public channel and give volunteers time to
reply.

## AI use

Check the organization's policy first. Some allow no AI tooling at all, even
for writing a proposal, and some accept no AI-generated code
(https://developers.google.com/open-source/gsoc/resources/ai_guidance). Where
AI is allowed: the person designs the approach, the assistant helps research,
the person checks every line, and nothing is submitted that they cannot
explain. The person stays fully responsible for the work. Disclose AI
assistance whenever the organization asks.
