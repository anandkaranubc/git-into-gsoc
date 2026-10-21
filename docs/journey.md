# Contributor journey

The full journey lives in the [beginner guide](README.md). Start there for explanations, commands, expected results, and next steps.

```text
learn → discover → evaluate → orient → community → find_issues → contribute → iterate → proposal → track
```

You can loop (for example more issues after the first PR). Order is a default, not a rule.

| Phase | Useful outcome | Commands | Guide |
|---|---|---|---|
| `learn` | You can explain GSoC and your constraints | `start`, `program`, `journey` | [Understand GSoC](guide/01-understand-gsoc.md) |
| `discover` | A shortlist of two or three organizations with reasons | `orgs`, `org`, `ideas`, `mentors`, `projects`, `recommend` | [Find organizations](guide/04-find-organizations.md) |
| `evaluate` | 1 or 2 repositories that merge newcomers' work | `repos`, `repo` | [Pick a repository and an issue](guide/05-choose-an-issue.md) |
| `orient` | You know where a change would go and how you would test it | `orient` | [Get your bearings](guide/05-choose-an-issue.md#get-your-bearings-in-the-repository) |
| `community` | You have introduced yourself in the organization's public channel and read how it works | `org` (channels), `draft intro` | [Introduce yourself](guide/05-choose-an-issue.md#introduce-yourself-to-the-community) |
| `find_issues` | One available, well-specified issue you can reproduce | `issues`, `issue`, `pointers`, `draft claim` | [Pick a repository and an issue](guide/05-choose-an-issue.md) |
| `contribute` | A meaningful, reviewed PR you can explain | `draft pr`, `pr-check` | [First contribution](guide/06-first-contribution.md) |
| `iterate` | Reviewers know you finish what you start | `draft review-reply`, `next` | [See it through review](guide/06-first-contribution.md#see-it-through-review) |
| `proposal` | An original draft aligned to the organization's template | `proposal`, `contributions`, `program` | [Prepare a proposal](guide/07-prepare-a-proposal.md) |
| `track` | A weekly log habit | `log`, `progress`, `next` | [Track progress](guide/08-track-progress.md) |

Mark a phase done with `git-into-gsoc progress complete_phase --phase discover`. Orient comes before community so your introduction can mention something concrete you read or ran. Community comes before claiming an issue on purpose: the [official contributor guide](https://google.github.io/gsocguides/student/), [Outreachy](https://www.outreachy.org/docs/applicant/) (another paid open-source internship program), and [Google's guidance on low-quality proposals](https://developers.google.com/open-source/gsoc/resources/spam_proposals) all say to make public contact first, and a short introduction in the organization's channel makes your later comment on an issue land better. Note-taking can start at any point.
