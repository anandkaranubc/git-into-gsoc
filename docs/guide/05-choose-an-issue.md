# 5. Pick a repository and an issue

A GitHub **repository**, often shortened to **repo**, holds a project's files and history. An **issue** is a discussion about a bug, question, or requested change. A **pull request (PR)** proposes changes for maintainers to review.

## Which of the organization's repositories?

Many organizations own dozens of repositories, and only a few are where mentors spend their time.

```bash
git-into-gsoc repos "SymPy" --language python
```

The table ranks the organization's active repositories. The strongest signal is whether the organization's GSoC ideas page names the repository. After that come open, unassigned beginner issues, recent pushes, stars, and whether the repository is written in your language. The caption tells you whether the ideas page could be read; some wikis block automated readers, in which case the ranking uses activity and beginner issues only. You can also pass a GitHub organization login directly, such as `repos sympy`.

## Will a newcomer's PR land here?

```bash
git-into-gsoc repo sympy/sympy
```

Expect a grade from A to F, the evidence behind it, and setup hints. The signals that matter most for you:

- **Merges outside contributors' PRs.** A project can have a high overall merge rate that is entirely core-team work. This signal looks only at PRs from people without write access.
- **Different outside authors merged recently.** Breadth of people without write access who got a PR in, which is direct proof that newcomers get through. The outside merge rate is only scored once at least ten outside PRs are in the sample; with fewer it is shown as evidence only.
- **Time to merge.** The median time from opening to merging among merged human PRs. It says nothing about PRs that were never merged, so read it together with the outside merge rate.
- **Open beginner issues** under the repository's actual beginner label, which may be "good first issue", "beginner friendly", or something project-specific.
- **CONTRIBUTING guide, Code of Conduct, issue and PR templates, CI.**

"Getting set up" lists the toolchain files found in the repository root, whether a dev container exists (one click in Codespaces or VS Code gets you a working environment), the CONTRIBUTING link, and the chat channels it mentions. Read the README and CONTRIBUTING on GitHub before writing code. A high grade does not guarantee mentoring, and a missing file can mean the guide lives elsewhere. If the repository is archived, look for the project's current repository before continuing.

```bash
git-into-gsoc repo sympy/sympy --track          # same check, and saves the repo to your progress
```

## Find an issue that is actually free

```bash
git-into-gsoc issues --repo sympy/sympy -n 5
git-into-gsoc issues --language python -n 10
```

Without `--repo` or `--org`, the search covers only repositories owned by GSoC organizations that use your language, and each result shows the organization it belongs to. Add `--scope all` to search every repository on GitHub. The search asks GitHub for open issues labelled "good first issue" (falling back to "help wanted" when results are thin) that have no assignee, no linked PR, are not in archived repositories, and were updated in the last year. The top candidates are then verified against their timelines.

Each result has a status:

| Status | Meaning | What to do |
|---|---|---|
| `available` | Open, unassigned, no open PR, no recent claim | Read the thread, reproduce the problem, then comment with a plan |
| `claimed` | Someone asked to work on it in the last 30 days, or a maintainer approved them | Pick another issue; do not compete |
| `contested` | Three or more people asked in the last 60 days | Avoid; this is the GSoC-season trap |
| `likely_taken` | An open PR references the issue | Choose another unless the PR is abandoned |
| `assigned` | GitHub shows an assignee | Choose another unless maintainers invite collaboration |
| `stale` | No activity for a year and no maintainer engagement | Ask whether it is still relevant before investing time |
| `closed` | Issue is closed | Look for another |
| `unknown` | The tool could not fetch the timeline | Open GitHub and check manually |

Before you comment, check one issue in depth:

```bash
git-into-gsoc issue sympy/sympy#12345
git-into-gsoc issue https://github.com/sympy/sympy/issues/12345
```

It lists linked PRs with their state and author, every claim with its age and whether a maintainer approved it, whether maintainers have engaged at all, and caveats such as "a merged PR references this issue; it may already be partly fixed". Below that is a short checklist to complete before you write anything in the thread.

Availability is an estimate from public data. The tool reads up to 100 timeline events, so very long threads may hide a claim. Read the discussion yourself before starting. Results are cached briefly; add `--output json` to see the full assessment.

## Choose one understandable task

Look for a clear problem, steps to reproduce it, and an explanation of the expected outcome. Documentation and tests are useful contributions too. Choose something small enough that you can explain the planned change.

Before commenting, read the project's assignment policy. If confirmation is needed, say what you tried and what you plan to do, in your own words:

```text
I reproduced this using [version and steps]. I think the relevant code is
[file or function], and I would like to [specific change]. Does that
approach fit, or is there a direction you would prefer?
```

Replace the brackets with real observations. Do not post the template unchanged, and never post a bare "can I work on this?". If someone is already working on it, find another issue or ask whether they welcome help.

```bash
git-into-gsoc issue sympy/sympy#12345 --track   # same check, and saves the issue to your progress
```

**Ready to move on:** you can explain the problem, have checked the discussion, and know the project's contribution process.

[Next: make your first contribution](06-first-contribution.md) · [Guide contents](../README.md)
