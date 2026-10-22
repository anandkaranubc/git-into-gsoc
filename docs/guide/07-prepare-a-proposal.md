# 7. Prepare your proposal

A proposal is a plan for a specific GSoC project. It explains the problem, your approach, the work you will deliver, and how you will use the available time. Start from the organization's current template and application instructions.

```bash
git-into-gsoc proposal
git-into-gsoc program            # when does the proposal window open and close?
```

`proposal` prints a checklist and a suggested structure. It does not create an application, save a draft, or submit anything. `program` shows the proposal milestones for the year; when they are estimates rather than official dates, it says so.

## Gather evidence before drafting

Collect the project idea, required questions, relevant code or documentation, your real contribution links, and feedback from the community. The tool can gather the links for you:

```bash
git-into-gsoc contributions --org "SymPy"
```

It needs your GitHub username: if you did not save it in step 1, run `git-into-gsoc profile --github YOUR_USERNAME` first, or add `--github YOUR_USERNAME` to this command. It lists your pull requests, issues, and reviews in the organization's repositories with their state, ready to paste into the "about you" and "prior contributions" sections. The proposal check below verifies those links again.

Check the organization's requested project size against your availability. Projects are about 90 hours (small), 175 hours (medium), or 350 hours (large), and the coding period runs 8 to 22 weeks ([GSoC FAQ](https://developers.google.com/open-source/gsoc/faq)). If you saved your hours with `profile --hours`, `next` tells you which sizes fit. There is no universal requirement for a fixed number of merged PRs; follow the organization's prerequisites.

To see how big accepted projects have been and what the organization values:

```bash
git-into-gsoc org "Your Org"                  # recent accepted project titles
git-into-gsoc projects --org "Your Org" -n 20
```

Use these to calibrate scope. Never copy a past proposal.

## Write a plan in your own words

Use the organization's sections first. If it does not provide a template, these questions can help:

- What problem are you solving, and who benefits?
- How does the project work today? What have you investigated?
- What will you change, and what will be outside the scope?
- What will each milestone deliver, and how will you check that it works?
- How much time will each part take, including learning, tests, reviews, and unexpected problems?
- What might be difficult, and what could you reduce if time runs short?
- How will you communicate progress, and when will you be unavailable?
- What experience and real contributions help you carry out this plan?

A **milestone** is a concrete result you can demonstrate. For example, "add and test input validation for the agreed cases" is easier to assess than "work on validation." Use examples from your actual project and discuss the scope with mentors.

## Check the draft before anyone else reads it

```bash
git-into-gsoc proposal draft.md --github YOUR_USERNAME
```

Save your draft as Markdown or plain text and run the check. It reports, with reasons, whether the required sections are there (synopsis, deliverables, timeline, about you), whether you linked pull requests and whether GitHub confirms they are yours and merged, whether the timeline is week by week with buffer time, whether the text names real files, functions, and issues, and whether it contains the generic phrases and leftover placeholders that [Google's spam guidance](https://developers.google.com/open-source/gsoc/resources/spam_proposals) warns organizations about. If you saved the organization's ideas page as a text file, add `--ideas-file ideas.txt` to see how much of your draft merely restates it.

The check never rewrites anything. Fix the failures, then the warnings, in your own words. "Structurally complete" means the skeleton is right; only a mentor can tell you whether the plan is good.

## Get feedback and submit

1. Share a draft through the organization's requested channel, if it accepts drafts.
2. Ask focused questions about your approach and schedule.
3. Revise based on feedback and check every required section.
4. Follow the organization's AI policy, including any disclosure requirements.
5. Submit through the [official GSoC site](https://summerofcode.withgoogle.com) and check that the submission is recorded before the official deadline.

Sending a document to a mentor is not the formal submission. Verify the deadline and time zone on the [official timeline](https://developers.google.com/open-source/gsoc/timeline); the tool's estimates are not deadlines.

Read [Google's proposal guidance](https://google.github.io/gsocguides/student/writing-a-proposal.html), [AI guidance](https://developers.google.com/open-source/gsoc/resources/ai_guidance), and [advice about low-quality proposals](https://developers.google.com/open-source/gsoc/resources/spam_proposals). Specific evidence and a realistic plan matter more than elaborate wording.

When your draft has had mentor feedback and is ready for the official site, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase proposal
```

**Ready to submit:** your proposal follows the organization's instructions, contains only claims you can support, and describes work you understand.

[Next: track your progress](08-track-progress.md) · [Guide contents](../README.md)
