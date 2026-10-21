# 1. Understand GSoC

**Google Summer of Code (GSoC)** is an online program where contributors work on open-source software with guidance from mentors. Accepted contributors receive a stipend, subject to the program's rules and evaluations. It is not a job at Google. Read the [official FAQ](https://developers.google.com/open-source/gsoc/faq) for eligibility and how the program works.

**Open source** means a project's code is shared under a license that lets people use, study, and contribute to it. A **mentoring organization** is a community participating in GSoC. Its **mentors** help contributors plan and carry out a project. **Maintainers** look after a project's code, documentation, and reviews; not every maintainer is a GSoC mentor.

## What applying involves

1. Check the official eligibility requirements for your application year.
2. Find participating organizations and read their project ideas and application instructions.
3. Get to know a project, try its software, and discuss an idea with the community.
4. Write a **proposal**, a plan explaining what you want to build and how you will do it.
5. Submit through the official GSoC website before its deadline.

Organizations may ask for contributions or other preparation before applying. Follow their requirements rather than aiming for a particular number of changes. A useful contribution is a way to learn whether you enjoy the project; it does not guarantee selection.

## Start with what you know

Write a few lines for yourself:

```text
Languages or tools I have tried:
Topics I enjoy:
Time I can spend preparing each week:
My time zone and upcoming exams, work, or travel:
One thing I would like to learn:
```

After you [install the tool](02-install.md) in the next step, save the same answers so every recommendation fits you without retyping flags:

```bash
git-into-gsoc profile --tech python --interests science --hours 10 --tz Asia/Kolkata
```

Add `--github YOUR_USERNAME` and it also reads your public repositories to confirm your main language; offline, it saves the username and reads the languages next time. The profile lives only on your computer.

You can start by reading documentation or reproducing a bug. You do not need to be an expert in the whole codebase. The time you can spend preparing may differ from the time a GSoC project requires; discuss the project schedule before applying.

## Where you are in the year

After [installing the tool](02-install.md), run:

```bash
git-into-gsoc program
```

It shows the current phase of the program (for example "Before the program is announced" or "Proposal window is open"), what to do during that phase, and the timeline. When Google has published the year's dates, they are marked **official**. Otherwise the tool projects them from the previous year and marks every date as an **estimate** with an uncertainty window. Either way, confirm dates on the [official timeline](https://developers.google.com/open-source/gsoc/timeline) before acting on them.

Starting before the program is announced gives you time to learn a project and get feedback, and organizations that took part last year are the most likely to return. You can still begin at any point in the year.

## AI assistance

Before using AI for a contribution or proposal, read [Google's AI guidance](https://developers.google.com/open-source/gsoc/resources/ai_guidance) and the organization's own policy. Ask if the policy is unclear. You are responsible for understanding and checking anything you submit. Many organizations reject proposals that read as AI-generated, and the tool's guidance asks you to write everything in your own words.

When you are unsure what to do at any point, run `git-into-gsoc next`. It combines the program phase, your profile, and your saved progress into the next few actions, each with the command to run.

**Ready to move on:** you can describe GSoC, know where to check the rules, and have written down your interests.

[Next: install the tool](02-install.md) · [Guide contents](../README.md)
