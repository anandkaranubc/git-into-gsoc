# 8. Keep track of your progress

A few notes help you remember what you learned and choose a next step. Start whenever useful; you do not need to finish the earlier steps first.

```bash
git-into-gsoc progress summary
```

The summary shows completed phases, saved organizations, repositories, and issues. On a fresh installation the phase count is `0/8`. It is a personal checklist, not an application status or a measure of readiness.

## Save something you want to revisit

These commands write to a file on your computer. Replace the example organization and repository with your own choices when appropriate:

```bash
git-into-gsoc progress shortlist_org --value "SymPy"
git-into-gsoc progress track_repo --value sympy/sympy
git-into-gsoc progress track_issue --value https://github.com/sympy/sympy/issues/12345
git-into-gsoc progress note --value "Read the setup guide. Next: run the project locally."
git-into-gsoc progress complete_phase --phase learn
```

The tool saves the text you provide; it does not assign the issue to you. Re-run `git-into-gsoc issue <link>` before you start work on a tracked issue, because availability changes daily during GSoC season.

Valid phase names are `learn`, `discover`, `evaluate`, `community`, `find_issues`, `contribute`, `proposal`, and `track`; the [journey map](../journey.md) shows which commands and guide page belong to each. Mark one complete only when its goal is useful and satisfied for you. You can revisit any phase.

## Keep a weekly note

```text
This week's goal:
What I tried or finished:
Links to work and discussions:
What I learned:
Where I am stuck:
My next small step:
```

`progress note` prints the saved state, including notes. `progress summary` does not include note text. To read all notes later, open `progress.json` in the data directory shown by `doctor`. See [local data](../configuration.md) for backup and editing instructions.

There is no CLI command to remove an entry or undo a completed phase. The store is local, does not sync between computers, and does not send updates to mentors. Share a useful update yourself through the community's preferred channel.

If accepted, agree on a reporting schedule with your mentor. If you are not selected, you can still keep contributing, learn from feedback, or explore another project.

[Return to the guide](../README.md) · [Command reference](../cli.md)
