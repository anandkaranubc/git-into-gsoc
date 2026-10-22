# How recommendations work

`orgs`, `recommend`, `repos`, `issues`, and `ideas` all try to answer one question: where can this person start contributing, given what they know, what they care about, how much open source they have done, and how many hours they have? This page explains how the answer is built, what it never claims, and how well it works.

## What you get

`git-into-gsoc recommend --tech html,css --interests accessibility --experience new --hours 8` returns:

- **Organizations**, each with a **fit**: *strong*, *good*, or *partial*. Fit says how well the organization's work matches you. It is not your chance of being accepted, and nothing here estimates that.
- **Evidence** for every fit, each line naming its source, for example "Topic Accessibility: topic tag 'accessibility' on its official GSoC listing" or "Skill Python: main language of 17 of its 28 GitHub repositories pushed in the last year".
- **Caveats**: things to know before choosing, such as "4 of the 5 ideas that state a difficulty are hard", or that the ideas' sizes cannot fit your hours.
- **Ideas that fit you**, from each top organization's latest ideas page: what you already know for each idea, and what you would learn.
- **Starter issues** still open to newcomers, each with what in it fits you.
- **Your path from here**: a few ordered steps, each with the command that does it.

`orgs` gives the same fit, evidence, and caveats for a quick list. In an AI assistant, the `gsoc_recommend_path` and `gsoc_search_orgs` tools return the same fields.

## Your words

You can type skills and interests in your own words. A small vocabulary, kept in [`matching/concepts.py`](../src/git_into_gsoc/matching/concepts.py), maps about 150 skills and subjects to the many ways people and organizations write them:

- `healthcare` also finds organizations tagged `radiology`, `electronic medical records`, or `fhir`.
- `web dev`, `AI`, `k8s`, and `node.js` mean what you expect.
- `c/c++` counts once, as one skill with two parts.
- An obvious misspelling such as `pyhton` is read as `python`, and the output says so ("Read 'pyhton' as 'python'").
- A word that names nothing in the vocabulary is still searched for as a plain word.

Short words that are also English words (`go`, `c`, `r`, `react`, `spring`) only count in tags and in what you type, never inside a description, unless they appear with their usual capital letter ("written in Go").

## What we know about each organization

Three public sources describe each organization:

| Source | What it tells us | How fresh |
|---|---|---|
| Its official GSoC listing (tags, categories, tagline, description) | What the organization says it works on and with | The latest official list, embedded and refreshed weekly |
| Its ideas page | How many ideas, the difficulty and size each states, and the skills and subjects they name | Read for every organization once a month and shipped as `data/org_signals.json` |
| Its GitHub repositories | How many were pushed to in the last year, and their languages and topics | Same monthly refresh |

A tag the organization chose counts most. A word in its description, ideas page, or repositories counts less, and more when several sources agree. A subject that tags, ideas, and code all mention is central to an organization; a single tag may be a side interest. The ideas evidence always names its year ("listed as a skill in 9 of 12 2026 ideas"), because last year's page says what an organization works on even before the new one appears.

## How fit is decided

Relevance decides the order:

1. **Interests.** How well the organization's work covers each thing you care about. A match through a neighbouring subject (physics for astronomy) counts for less, and the evidence says so plainly: "Topic Astronomy and space: not named; the nearest is Physics". An umbrella subject such as "science" or "web" never stands in for a specific interest.
2. **Skills.** A skill matches only itself or what it is part of: React counts where JavaScript is used, but Phoenix never counts because an organization does backend work, and C is not assembly. Skills are alternatives: someone who knows Python and R can work where either is used, so the best match counts most and covering more of them adds a little. A skill few organizations use (Julia, Kotlin) says more than one most use (Python), so rare skills weigh more, like inverse document frequency in search engines.
3. Interests and skills count about equally, with a small bonus when both match.
4. An organization named after something you asked for (The Rust Foundation, LLVM, Open Robotics) is that thing's home and gets a small lift when its other evidence agrees, except for people new to open source, for whom fit matters more than a flagship.
5. An organization that lists many skills or subjects (a runtime for nine languages, an umbrella for dozens of projects) says less about each one than a focused organization does, so its matches count a little less, the way search engines discount very long documents.

Three things only break ties. Together they can move an organization by a fifth of its score, never past a clearly better match:

- **Track record**: how many of the last five years it took part.
- **Capacity**: how many contributor projects it had last year.
- **Beginner readiness**: a contributor guide, a readable ideas page, and how many ideas are easy or medium and small or medium. This weighs more when you say you are new to open source.

With several interests, the list is reordered a little so each interest appears near the top (maximal marginal relevance, Carbonell and Goldstein, 1998).

A fit is good only when the organization names at least one of your interests itself; a match only through a neighbouring subject is partial. It is strong only when two kinds of evidence (a tag and its description, ideas, or code) agree on the interest, and nothing decides against it: not when most of an organization's ideas need a language you did not list (it says "Most of its ideas need Fortran, which you did not list"), when its stated idea sizes cannot fit your hours, when most of its ideas are hard and you are new, or when your interest is so broad that it matches dozens of organizations.

The numeric `match_score` in JSON output only orders results. Please never present it, or the fit level, as a probability of anything.

## When your words are broad

A broad word matches dozens of organizations: "ai" matches more than 90, and "python" alone more than 120. Then `orgs` and `recommend` add a tip with narrower words and how many organizations each matches, for example "LLMs and AI agents (29), Computer vision (11), Natural language processing (8)", or for a skill with no interest, the subjects the organizations that use it work on most. The JSON output has the same tips under `sharpen`.

## Experience and hours

Set them once with `profile --experience new|some|experienced --hours 10`, or pass them to `recommend`. With `profile --github USER` and no `--experience`, the level is read from how many of your pull requests were merged in other people's repositories (none: new; 1 to 9: some; 10 or more: experienced), and the output says where it came from.

- **New**: organizations whose stated ideas are nearly all hard move down and say so; documentation and test issues get a small lift; the path starts with practising the pull request routine.
- **Hours**: GSoC projects are about 90, 175, or 350 hours, usually over 12 weeks and at most 22 with the mentor's agreement ([GSoC FAQ](https://developers.google.com/open-source/gsoc/faq), [timeline](https://developers.google.com/open-source/gsoc/timeline)). When none of an organization's stated idea sizes fits in 22 weeks at your hours, it moves down with a caveat, and ideas too big for your hours are left out of "ideas that fit you".

## The coming year and last year

Google announces each year's organizations around February. Until then, `orgs` and `recommend` use the latest official list and say plainly that none of these organizations is confirmed for the coming year ([official API](https://summerofcode.withgoogle.com/api/program/), checked 2026-10-21: the 2027 program does not exist yet).

`recommend` (and `orgs`, for its top three) also reads what its top five organizations (three without a GitHub token) posted about the coming year, in their issue trackers and wiki home pages. One whose maintainers say it will not take part moves to the end with the post as its first caveat, and its issues are left out of the starter list. A maintainer post about the coming year becomes a readiness line. A name you search that took part in earlier years but is not on the current list gets an explanation instead of an empty table.

## Who can apply

`recommend` ends with the facts that decide whether and where you can apply, quoted from the [GSoC FAQ](https://developers.google.com/open-source/gsoc/faq): you must be 18 or older when you register, and a student or a beginner to open source ("GSoC is not for experienced open source developers"; it says this to anyone who calls themselves experienced). For someone who lists only writing tools, it notes that GSoC projects are coding projects. When no 2026 organization uses one of your skills (Elixir, for example), it says so, because the results then rest on your other skills.

## Repositories, issues, and ideas

- **`repos ORG`** ranks an organization's repositories by whether its ideas page names them, open beginner issues, recent activity, and whether their language, topics, and description match your skills and interests. The project's main repository (named like its GitHub owner, or its most-starred active one) comes first. Repositories around the project go lower, each with a reason: GSoC, event, and governance repositories; build, CI, and release tooling; and websites. A website is still fine for a first docs fix. Repositories with GitHub issues turned off stay in the list, since a main repository may track bugs elsewhere. Deprecated repositories and mirrors are left out. For the top five, it reads the last 30 closed pull requests and says how many people outside the team got one merged in the last 180 days. A repository with none goes lower. When none of the checked repositories took outside work, `repos` says so and points to the organization's ideas page and its mentors: at some organizations GSoC work starts there, not from GitHub issues. Very large repositories (over about 1 GB) say so, because cloning and building take longer.
- **Caveats name the language most of an organization's active code is in** when you did not list it ("Its code is mostly Rust: the main language of 6 of its 14 GitHub repositories pushed in the last year").
- **Starter issues in `recommend`** come from the first six organizations, up to two GitHub owners each, in every language you know (Django counts as Python). They must carry a beginner label such as "good first issue", "starter", or "easy". "Help wanted" alone is not enough: in two blind reviews, only 1 of 12 such issues was a good first task. They must also be first tasks, so these are skipped (the table says how many):
  - announcements, roadmaps, trackers, epics, "what can I work on?" lists, and calls for testing;
  - issues open three years or more;
  - issues labelled intermediate, medium, advanced, "can't reproduce", "needs triage", "needs discussion", duplicate, or similar;
  - issues in repositories marked deprecated or legacy, in governance, test, or sandbox repositories, or in repositories mostly written in a language you did not list;
  - issues that need only skills you did not list;
  - issues someone else is likely working on: three or more people asked for it, its own author said they are working on it, or a maintainer approved someone in the last 180 days. `issue` calls older claims stale, which is fair when you check one issue yourself, but a first-task list should not send you to someone else's work.

  Issues from the wider language search must come from organizations near the top of your ranking. When nothing is left, it says what to do instead.
- **`issues`** keeps its order (availability, the beginner score, and an organization's own repositories before the ones its ideas page links to) and says what in each issue fits you. **`recommend`** goes further with its starter issues: an issue that names a skill you have or a subject you care about moves up, and people new to open source get a small lift for documentation and test issues. Personalised first-issue research found that newcomers' first issues share their task type, language, and domain ([Xiao et al., ASE 2023](https://arxiv.org/abs/2308.09038)).
- **Ideas that fit you** leave out page headings and fragments ("Description", "Project 2", "Benefit to ...") and ideas marked as taken.
- **`ideas ORG`** matches ideas by concept, so `reactjs` matches React and `c` no longer matches every idea that contains the letter c, and lists the skills each idea would teach.

## How well it works

Two benchmarks in [`evals/`](../evals/README.md) run offline against the embedded data:

- **34 personas** across ecosystems and experience levels, each with graded judgments (3 strong, 2 good, 1 partial) made by a reviewer who never saw the ranking code, and a list of organizations that should not reach the top five.
- **238 profiles written from real GSoC 2026 accepted projects**, without seeing the organization. The organization that accepted the project is the answer.

Each has a dev half, used while tuning, and a test half, checked only after tuning. Results on the test half, against the keyword ranker this replaced:

| Test half | Keyword ranker | Now |
|---|---|---|
| Personas: nDCG@10 (agreement with graded judgments, 1 is perfect) | 0.643 | **0.810** |
| Personas: share of the top 5 that judges rated good or strong | 0.537 | **0.637** |
| Personas: strong fits found in the top 10 | 0.763 | **0.885** |
| Personas: picks in the top 5 that judges called wrong | 14 | **6** |
| Accepted projects: accepting organization in the top 5 | 52.1% | **66.4%** |
| Accepted projects: accepting organization in the top 10 | 62.2% | **76.5%** |

A third set of 12 personas from a second blind reviewer, in ecosystems the first set does not cover (Swift, Elixir, Scala, Lua, C#, embedded Rust, documentation only), confirmed the gain on first sight: nDCG@10 0.451 for the keyword ranker against 0.566 now, and judged-wrong picks in the top five down from 21 to 11.

A fourth set of 15 personas from a third blind reviewer (quantum computing, browser engines, FPGA, cheminformatics, localization, a near-empty profile, and more) is sealed: only its totals are shown, and nothing is tuned on it. At its first look the current ranker scored nDCG@10 0.488 against 0.332 for the keyword ranker, but put 6 judged-wrong organizations in top fives against the keyword ranker's 5. People unlike any earlier persona are where matching is weakest.

So a fifth set of 15 such people, from a fourth blind reviewer, became a second development set (screen readers, supply chain security, R dashboards, speech models, hospital software, and more). It showed vocabulary and matching gaps, fixed in a fifth round: on that set nDCG@10 went from 0.550 to 0.623 and wrong picks from 9 to 8. On the sealed set, read once afterwards, nDCG@10 went from 0.488 to 0.493 and strong fits found from 0.667 to 0.700, with wrong picks unchanged at 6. The gain carries over to new kinds of people, but only a little.

Run `python scripts/eval_matching.py` to reproduce them. A test (`tests/unit/test_match_benchmark.py`) fails if a change makes them clearly worse, and CI runs it on the monthly data refresh too.

## What independent reviewers found

Twice, a reviewer who never saw the code read the live `recommend` output for all 46 personas and graded it as a mentor would. Both times every output was honest: no chance of acceptance, the 2027 list never presented as confirmed, and the eligibility rules stated correctly. About 70% of the top three organizations were graded good or strong (a mean of about 2 out of 3), and the learning path was judged right for about two thirds of people. Their findings led to the stricter evidence, the screened starter issues, the eligibility notes, and the sitting-out flags described above.

Starter issues were then compared in blind pairs: for each of the 46 personas, a reviewer read the live thread of every issue in two lists without knowing which version made which, graded each issue good, ok, or bad for that person, and picked the list they would rather hand over. Against the version before the stricter screen, the current one kept the same number of good issues (8 against 8), cut bad ones from 26 to 8, cut the people handed a bad issue from 19 to 7, and was preferred for 19 people against 6 (21 ties). The price is that 9 more people get an empty list with a note on where to look instead. Two further rules were tested against the reviewers' grades and left out because they would have dropped good issues: skipping an issue that a merged pull request mentions (4 good, 13 ok, and 7 bad issues), and skipping one that several pull requests tried and failed (a single example).

`repos` was checked the same way: for 20 personas and their top organization, a reviewer read each suggested repository on GitHub. The first review graded 38 of 98 top-five repositories bad. A blind paired review of the old and new versions found good ones up from 29 to 35 and bad ones down from 34 to 27. 16 of 20 people now have a good repository first, against 14 before, and the reviewer preferred the new list for 8 people against 2 (10 ties). A small penalty for repositories in a language the person did not list was tried and left out: it dropped a C library a physicist could use, and brought in a logo repository. Reading recent outside merges for the top five was then compared the same way, by a third reviewer: it was a tie (28 good repositories in both, 36 bad against 38, preferred for 7 people against 8). It stays because it tells you, with the count, whether outsiders get work merged there, and it turns a list of quiet repositories into a pointer to the ideas page. The three reviewers also graded the same lists quite differently (28 to 35 good), so only comparisons made by one reviewer are meaningful.

What the reviewers still found weak is listed next.

## Known limits

- **Some suggested repositories are still a poor fit.** The top five now say whether outsiders got work merged lately, but the rest of the list is not checked, and a repository in a language you did not list can still appear. Run `git-into-gsoc repo owner/name` on your pick for the full check.
- **Starter issues are thin.** Recent issues with a beginner label that suit a given person are scarce in their best organizations, so after screening about six in ten people get no starter issue and are pointed to the best organization's repositories and chat instead. About one in four issues that pass the checks is still unsuitable, most often because it was already fixed without a linked pull request, or is not really a task (a question, a broken link to fix by a maintainer). Read each thread before you start.
- **Some ideas lists are noisy.** Ideas pages are written in many formats, and some headings still slip through as ideas.
- **Very vague input** ("ai" alone) still gives a long list; the tip suggests narrower words, and adding one helps most.
- **Organizations with many tags** (polyglot runtimes, umbrellas) still match many searches, but count a little less per match than focused organizations.
- **Reputation is invisible.** Some organizations are known for welcoming newcomers in ways their listing and ideas page do not show. Evidence comes only from public data, so ask in each community.
- **Ideas pages vary.** About a third state a difficulty and about a third a size, and some pages cannot be read automatically; the evidence says when a page could not be read.
- **Judgments are one reviewer's view.** The persona grades were made carefully but by a single reviewer, so treat small differences between versions as noise.

## Research this builds on

- Newcomer barriers: social interaction, previous knowledge, finding a way to start, documentation, and technical hurdles ([Steinmacher et al., IST 2015](https://doi.org/10.1016/j.infsof.2014.11.001)). The path's first steps address finding a way to start and the technical setup.
- Good first issues are often unsolved by newcomers, and good ones have limited scope and skill ([Tan et al., ESEC/FSE 2020](https://doi.org/10.1145/3368089.3409746)); expert involvement in the thread helps ([Tan et al., ICSE 2023](https://arxiv.org/abs/2302.05058)).
- Skill labels for tasks help people choose ([Santos et al., MSR 2021](https://doi.org/10.1109/MSR52588.2021.00047)), but carry over only partly between projects ([Santos et al., EMSE 2023](https://doi.org/10.1007/s10664-023-10329-4)), so the vocabulary maps words to a few broad concepts rather than fine-grained labels.
- Graded relevance and nDCG for evaluation ([Järvelin and Kekäläinen, TOIS 2002](https://doi.org/10.1145/582415.582418)); diversity by maximal marginal relevance ([Carbonell and Goldstein, SIGIR 1998](https://doi.org/10.1145/290941.291025)); explanations improve trust and usefulness ([Zhang and Chen, 2020](https://doi.org/10.1561/1500000066)).
- Earlier contributions to a project predict how much GSoC students produce and how long they stay ([Silva et al., ICSME 2017](https://doi.org/10.1109/ICSME.2017.81)), which is why the path asks for contact and a merged change before the proposal.
- Google's own advice: pick three to five organizations to research in depth, contact them before the application period, and remember that quality matters more than quantity ([contributor advice](https://developers.google.com/open-source/gsoc/help/student-advice), [making first contact](https://google.github.io/gsocguides/student/making-first-contact)).
