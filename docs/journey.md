# Journey map

The [beginner guide](README.md) explains each step. This page is the one-screen version: every phase the tool tracks, what you leave it with, and the commands and guide page that belong to it.

```text
learn → discover → evaluate → orient → community → find_issues → contribute → iterate → proposal → track
```

The order is a default, not a rule. You can loop (more issues after the first PR), and notes fit anywhere.

| Phase | You leave with | Commands | Guide |
|---|---|---|---|
| `learn` | You can explain GSoC and your own constraints | `start`, `program`, `journey` | [Understand GSoC](guide/01-understand-gsoc.md) |
| `discover` | Two or three organizations with a reason for each | `orgs`, `org`, `ideas`, `mentors`, `projects`, `recommend` | [Find organizations](guide/04-find-organizations.md) |
| `evaluate` | One or two repositories that merge newcomers' work | `repos`, `repo` | [Pick a repository and an issue](guide/05-choose-an-issue.md) |
| `orient` | You know where a change would go and how you would test it | `orient` | [Get your bearings](guide/05-choose-an-issue.md#get-your-bearings-in-the-repository) |
| `community` | You have introduced yourself in the organization's public channel | `org` (channels), `draft intro` | [Introduce yourself](guide/05-choose-an-issue.md#introduce-yourself-to-the-community) |
| `find_issues` | One free, well-specified issue you can reproduce | `issues`, `issue`, `pointers`, `draft claim` | [Find a free issue](guide/05-choose-an-issue.md#find-an-issue-that-is-actually-free) |
| `contribute` | A reviewed pull request you can explain | `draft pr`, `pr-check` | [First contribution](guide/06-first-contribution.md) |
| `iterate` | Reviewers know you finish what you start | `draft review-reply`, `next` | [See it through review](guide/06-first-contribution.md#see-it-through-review) |
| `proposal` | An original draft in the organization's template | `proposal`, `contributions`, `program` | [Prepare a proposal](guide/07-prepare-a-proposal.md) |
| `track` | A weekly note habit | `log`, `progress`, `next` | [Track progress](guide/08-track-progress.md) |

Mark a phase done with `git-into-gsoc progress complete_phase --phase discover` (or any other phase name from the table). Two orderings are deliberate. Orient comes before community, so your introduction can mention something concrete you read or ran. Community comes before claiming an issue, because the [official contributor guide](https://google.github.io/gsocguides/student/), [Outreachy](https://www.outreachy.org/docs/applicant/) (another paid open-source internship program), and [Google's guidance on low-quality proposals](https://developers.google.com/open-source/gsoc/resources/spam_proposals) all say to make public contact first, and a short introduction makes your later comment on an issue land better.
