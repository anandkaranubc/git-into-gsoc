# Coaching examples

Patterns, not scripts. Adapt them to the person and report what the tools
actually returned.

## "I know a little Python and want to try GSoC"

Explain GSoC in two sentences and link the FAQ. Ask what they enjoy. Then run
one search:

```bash
git-into-gsoc orgs --tech python --topics <their interest> -n 5
```

Say that the list shows the latest announced year and that next year's
organizations are not confirmed. Suggest one next step: open one
organization's ideas page with `git-into-gsoc org "<name>"` and read it. Do
not list every command.

## "Which repository should I start in?"

Rank the organization's repositories, then check the best one:

```bash
git-into-gsoc repos "<organization>"
git-into-gsoc repo owner/name
```

Point out the setup hints and the contributing guide link. If outside
contributors' pull requests rarely get merged, say so and suggest comparing
another repository in the same organization.

## "Find me an issue and open the PR for me"

Find candidates, then check the one they like:

```bash
git-into-gsoc issues --repo owner/name -n 5
git-into-gsoc issue owner/name#123
```

Walk through the status, linked pull requests, and claims. Help them reproduce
the problem and describe their approach in their own words before anyone
comments. Decline to write the whole change for them; offer to review their
plan or their diff instead.

## "The repository got a D"

Read the warnings together. A missing contributing guide may live on a
website, and slow reviews in a sample of recent pull requests may not reflect
how a small documentation fix would be treated. Suggest an alternative only
when the evidence is clear: archived, no activity for months, or outside pull
requests never merged. Describe the project, not the people.

## "Review my proposal"

Ask for the organization's template and AI policy if you do not have them.
Run `git-into-gsoc proposal` and compare the draft against the organization's
requirements. Name specific gaps: a milestone that cannot be demonstrated, a
claim without a link, a schedule that ignores their availability. Do not
rewrite it in a different voice, and do not add experience they do not have.

## "I have no merged PR yet and the deadline is close"

Check the organization's actual prerequisites. Reviewed pull requests,
reproduced bugs, documentation fixes, and helpful discussion all count as
evidence of engagement. Help them write about what they did and learned. Do
not promise that any number of pull requests leads to acceptance.
