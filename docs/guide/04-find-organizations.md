# 4. Find organizations you want to join

Start with a language you know and a topic you care about. You are looking for a community where you can learn and contribute, not just the highest score.

The quickest first look is the guided start. It asks four questions (your GitHub username, which is optional, the languages you know, topics from a numbered list, and hours per week), saves the answers as your profile, and shows the three organizations that fit best:

```bash
git-into-gsoc start
```

To see a longer list, or to try other languages and topics, search directly:

```bash
git-into-gsoc orgs --tech python --topics science -n 5
```

Expect a table with a fit score, the organization, why it matched ("Uses python", "Topic: science"), how many years it has mentored, and how many projects it ran in recent years. The caption tells you which year's list you are looking at. Until Google announces the next year's organizations, the tool shows the latest official list, because last year's participants are the best predictor of who returns.

Technologies and topics decide whether an organization matches at all; continuity and capacity decide the order among matches. Aliases such as `js`, `golang`, or `ml` are understood. Use `--query` to search names and descriptions, and `--category` for GSoC categories such as "Science and medicine".

```bash
git-into-gsoc orgs --query "symbolic math" -n 5
git-into-gsoc org "SymPy"
```

`org` shows one organization's ideas page, contributor guide, source code, website, GitHub organizations, contact channels, technologies, projects per year, and its recent accepted project titles. Those titles are there to help you understand the scope organizations fund; never copy a past proposal. SymPy is an example lookup, not a promise of future participation or available work. In October 2026 a SymPy maintainer wrote that, after a flood of low-quality AI pull requests, SymPy will likely not take part in GSoC 2027 ([SymPy issue 30671](https://github.com/sympy/sympy/issues/30671)). The official 2027 organization list is the final word.

## Read the ideas page as a list

```bash
git-into-gsoc ideas "SymPy" --skills python,sympy
git-into-gsoc mentors "SymPy"
```

Ideas pages are long and every organization formats them differently. `ideas` reads the page into a table with each idea's size, difficulty, mentors, and skills, and ranks the ones that match the skills you give. `mentors` lists who has mentored the organization's completed projects and which ones, so you know whose name to look for in discussions. Both are best-effort readings of pages the tool does not control; open the page itself before you decide.

## See what organizations have funded before

```bash
git-into-gsoc projects "graph neural networks" --since 2024
git-into-gsoc projects --org "Zulip" -n 10
```

Searching past accepted projects by keyword tells you which organizations fund the kind of work you enjoy, and how big a typical project is.

## Make a small shortlist

For each interesting result:

1. Check its participation on the [official GSoC site](https://summerofcode.withgoogle.com) for your target year once the list is announced.
2. Open its ideas page and contributor guide from the `org` output. Read a project idea and identify what you would need to learn.
3. Find the community's preferred discussion channel and read recent conversations.
4. Keep a brief note about why it fits you and what remains unclear.

Start with two or three organizations. It is fine to keep only one if you already have a clear fit. Previous participation is useful context, not a guarantee that the organization will return.

```bash
git-into-gsoc org "SymPy" --shortlist           # same details, and adds it to your shortlist
```

```text
Organization:
Official program page and current ideas page:
What interests me:
Skills I have / need to learn:
Contribution instructions and discussion channel:
Next thing to investigate:
```

## Optional recommendations

```bash
git-into-gsoc recommend --tech python --interests science --experience new --hours 10
```

Each organization comes with a fit (strong, good, or partial) and the evidence for it, such as "topic tag 'astronomy' on its official GSoC listing" or "main language of 17 of its 28 GitHub repositories". Read the caveats too: an ideas page where nearly every idea is hard, or ideas too big for your hours. You also get ideas from each top organization's latest ideas page that fit what you know, with the skills each would teach you, starter issues with what in them fits you, and a short path with a command for each step.

Adding `--github YOUR_USERNAME` uses your recent public repositories to infer your main language, and your merged pull requests to estimate your experience, and saves a profile locally. A new or empty GitHub profile is fine; supplying `--tech` yourself is enough. `--experience` is `new`, `some`, or `experienced`. The starter issues it lists come from repositories owned by the recommended organizations, then other GSoC organizations that use your language.

Fit says how well the work matches you, not your chance of being selected. Until Google announces the coming year's organizations, the list shows last year's participants, and none is confirmed. See [how recommendations work](../recommendations.md).

## If results are missing or unhelpful

Try a broader `--query`, another technology, or omit the topic. If the tool cannot reach the official site or the archive, the error names the source that failed; open the organization list on [summerofcode.withgoogle.com](https://summerofcode.withgoogle.com) in your browser, or try again later. Scores help sort research; they do not measure your chances of selection. Read [sources and limitations](../sources.md) for more detail.

When you have a short list with a reason for each organization, mark the step done:

```bash
git-into-gsoc progress complete_phase --phase discover
```

**Ready to move on:** you have an organization, its current ideas page, and a reason it fits you.

[Next: pick a repository and an issue](05-choose-an-issue.md) · [Guide contents](../README.md)
