# 4. Find organizations you want to join

Start with a language you know and a topic you care about. You are looking for a community where you can learn and contribute, not just the highest score.

```bash
git-into-gsoc orgs --tech python --topics science -n 5
```

Expect a table with a fit score, the organization, why it matched ("Uses python", "Topic: science"), how many years it has mentored, and how many projects it ran in recent years. The caption tells you which year's list you are looking at. Until Google announces the next year's organizations, the tool shows the latest official list, because last year's participants are the best predictor of who returns.

Technologies and topics decide whether an organization matches at all; continuity and capacity decide the order among matches. Aliases such as `js`, `golang`, or `ml` are understood. Use `--query` to search names and descriptions, and `--category` for GSoC categories such as "Science and medicine".

```bash
git-into-gsoc orgs --query "symbolic math" -n 5
git-into-gsoc org "SymPy"
```

`org` shows one organization's ideas page, contributor guide, source code, website, GitHub organizations, contact channels, technologies, projects per year, and its recent accepted project titles. Those titles are there to help you understand the scope organizations fund; never copy a past proposal. SymPy is an example lookup, not a promise of future participation or available work.

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
git-into-gsoc recommend --tech python --interests science
```

Adding `--github YOUR_USERNAME` uses your recent public repositories to infer your main language and saves a profile locally. A new or empty GitHub profile is fine; supplying `--tech` yourself is enough. The starter issues it lists come from repositories owned by GSoC organizations that use your language.

## If results are missing or unhelpful

Try a broader `--query`, another technology, or omit the topic. Check the official directory directly if both the official site and the archive are unavailable; the error message names the source that failed. Scores help sort research; they do not measure your chances of selection. Read [sources and limitations](../sources.md) for more detail.

**Ready to move on:** you have an organization, its current ideas page, and a reason it fits you.

[Next: pick a repository and an issue](05-choose-an-issue.md) · [Guide contents](../README.md)
