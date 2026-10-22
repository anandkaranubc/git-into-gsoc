# 5. Pick a repository and an issue

A GitHub **repository**, often shortened to **repo**, holds a project's files and history. An **issue** is a discussion about a bug, question, or requested change. A **pull request (PR)** proposes changes for maintainers to review. When maintainers accept a pull request they **merge** it (people also say it **lands**). A **commit** is one saved change in the project's history, and **continuous integration (CI)** is the set of automated tests that runs on each pull request.

## Which of the organization's repositories?

Many organizations own dozens of repositories, and only a few are where mentors spend their time.

```bash
git-into-gsoc repos "SymPy" --language python
```

The examples on this page use SymPy only to show what the commands print. Run them on your own shortlist, and see the note on SymPy in [step 4](04-find-organizations.md).

The table ranks the organization's active repositories. The strongest signal is whether the organization's GSoC ideas page names the repository. After that come open, unassigned beginner issues, recent pushes, stars, and whether the repository is written in your language. The caption tells you whether the ideas page could be read; some wikis block automated readers, in which case the ranking uses activity and beginner issues only. You can also pass a GitHub organization login directly, such as `repos sympy`.

## Will a newcomer's PR land here?

```bash
git-into-gsoc repo sympy/sympy
```

Expect a grade from A to F, the evidence behind it, and setup hints. The signals that matter most for you:

- **Merges outside contributors' PRs.** A project can have a high overall merge rate that is entirely core-team work. This signal looks only at PRs from people without write access. The tool reads who can be assigned issues in the repository (public, no token needed), so long-time contributors who are really maintainers are not counted as outsiders. Some projects never press GitHub's merge button: Go, for example, imports pull requests into its own review system and commits them there, so GitHub shows them as closed. The tool counts a closed outside pull request as landed when a later commit names it (a `GitHub-Pull-Request:` trailer, a `#123` reference, or a link) or credits its author as a co-author, and says how many it found.
- **Different outside authors merged recently.** Breadth of people without write access who got a PR in, which is direct proof that newcomers get through. The outside merge rate is only scored once at least ten outside PRs are in the sample; with fewer it is shown as evidence only. When it is scored, it also limits the grade: a repository that merged fewer than 40% of recent outside PRs gets at most a B, and fewer than 20% at most a C, however good everything else looks.
- **Time to a first human reply.** The median time until someone other than the author (and not a bot) comments on or reviews an outside PR. This is the number that predicts whether newcomers keep contributing, so it replaces time to merge in the grade when it rests on at least five PRs; time to merge is still shown. With a token it is read from each PR's timeline; without one it is derived from the repository's newest 200 comments, which covers the last few days on a busy project and months on a quiet one, so the output says how many PRs it is based on.
- **People who landed a single commit last year.** Counted from the repository's commit history by a community service, so it needs no token. Many single-commit authors means newcomers really do get through. A bus factor of one (one person behind more than half of the commits) is flagged as a warning.
- **Typical outside PR size.** The median lines changed in merged outside PRs, so you know how big a first PR usually is there.
- **Open beginner issues** under the repository's actual beginner label, which may be "good first issue", "beginner friendly", or something project-specific. The count is of issues nobody is assigned to yet; when every one is assigned, the tool says so.
- **CONTRIBUTING guide, Code of Conduct, issue and PR templates, CI.**
- **Recent pushes.** The pull request figures above come from the latest closed pull requests, however old they are. When nothing has been pushed for over a year, the tool says so first, marks each of those figures "Before it went quiet", and grades the repository D at best, because a new pull request there may get no reply.

### How the grade is worked out

Each signal adds points, and the points add up to exactly 100. A repository with every signal at its best scores 100, and each missing signal costs exactly its points, so two repositories that both show 100 really are equal.

| Signal | Most points | How the points are earned |
|---|---|---|
| Recent push | 16 | 16 within two weeks, 12 within 45 days, 6 within 120 days |
| CONTRIBUTING guide | 12 | Found in the repository |
| Outside merge rate | 12 | 12 at 40% or more, 6 at 20% or more, once ten outside PRs are sampled |
| Open beginner issues | 10 | 10 when one is free, 4 when the label has no open issues, 2 when every one is assigned |
| Time to a first human reply | 10 | 10 within a day, 6 within three days. With too few replies measured, time to merge: 10 within three days, 5 within ten |
| Merge rate of all human PRs | 8 | 8 at 50% or more, 4 at 25% or more |
| CI on pull requests | 8 | At least one workflow |
| Different outside authors merged | 6 | 2 for each, up to three |
| People who landed a single commit last year | 6 | 6 for ten or more, 3 for three or more |
| Code of Conduct | 4 | Found in the repository |
| Issue or PR templates | 4 | Either one found |
| License | 4 | Detected by GitHub |

The outside merge rate is worth more than the merge rate of all PRs, because most PRs in a busy project come from the core team. The grade follows the score: A from 85, B from 72, C from 58, D from 45, and F below that. Two rules can then hold it down, however many points the rest earns: the outside merge rate limits described above (a B or a C at best), and a year without a push (a D at best). An archived repository is an F.

A figure that rests on too few PRs is shown but scores nothing, since a handful of PRs is not evidence either way. The single-commit count comes from a community service (ecosyste.ms). When it has no commit history for the repository, the count is left out and the score is out of the other 94 points, because a gap in someone else's data says nothing about the project.

The advice under the grade follows the grade: "Strong candidate" for an A, "Promising, with caveats" for a B, "Risky" for a C or a D, and "Poor fit" for an F.

"Getting set up" lists the toolchain files found in the repository root, whether a dev container exists (one click in Codespaces or VS Code gets you a working environment), the CONTRIBUTING link, and the chat channels it mentions. Read the README and CONTRIBUTING on GitHub before writing code. A high grade does not guarantee mentoring, and a missing file can mean the guide lives elsewhere. If the repository is archived, look for the project's current repository before continuing.

```bash
git-into-gsoc repo sympy/sympy --track          # same check, and saves the repo to your progress
```

When you have one or two repositories you want to work in, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase evaluate
```

## Get your bearings in the repository

```bash
git-into-gsoc orient sympy/sympy
```

Before you look for an issue, spend one session learning how the project is put together. `orient` prints a code map with entry points, the command CI really runs for tests, who writes most of the code (commit authors and CODEOWNERS), and the rules you must follow before opening one (sign-offs, commit style, templates, AI disclosure), each with the file it came from. Then clone the repository, build it, run its test suite once, and read the files behind the feature you care about. When you can say where a change would go and how you would test it, mark the phase done:

```bash
git-into-gsoc progress complete_phase --phase orient
```

## Introduce yourself to the community

Before you claim an issue, say hello in the organization's public channel: the chat or mailing list that `org` lists. A short introduction that mentions something concrete you read or ran with `orient` makes your later comment on an issue land better, and the [official contributor guide](https://google.github.io/gsocguides/student/) asks for public contact first.

```bash
git-into-gsoc draft intro --org "SymPy"
```

`draft intro` and `draft question` give you a short, specific structure for a first message; fill it in with your own words. When you have written your message, `git-into-gsoc draft intro --check my-message.md` checks it before you post: placeholders you forgot to replace, phrases that read as machine-written, or a first message that is only a greeting. Read recent conversations to learn how the project talks and decides. When you ask for help, say what you tried, the exact error without private data, and the relevant versions. Ask in public rather than messaging maintainers privately, do not send the same request to several people, and give volunteers time to reply.

```bash
git-into-gsoc progress complete_phase --phase community
```

## Find an issue that is actually free

```bash
git-into-gsoc issues --repo sympy/sympy -n 5
git-into-gsoc issues --language python -n 10
```

Without `--repo` or `--org`, the search covers only repositories owned by GSoC organizations that use your language, and each result shows the organization it belongs to. Add `--scope all` to search every repository on GitHub. The search asks GitHub for open issues labelled "good first issue" or "help wanted" (with "good first issue" ranked first) that have no assignee, no linked PR, are not in archived repositories, and were updated in the last year. The top candidates are then verified against their timelines.

Each result has a status:

| Status | Meaning | What to do |
|---|---|---|
| `available` | Open, unassigned, no open PR, no recent claim | Read the thread, reproduce the problem, then comment with a plan |
| `claimed` | Someone asked to work on it and the claim was active in the last 30 days, a maintainer approved a claim that was active in the last 60 days, or a label marks it as taken. A claim stays active while its author keeps commenting or a maintainer checks in with them, so an approval from long ago no longer counts | Pick another issue; do not compete |
| `contested` | Three or more people asked in the last 60 days | Avoid; this is the GSoC-season trap |
| `likely_taken` | An open PR references the issue, or a comment points at an open PR that covers it | Choose another unless the PR is abandoned |
| `not_open` | A label such as "Idea for Discussion" or "on hold", or the project itself, says it is not taking claims yet, or the repository is archived (read-only) | Choose another; do not comment asking for it |
| `assigned` | GitHub shows an assignee | Choose another unless maintainers invite collaboration |
| `stale` | No activity for a year and no maintainer engagement | Ask whether it is still relevant before investing time |
| `closed` | Issue is closed | Look for another |
| `unknown` | The tool could not fetch the timeline | Open GitHub and check manually |

To see where to start reading for an issue, ask for pointers:

```bash
git-into-gsoc pointers sympy/sympy#12345
```

It lists the files the issue names, past fixes of similar issues and the files they touched, and how big a typical fix is. It never proposes a fix; it tells you where to look.

Before you comment, check one issue in depth:

```bash
git-into-gsoc issue sympy/sympy#12345
git-into-gsoc issue https://github.com/sympy/sympy/issues/12345
```

It lists linked PRs with their state and author, every claim with its age and whether a maintainer approved it, whether maintainers have engaged at all, and caveats such as "a merged PR references this issue; it may already be partly fixed". Below that is a short checklist to complete before you write anything in the thread. If an open pull request already references the issue but has been quiet for ninety days or more, it says so and suggests asking its author in the thread before you start. If an earlier pull request for the issue was closed without merging, it says so: read that pull request's review comments before you start, because they show what the maintainers expect.

Availability is an estimate from public data. The tool reads up to 100 timeline events, so very long threads may hide a claim. Read the discussion yourself before starting. Results are cached briefly; add `--output json` to see the full assessment.

## Choose one understandable task

Look for a clear problem, steps to reproduce it, and an explanation of the expected outcome. Documentation and tests are useful contributions too. Choose something small enough that you can explain the planned change.

Before commenting, read the project's assignment policy. If confirmation is needed, say what you tried and what you plan to do, in your own words:

```text
I reproduced this using [version and steps]. I think the relevant code is
[file or function], and I would like to [specific change]. Does that
approach fit, or is there a direction you would prefer?
```

Replace the brackets with real observations. Do not post the template unchanged, and never post a bare "can I work on this?". `git-into-gsoc draft claim --issue sympy/sympy#12345` prints a skeleton that already respects the repository's claim rules; fill it with what you found. If someone is already working on it, find another issue or ask whether they welcome help.

```bash
git-into-gsoc issue sympy/sympy#12345 --track   # same check, and saves the issue to your progress
```

When you have one issue you can reproduce and explain, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase find_issues
```

**Ready to move on:** you can explain the problem, have introduced yourself in the project's channel, have checked the discussion, and know the project's contribution process.

[Next: make your first contribution](06-first-contribution.md) · [Guide contents](../README.md)
