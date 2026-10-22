# 6. Make your first contribution

Your goal is one useful change that you understand. Fixing a confusing instruction can be as valuable as fixing a bug. If you want to improve git-into-gsoc itself, use [this repository's contributor guide](../../CONTRIBUTING.md).

## Set up the project

Start from the "Getting set up" section of `git-into-gsoc repo owner/name`: it lists the toolchain files in the repository, whether a dev container exists, and the CONTRIBUTING link. If there is a dev container, opening the repository in GitHub Codespaces or VS Code gives you a working environment with no local setup. Otherwise follow the project's README and contribution guide. First get the unchanged project running; this helps distinguish setup problems from problems caused by your change.

Many GitHub projects use this workflow:

1. **Fork** the repository on GitHub to create a copy under your account.
2. **Clone** your fork to download it to your computer.
3. Create a **branch**, a separate line of work for your change.
4. Make the change and run the project's checks.
5. **Commit** the change to save a named checkpoint, then **push** it to your fork.
6. Open a **pull request** from your branch to the original project.

GitHub's [fork tutorial](https://docs.github.com/en/get-started/quickstart/fork-a-repo) walks through the first steps. The project's own workflow takes priority.

This is a command template, not something to paste unchanged. Replace `YOUR_USERNAME` and `PROJECT` with your fork's owner and name:

```text
git clone https://github.com/YOUR_USERNAME/PROJECT.git
cd PROJECT
git switch -c fix/describe-the-problem
```

## Make and check a focused change

Reproduce the problem before editing. For a bug, record expected and actual behavior. For documentation, try the instructions as written. Then change only what is needed to solve that problem.

Run the relevant tests and checks listed by the project. If a test already failed before your change, note that separately. Review your own work:

```bash
git diff
git status --short
```

Read every changed line. Leave out temporary files, credentials, unrelated formatting, and changes you cannot explain. If AI assistance is allowed, verify its suggestions just as carefully as your own. You must be able to walk a reviewer through every line.

## Ask for review

`git-into-gsoc draft pr --repo sympy/sympy --issue sympy/sympy#12345` prints a skeleton that follows the repository's pull request rules (template, sign-off, commit style). A useful pull request description answers:

```text
Problem: What was confusing or broken? Link the issue if there is one.
Change: What did you change, and why?
Validation: What commands or manual checks did you run? What happened?
Questions: Is there anything you still need help with?
```

The project's **continuous integration (CI)** checks are automated tests that run after you push. Open their logs if they fail. A draft PR can be useful for early feedback when the project welcomes drafts. Explain what is unfinished.

Before you ask for review, run `git-into-gsoc pr-check owner/repo#N` on your pull request. It checks your pull request against what the repository itself asks for: a linked issue, the template's checklist, a sign-off on every commit if the project requires one, tests next to code changes, a changelog entry if the project keeps one, and failing checks or merge conflicts. Each finding says where the rule came from, so you can confirm it. It cannot tell whether your change is right; only reviewers can.

When your pull request is open and has had a first review, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase contribute
```

## See it through review

Reviews often ask for changes. That is a normal part of collaboration, and how you respond matters as much as the code. Reply to every review comment within a day, even if only to say when you will get to it. Make the requested updates, push them as new commits to the same branch, and say what changed. If you disagree, explain your reasoning with an example. If you are stuck, ask one focused question instead of going quiet; a pull request that falls silent is usually closed. `git-into-gsoc draft review-reply --repo sympy/sympy --issue sympy/sympy#12345` gives you a respectful structure for answering a review. If the project declines the change, thank them, note what you learned, and choose the next thing.

Once your profile has your GitHub username, `git-into-gsoc next` also checks your open pull requests: it says which ones have a merge conflict, a failing check, requested changes, or a comment you have not answered, and which are simply waiting. When reviewers know you finish what you start, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase iterate
```

**Ready to move on:** your change has been reviewed or is ready for review, and you can explain what it does and how you checked it.

[Next: prepare a proposal](07-prepare-a-proposal.md) · [Track your progress](08-track-progress.md) · [Guide contents](../README.md)
