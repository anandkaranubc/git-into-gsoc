<!-- Research working notes. Written 2026-10-20/21 during the ecosystem research pass; kept as the evidence base for ../research.md. Claims marked unverified were not confirmed against a primary source. Plain-language rules apply loosely here; these are notes, not a guide. -->

> Working notes from the research pass of October 2026. The research on newcomer onboarding, what maintainers say they want, and adjacent programs. The checked conclusions are in [the research summary](../research.md); these notes keep the evidence, numbers, and URLs behind them. Items marked unverified were not confirmed against a primary source.

# F. The science and craft of newcomer onboarding, personalised guidance, and adjacent ideas

> Verification status. Re-checked first hand on 2026-10-21: the five studies were re-opened and the quoted figures read from the PDFs (48,402 good first issues; 1,155 GitHub projects and five Gerrit projects), Google's 2026 ratio, Outreachy's models, the CNCF proposal template, OWASP Nest's contribution check, the GSoC discussion group's topic list, and Hacker News's story set. Links: 82 of 87 resolved with HTTP 200 on 2026-10-21; the rest are URL templates with placeholders, endpoints that need a token, or sites that block scripts. Everything else here is the research stream's working record as written.

Research stream for git-into-gsoc. Written 2026-10-20. Every claim about a paper, project or page cites the URL it was read from. Where a number could not be checked against a primary source it is marked **unverified**.

---

## TL;DR

1. **The acceptance funnel is brutal and prior engagement is the main lever.** GSoC 2025: 15,240 applicants, 23,559 proposals, 1,272 accepted (about 5.4% of proposals, 8.3% of applicants). 66.3% of applicants had no prior open-source experience, but only 43.04% of accepted contributors had none. If the two figures measure the same thing, applicants with prior OSS experience were roughly 2.6x as likely to be accepted (my computation; the two figures come from different Google posts so treat as an estimate). Google's own advice: "An organization won't accept a person based solely on a nice proposal" and "Over 94% of people accepted last year submitted 2 or fewer proposals." ([May 2025 post](https://opensource.googleblog.com/2025/05/gsoc-2025-we-have-our-contributors.html), [Aug 2025 stats](https://opensource.googleblog.com/2025/08/google-summer-of-code-2025-contributor-statistics.html), [student advice](https://developers.google.com/open-source/gsoc/help/student-advice))
2. **Task selection has a replicated evidence base.** Across 1,155 GitHub + 5 Gerrit projects, newcomers' first patches are more likely to be accepted when they are bug fixes, add few lines, touch few files, are labelled good-first-issue (5.57x odds in large GitHub projects), and are low-complexity or documentation changes. Starting with a *new feature* lowers acceptance odds on GitHub. Longer/prettier titles and descriptions do **not** help. "Be proactive" and "be patient" (responding to review) are the strongest predictors of all. Three recommendations (low complexity, docs, few deletions) are newcomer-specific and should be abandoned after the first merges. ([Turzo, Sultana, Bosu 2025](https://arxiv.org/pdf/2407.04159))
3. **Mentoring, not submission polish, drives first-PR success; response time matters.** 70% of good-first-issues have expert participation; the median first expert reply after a newcomer comment is 8.5 hours, 25% within 41 minutes, a few over two months. Expert involvement raises first-contribution success by 71%. ([Tan et al. ICSE 2023](https://arxiv.org/pdf/2302.05058)) Replies within 48 hours correlate with future participation ([Jensen, King, Kuechler 2011](https://flosshub.org/node/1481)); Mozilla: "prompt review of a patch is strongly correlated to contributor retention" ([Mozilla wiki, 2014](https://wiki.mozilla.org/Contribute/Coding/Pathways)).
4. **GFI supply is shrinking and newcomer GFI merge rates are falling (61.9% to 42.2%, 2021-2025), with a structural break in January 2024 that coincides with AI-tool adoption**; 73% of GFIs never get a newcomer PR; description length rose 57% and predicted nothing. ([Hoshikawa et al. EASE 2026](https://arxiv.org/pdf/2604.27532)) Maintainers say the same thing: stdlib found GFIs "resulted in a very high number of low-quality submissions" and now avoids assigning issues at all ([stdlib 2024 retrospective](https://dev.to/stdlib/reflecting-on-gsoc-2024-5doa)); Hacktoberfest 2026 stopped counting PRs entirely because "It's easier than ever to submit low-effort spam PRs" ([hacktoberfest.com](https://hacktoberfest.com/llms-full.txt)).
5. **Retention is about willingness and opportunity, not prestige.** Newcomers who get an issue they reported fixed within their first month roughly double their odds of becoming long-term contributors; low peer attention and *high project popularity* reduce those odds ([Zhou & Mockus, TSE 2015](https://core.ac.uk/works/174176176)). Newcomers who solve a GFI in a *less popular* project are more likely to keep contributing ([Tan 2023](https://arxiv.org/pdf/2302.05058)). For GSoC specifically: ~43% of newcomer students kept contributing more than a month after the program, ~26% more than six months, ~16% more than a year ([Silva et al. ICSME 2017](https://www.ime.usp.br/~gerosa/papers/08094410.pdf)), versus Google's survey where 99.84% *said* they planned to continue ([Google 2023](https://opensource.googleblog.com/2023/12/google-summer-of-code-2023-final-results.html)).
6. **Why PRs die:** superseded/duplicated (most common), vision mismatch, "not needed", integrator lack of interest, no tests ("if the proposed contribution does not come with tests, the pull-request is immediately closed"), side effects, obsolete code. 85% of unsuccessful contributors try only once; 30% are demotivated. ([Steinmacher et al. ICSE 2018](https://www.ime.usp.br/~gerosa/papers/icse2018-Pinto.pdf))
7. **Our journey order is wrong in one important place:** community contact comes *before* finding issues in every authoritative source (GSoC guide "lurk first, ask questions before offering opinions", Outreachy "All applicants need to be the first one to reach out to mentors", Google "TALK TO THE ORG!", Steinmacher's FLOSScoach flow). We also lack an "orient" phase (environment + code reading), an "iterate" phase (respond to review; second contribution), an explicit "ask a good question" skill, and a post-decision phase.
8. **A weekly log should copy python-gsoc's three questions** ("What did you do this week? What is coming up next? Did you get stuck anywhere?") plus links, and feed the proposal's "about you / prior contributions" and the mandatory GSoC final work product (whose required contents Google lists). Weekly, not daily streaks: streak research says rigid streaks cause guilt and abandonment, and Outreachy caps blogging at "1-3 hours". ([python-gsoc.org](https://python-gsoc.org/blogs.html), [GSoC work product](https://developers.google.com/open-source/gsoc/help/work-product), [Outreachy internship docs](https://www.outreachy.org/docs/internship/))
9. **Templates should be grounded in maintainers' words**, which converge on: say what you tried, be specific, one claim comment with a plan, small PRs with tests and a what/why description, reply to every review comment, never DM/LinkedIn mentors. Details and sources in section 6.
10. **Present ethics as the reviewer's inbox, not a sermon**: show the ratio (stdlib: 1,000+ PRs from 100+ people for 4 slots), quote the org's own consequence ("It will be caught... will either be ignored or closed", SymPy), and make the evidence-bearing path the default template.

---

## 0. Method and verification notes

- Primary sources fetched directly: 11 academic PDFs (extracted with pdftotext), the GSoC contributor guide chapters, Google's FAQ/responsibilities/work-product/AI/spam-proposal pages, Outreachy docs, python-gsoc.org, kernelnewbies, Exercism docs, Hacktoberfest's `llms-full.txt`, CNCF/Apache/All-Contributors/first-timers-only pages, READMEs via `gh api`, and maintainer threads (stdlib, Jenkins, SymPy, Joplin, Julia, Kubernetes, pandas).
- **Could not verify:** r/GSoC (reddit blocked from this environment; the "common mistakes" material below comes from blogs, Discourse and mailing lists instead). The "48 hours / 7 days" Mozilla retention numbers exist only on an Ansible wiki page citing Mike Hoye ([ansible/community wiki](https://github-wiki-see.page/m/ansible/community/wiki/Contributor-Experience:-Plan)); Mozilla's own wiki states the correlation without numbers. GitHub's 2026 "restrict PRs from outside contributors" controls are reported by single secondary outlets only. Octoverse 2024/2025 first-time-contributor counts were not found. GFI-Bot's repo (`osslab-pku/gfibot`) could not be resolved via `gh`.
- Gousios' integrator percentages are taken from Adrian Colyer's summary of the paper, not the paper itself ([blog.acolyer.org](https://blog.acolyer.org/2015/06/23/work-practices-and-challenges-in-pull-based-development/)).

---

## 1. What the research says, concretely

### 1.1 Barriers: the map we should design against

- **Steinmacher et al., systematic literature review (IST 2015):** 15 barriers in five categories: social interaction, newcomers' previous knowledge, finding a way to start, documentation, technical hurdles; classified by origin (newcomer / community / product). The earlier multi-source study found 58 barriers in six categories: cultural differences, newcomers' characteristics, reception issues, orientation, technical hurdles, documentation problems. ([NAU record](https://experts.nau.edu/en/publications/barriers-faced-by-newcomers-to-open-source-projects-a-systematic-/), [2014 preprint](https://www.ime.usp.br/~gerosa/papers/HardLife2014Steinmacher.pdf))
- **FLOSScoach (ICSE 2016):** a portal with one section per barrier category (skills needed, step-by-step contribution flow, where the repo/tracker/list live, message templates). Evaluated with 65 students via diaries, self-efficacy questionnaires and TAM: it helped orientation and the contribution process and "increased newcomers' confidence", but "was not effective in lowering technical barriers". ([ICSE 2016 PDF](https://www.ime.usp.br/~gerosa/papers/ICSE2016.pdf)) **Lesson for us:** a guidance tool can fix orientation and social barriers; the technical barriers (env setup, build, finding the code) need code-level help, which is exactly the gap the brief already flags ("no codebase-understanding help once a repo is chosen").
- **Mentors have barriers too (Balali et al., CSCW 2018):** 44 barriers; 19 affect mentors, 34 affect newcomers, 9 both; 66% are social. ([eusset record](https://dl.eusset.eu/items/0bebd066-4488-4509-b57b-582c1c8faed1/full)) Implication: anything we tell a beginner to do should reduce, not add, mentor load.

### 1.2 Task selection: which starter tasks actually get merged

**Turzo, Sultana, Bosu, "From First Patch to Long-Term Contributor" (TSE, arXiv v2 Mar 2025).** Two-stage: SLR of 16 papers yielding 15 task-related recommendations, then logistic regressions over 5 Gerrit projects (Android, LibreOffice, oVirt, Typo3, Wikimedia) and 1,155 GitHub projects split by popularity (L/M/H). ([PDF](https://arxiv.org/pdf/2407.04159))

The 15 recommendations (verbatim titles):

| Group | Rec | Evidence verdict for newcomers |
|---|---|---|
| Task selection | R1 Work on smaller tasks first and later choose larger tasks | variable dropped (collinear) |
| | R2 Work on Good First Issues (GFIs) (for GitHub projects) | supported in GitHub (M) and (H); "a newcomer working on GFI has 5.57 times higher odds" in GitHub (H); insignificant in GitHub (L) |
| | R3 Add new functionality to the project as your first contribution | **contradicted** on GitHub (M),(H); supported only in Android. "we recommend that newcomers, particularly those contributing to OSS projects on GitHub, do not start with new features" |
| | R4 Start your contribution by working on minor bug fixes | supported in 7 of 8 datasets (Android bug fixes: 2.41x odds) |
| | R5 Work on changes where the number of files involved are few | variable dropped (collinear) |
| | R6 Start your contribution by performing less complex tasks | supported in 4 datasets; **newcomer-specific** (reverses for non-newcomers) |
| | R7 Start your contribution by working on documentation changes | supported in 5 of 8; **newcomer-specific**; "after a few documentation changes are accepted, we recommend that joiners... focus on non-documentation changes if they want to become long-term members" |
| | R8 Work on changes where fewer lines need to be added | supported in 7 of 8 |
| | R9 Work on changes where fewer lines need to be deleted | supported in all 3 GitHub sets; contradicted in Android/oVirt; **newcomer-specific** |
| Task preparation | R10 longer title / R11 longer description / R12 readable title / R13 readable description | insignificant or negative; explanatory power < 0.2%: "we recommend that newcomers focus on code quality rather than spending a lot of effort to improve the title/description" |
| Task completion | R14 Be proactive by quickly responding to questions or suggestions | context-dependent but, with R15, "have high explanatory powers across all datasets and are important predictors" |
| | R15 Be patient and focus on addressing review suggestions | supported across all Gerrit projects and GitHub (M) |

**Tan, Zhou, Sun, "A First Look at Good First Issues on GitHub" (ESEC/FSE 2020):** 9,368 GFIs across 816 projects; "almost half of GFIs are not solved by newcomers"; GFIs take longer to resolve than ordinary issues. ([FSE 2020 record](https://2020.esec-fse.org/details/fse-2020-papers/172/A-First-Look-at-Good-First-Issues-on-GitHub))

**Hoshikawa et al., "A Longitudinal Analysis of Good First Issue Practices" (EASE 2026):** 406,826 issues and 1,117 newcomer GFI PRs across 37 popular repos, July 2021 to June 2025. GFI ratio stable (~0.9% of issues) for three years then a significant drop after January 2024 (0.91% to 0.63%, a 31% decrease); 23% of repos declining, 70% flat, 7% rising. Newcomer engagement with GFIs stable at ~27%, but "73% of GFIs did not receive a newcomer PR". Newcomer GFI PR merge rate 61.9% (Y1) to 42.2% (Y4); bug-fix PRs highest (68.7%), features stable (54.4%), docs 68.4% to 47.7%. Description length +57% with "no significant association with merge outcomes". Case notes: "yt-dlp/yt-dlp introduced anti-spam protections in August 2024, after which GFI labeling dropped sharply, and godotengine/godot assigned zero GFI labels for 17 consecutive months while updating its contribution guidelines to mitigate spam". Advice to newcomers: "seek out projects and maintainers that actively support contributions, and proactively engage with reviewer feedback once a PR is submitted." ([PDF](https://arxiv.org/pdf/2604.27532))

**Steinmacher et al., "Understanding and Supporting the Choice of an Appropriate Task to Start with" (HICSS):** interviews across projects; the core finding is *lack of confidence to choose*: "I really didn't know which one to pick, which one I was 'authorized' to pick... whether they are important"; experienced members counter that "newcomers do not know how to reduce the scope" and "the newbie thinks she'll be able to implement it in a few days". Three information defects in issues: outdated issues, no required-skills info, no difficulty info. Strategy table (Table 5): list easy tasks by difficulty / by required skills / by topic; list of mentored bugs; mentorship per subproject; a form to send goals+skills requesting a task; examples in easy bugs; recommend related artifacts; recommend similar bugs. ([PDF](https://www.ime.usp.br/~gerosa/papers/Understanding_and_Supporting_the_Choice_of_an_Appropriate_Task_to_Start_with_in_Open_Source_Software_Communities.pdf))

**Personalised first-issue recommendation (Xiao et al. 2023):** newcomers' choices depend on expertise preference, OSS experience, activeness and sentiment; a personalised recommender beats generic GFI recommenders. ([arXiv 2308.09038](https://arxiv.org/abs/2308.09038v1)) Our `recommend` is "shallow" precisely because it only uses language.

### 1.3 Mentoring on GFIs and time-to-first-response

**Tan et al., "Is It Enough to Recommend Tasks to Newcomers?" (ICSE 2023):** 48,402 GFIs from 964 repos (top 1% by GFI count). Findings:
- ~70% of GFIs have expert participation (experts = top 20% contributors); 43.63% have both newcomer and expert comments; 10.36% newcomer-only.
- Response time: 25% of GFIs get an expert comment within 41.25 minutes of the newcomer's comment; half within 8.5 hours; "the response time for a few of them is more than two months".
- Four mentorship structures: centralized 29%, decentralized 15%, collaborative 36%, distributed 20%.
- 14 newcomer challenges and 18 expert mentoring behaviours (Table II). Top-difficulty challenges by newcomers' own rating: **"unclear how to start" and "no response"**; also environment setting, unclear issue goal, reproducing, branch conflicts, CI, "unclear how to link PR and issue". Experts rank "minor issues (code style, typos, changelog)" as *often* occurring even though newcomers think they are easy.
- Expert support newcomers rate "very important": clarification of the issue, pointing out target files/code, examples/references, inline comments, pointing out errors/limitations, contributing-guideline clarification.
- Expert involvement is associated with a **71% increase** in newcomers' initial success. Newcomers who comment more on the GFI are more likely to solve it. But expert involvement is *negatively* correlated with later retention, which the authors read as: those who succeed unaided have stronger ability/willingness; still, 64.4% of retained newcomers had expert participation.
- Etiquette quote from an expert: "please do not 'Resolve' Comment. The person who has started the conversation should resolve the comment. And you should always reply to comments". Another expert redirecting a newcomer from a taken issue: "sounds good, please check some unassigned issues from here... There certainly can be one that you'd like to work on :)". ([PDF](https://arxiv.org/pdf/2302.05058))

**Jensen, King, Kuechler (HICSS 2011):** eight mailing lists in MediaWiki, GIMP, PostgreSQL, Subversion; ~80% of newbie posts got replies; replies, "especially within 48 hours", positively correlated with future participation; 1.5% of responses rude/hostile. ([flosshub](https://flosshub.org/node/1481))

**Mozilla (2014 wiki):** "we know that prompt review of a patch is strongly correlated to contributor retention"; goal to "Maintain a list of minimum of 40 good first bugs with active mentors at all times" and 30 "good next bugs"; "When a patch is r+'ed, contributors should be guided towards their next bug." ([wiki.mozilla.org](https://wiki.mozilla.org/Contribute/Coding/Pathways)) The "48h / 7 days" figures attributed to Mike Hoye are **unverified** (only on the Ansible wiki).

### 1.4 What integrators accept, and why PRs die

**Gousios et al., integrator perspective (ICSE 2015; 749 integrators), via Colyer's summary:** acceptance driven by quality (style, documentation, granularity, convention compliance), project fit, timeliness, tests/CI. Rejection reasons: technical quality 85%, test failures 55%, not following project conventions 48%. Prioritisation: urgency, type (bug fixes first), feature status, size/complexity, age. Integrator quotes: "well written commit messages; one commit about a single subsystem, each commit compiles separately"; "Performance related changes require test data or a test case"; challenge: "Telling people that something is wrong without hurting their feelings". ([acolyer summary](https://blog.acolyer.org/2015/06/23/work-practices-and-challenges-in-pull-based-development/)) Large replication (3.3M PRs, 11,230 projects): whether the integrator is the submitter is the top factor; CI failed-build percentage matters when CI is used. ([Zhang, Yu, Gousios, Rastogi 2021](https://arxiv.org/pdf/2105.13970.pdf))

**Steinmacher, Pinto, Wiese, Gerosa, "Almost There" (ICSE 2018):** 21 projects; 10,099 quasi-contributors (~70% as many as actual contributors) with 12,367 unmerged PRs; 85% tried exactly once. Reasons given by quasi-contributors (mentions / % who disagreed with the decision): superseded/duplicated 52 (13%), mismatch of vision 45 (60%), PR not needed 37 (22%), lack of integrator interest 25 (72%), not optimal solution 24 (8%), lack of experience/commitment 20, side effects 12, lack of tests 11, incomplete 10, WIP 7, obsolete 6. 67.4% agreed with the non-acceptance; 88.8% found comments constructive; 30.3% were demotivated. Observations: "No tests, no fun" (Bootstrap closes test-less PRs "no questions asked"); "Typos are sometimes hard to fix" (a one-comma PR rejected; integrators call such PRs "noisy"); "The fast development cycle hinders external contributions" (a PR obsolete within days); some rejected PRs were re-implemented by integrators. Advice to newcomers: "work closely with integrators, and, when necessary, stand and argue for their contributions... investigate whether there are existing pull-requests proposing the same contribution... back up their contributions with tests... make sure that their contributions do not introduce side effects." ([PDF](https://www.ime.usp.br/~gerosa/papers/icse2018-Pinto.pdf))

### 1.5 What predicts retention

- **Zhou & Mockus (TSE 2015, Mozilla + GNOME):** newcomers who had at least one issue they reported fixed within the first month roughly doubled their odds of becoming long-term contributors; low peer attention reduced the odds; **high project popularity reduced the odds**; model precision 38x random. ([core.ac.uk](https://core.ac.uk/works/174176176)) The 2012 ICSE paper frames this as "willingness and opportunity" ([pkuscholar](https://pkuscholar.onrender.com/conf/icse/ZhouM12)).
- **GSoC-specific (Silva, Wiese, German, Steinmacher, Gerosa, ICSME 2017):** mining commits of GSoC students: 23.1% of newcomers contributed to the project before knowing they were accepted; ~43% kept contributing >1 month after GSoC, ~26% >6 months, ~16% >1 year; students with prior experience 47/33/23%. "~64% of the students did not stay later than a month after the program." Commit volume during GSoC correlates with later contribution. ([PDF](https://www.ime.usp.br/~gerosa/papers/08094410.pdf))
- **Motivations (JSS 2020) and theory (FSE 2020):** students join for learning, career building (44% cite adding GSoC to the CV), stipends; "not necessarily to become frequent contributors". Communities use strategies to plan participation, socially integrate students and reward them; the paper proposes non-monetary rewards (certificates, "seals of contribution") to increase participation. ([JSS](https://par.nsf.gov/servlets/purl/10158681), [arXiv 1910.05798](https://arxiv.org/pdf/1910.05798.pdf))
- **Google's own numbers measure intent, not behaviour:** 2023: "99.84% of contributors plan to continue working on open source and 97.81%... will continue working with their GSoC organization". ([Google 2023](https://opensource.googleblog.com/2023/12/google-summer-of-code-2023-final-results.html))
- **Trainer et al. (JORS 2014, Biopython):** GSoC's outcomes were new features, training, personal development; mentors struggle with project selection/ranking; "the intensive mentoring process facilitates creation of strong ties". ([DOAJ](https://doaj.org/article/313a2a5a86934a01929ef79ac8ae92b5))

### 1.6 Octoverse

- 2019: "1.3 million made their very first contribution to open source". ([GitHub blog](https://github.blog/news-insights/octoverse/the-state-of-the-octoverse-2019/))
- 2023: "commercially backed open source projects capture the largest share of first-time contributors"; brand recognition drives it; onboarding programs named: freeCodeCamp, First Contributions, GitHub Education. No GFI findings. ([Octoverse 2023](https://github.blog/news-insights/research/the-state-of-open-source-and-ai/))
- 2024/2025: no first-time-contributor count found (**unverified**).

---

## 2. GSoC's own guidance (what we must align to)

Official pages, with the lines that matter for our features:

- **Student advice** ([developers.google.com](https://developers.google.com/open-source/gsoc/help/student-advice)): "Pick 3-5 orgs to research in depth." "Narrow your list down to 1 or 2 orgs, and then get involved with them. TALK TO THE ORG!" "File a bug. Better yet, send a patch or pull request." "An organization won't accept a person based solely on a nice proposal." "Limit yourself to one or two. Quality is more important than quantity." "Over 94% of people accepted last year submitted 2 or fewer proposals." "DO NOT WAIT UNTIL THE LAST MINUTE TO APPLY."
- **FAQ** ([faq](https://developers.google.com/open-source/gsoc/faq)): up to three proposals, one accepted; sizes ~90/175/350 hours; end dates extendable to 22 weeks; "stipend payments are based on passing the evaluation, not code implementation"; AI-written proposals "could result in an automatic rejection by the organization".
- **Responsibilities** ([responsibilities](https://developers.google.com/open-source/gsoc/help/responsibilities)): contributor must "Give indication that you are alive and working daily", share completed work/next steps/blockers regularly, re-evaluate scope when ahead/behind; mentor standard "At least twice a week or better".
- **Making first contact** ([guide](https://google.github.io/gsocguides/student/making-first-contact)): join lists and spend "a few days just reading the conversations"; read archives; read past GSoC projects; work through docs so your questions are not already answered; "at least a few legitimate questions" before offering opinions; stay humble "for at least a few months"; "Don't wait for the application period to make contact."
- **Communication best practices** ([guide](https://google.github.io/gsocguides/student/communication-best-practices)): "Never private-message (pm) someone that you don't know without first asking if it is OK in the public channel." "Never send community members unsolicited personal messages." "Never reach out to mentors during the application period via social media like LinkedIn". "Don't use the mailing list as your own personal Google." "Always read the entire thread before replying." "Remember that other peoples' time is just as valuable as your own."
- **Writing a proposal** ([guide](https://google.github.io/gsocguides/student/writing-a-proposal)): elements: Name/Contact, Title, Synopsis, Benefits to Community, Deliverables ("brief, clear work breakdown structure with milestones and deadlines"), Related Work, Biographical Information, Follow the Rules. "Using AI-generated materials is an automatic reject for some orgs." "Under-scoping is an annoyance. Incomplete is a disaster." "Submit your proposal early... the more time they have to give you feedback". "Only propose to write something yourself if you cannot get it any other way."
- **Finding the right project** ([guide](https://google.github.io/gsocguides/student/finding-the-right-project)): "Formulate your questions and suggestions regarding each idea into a clear and concise communication"; mentors "will have lots of ideas and preconceptions"; separate critical from optional; mock-ups help.
- **Being turned down** ([guide](https://google.github.io/gsocguides/student/being-turned-down)): "Mentors may not be available"; orgs "receive over 100 proposals"; "it is okay to politely ask for" feedback; questions to ask: skills mismatch? enough community engagement? plan clear?
- **Head start / working with your mentor / time management** ([head start](https://google.github.io/gsocguides/student/how-to-get-a-head-start), [mentor](https://google.github.io/gsocguides/student/working-with-your-mentor), [time](https://google.github.io/gsocguides/student/time-management-for-students)): set up env, "Do a few practice commits", "Set up a blog"; agree "regular meetings, reports, code check-ins and any planned time off"; "Avoid working for two weeks on a chunk of code that is headed in the wrong direction"; if no mentor response "within 5 days" escalate to secondary mentor/org admin; "Have mini-goals for each week"; keep a progress log.
- **Evaluations / work product** ([evaluations](https://google.github.io/gsocguides/student/evaluations), [work product](https://developers.google.com/open-source/gsoc/help/work-product)): final report must include goals, what you did, current state, what's left, what merged/not, challenges learned; "The URL cannot be changed after submission"; best form "blog post, web page, or public GitHub gist"; unacceptable: tarballs, links to the main repo, your clone, or the GSoC project page.
- **AI guidance (updated 2026-02-19)** ([ai_guidance](https://developers.google.com/open-source/gsoc/resources/ai_guidance)): "Some organizations do not allow any use of AI tooling, including in the writing of proposals." "The human contributor retains 100% responsibility for the work." "Use AI tools mostly for research and less for code generation." "When developers blindly use AI tools to generate code they often don't understand what was generated."
- **How orgs filter AI/spam proposals (admin page, updated 2026-02-26)** ([spam_proposals](https://developers.google.com/open-source/gsoc/resources/spam_proposals)): require joining the chat and filter those who are not on it; keep a per-individual spreadsheet ("Keep the focus on individuals - not the proposals"); require links to 1-3 meaningful contributions; require a draft before formal submission and check edit dates; combine prerequisites (contact org, 2-3 PRs, template); templated 4-5 specific questions, auto-disqualify missing answers; search for placeholders and "signal words" like "revolutionize"; "typos are good - they are human"; 1-minute video intro; look for paraphrased ideas-list text; "Super pretty proposals are more likely to be AI-generated." **This page is effectively the rubric applicants are graded against and we should mirror it.**

Org-level AI policies seen: SW360 bans AI for the idea, allows formatting ([eclipse.dev/sw360](https://eclipse.dev/sw360/gsoc/ai-policy/)); CRIU rejects LLM-generated proposals but allows brainstorming/editing ([criu.org](https://criu.org/Special:MobileDiff/5613)); SymPy has a mandatory PR template with AI disclosure ([sympy list](https://groups.google.com/g/sympy/c/tBsrcNYHxFU)).

---

## 3. Maintainers in their own words (for templates and ethics copy)

- **stdlib, GSoC 2024 retrospective** ([dev.to](https://dev.to/stdlib/reflecting-on-gsoc-2024-5doa)): after acceptance announcement "over 1,000 PRs, more than 100 unique PR contributors" for four slots. GFIs "resulted in a very high number of low-quality submissions"; "Having a bunch of trivial issues provides weak signal"; complex issues "were often too complex"; "non-stop barrage of messages per day"; "AI has also led to a flood of low-quality PRs generated by AI tools"; an applicant "tried to sabotage a fellow applicant by impersonating them on Gitter"; "We found that it's best to avoid assigning issues to anyone via the respective GitHub feature". What worked: weekly office hours ("only individuals who were genuinely interested in the project attended"), a devcontainer, automated setup-help comments, "well-defined, incremental issues that serve as stepping stones". Advice: "start interacting with the community and codebase well before the application period... This is probably the biggest hack to get selected"; "contributors who clearly demonstrate an ability to receive and act on feedback will stand out"; "Clean PRs requiring little-to-no review feedback significantly improve the odds"; "Maintainers are human, and they are more likely to invest in you, the more you show you care about them."
- **Jenkins org admin, 2022** ([community.jenkins.io](https://community.jenkins.io/t/message-to-gsoc-2022-applicants/2533)): "A common proposal weakness was the lack of enough substance or depth." "Mentors couldn't judge whether the candidate understood the problem to solve." "Clearly explain what you intended to do in your PR and request guidance". "Don't hesitate to ask if you have doubts."
- **SymPy, Aug 2026 thread** ([groups.google.com](https://groups.google.com/g/sympy/c/tBsrcNYHxFU)): "sympy has a few thousand open issues. Have a look and pick one you think is interesting and managable for you." Don't wait for "easy to fix" labels, triage is backlogged; "play around with the code and understand roughly how things work"; "it will not be very useful to ask vague or broad-scoped questions about GSoC on the mailing list"; prefer "Specific and more focused questions, probably framed around your own work and findings"; on AI: "It will be caught even if you fail to mention it on the mandatory PR template" and the PR "will either be ignored or closed."
- **Joplin, GSoC first PR guide** ([discourse.joplinapp.org](https://discourse.joplinapp.org/t/creating-your-first-gsoc-pull-request/15795)): fix a high/medium priority bug or build a small plugin; "make sure the issue you choose has a very clear technical spec"; do not "submit a pull request just to fix some typo"; if a PR needs design discussion "we are likely to close the pull request".
- **Kubernetes contributor guide** ([kubernetes.dev](https://www.kubernetes.dev/docs/guide/first-contribution/)): claim with "/assign"; "Beware that every pull request creates work for maintainers and costs for testing it"; linter-warning PRs: "Always discuss with maintainers first".
- **pandas** ([contributing](https://pandas.pydata.org/docs/development/contributing.html)): "leave a comment with your intention to start working on it"; may take over if the previous claimant shows "a lack of activity in the issue or a pull request in the past 2-3 weeks"; "please leave a comment on an issue, so other people know it's available again".
- **Julia Discourse** ([julialang](https://discourse.julialang.org/t/getting-started-for-gsoc/52865)): "There is a good first issues tag"; "your focus would probably not be to contribute to base, but rather to write or contribute to a package".
- **Multi-year GSoC mentor (2025)** ([substack](https://innovationstrategymentor.substack.com/p/applying-to-google-summer-of-code)): looks for someone "who seems reliable enough to get through the project"; "Prioritize 2-3 organizations and reach out ASAP"; multiple generic applications "especially if they are to the same org, or clearly GPT/GenAI generated" signal weak seriousness; "if you simply throw things at GPT and then copy and paste it into a doc... we can tell"; "Identify how to record and measure project progress."
- **Godot (via secondary reporting, 2026, unverified wording):** Rémi Verschelde called the surge of AI PRs "draining and demoralizing": "was the code even partially written by a human, did the author understand it, did they test it?" ([opensourceforu](https://www.opensourceforu.com/2026/02/github-weighs-pull-request-kill-switch-as-ai-slop-floods-open-source/))
- **Drew DeVault** on stale bots ([drewdevault.com](https://drewdevault.com/blog/stalebot/)): an issue is "a place for motivated users to collaborate on narrowing down the problem and planning a potential fix"; "There is no shame in having a lot of open issues". On Hacktoberfest 2020 ([Spamtoberfest](https://drewdevault.com/blog/Spamtoberfest/)): DigitalOcean's FAQ placed "the burden of dealing with it entirely on the maintainers"; his alternative is mentorship, pointing to GSoC as the better model.
- **Steinmacher's interviewed core members** ([JCSCW](https://www.ime.usp.br/~gerosa/papers/JCSCW_Steinmacher.pdf)): "You cannot wait for other people. You have to be willing to study new stuff by yourself." "when a newcomer asks, we want to see that he or she did some research before asking."

---

## 4. Adjacent ecosystems: project records and what to borrow

### 4.1 Exercism mentoring model
- URL: https://exercism.org/docs/mentoring ; code: [exercism/website](https://github.com/exercism/website) (AGPL-3.0, 550 stars, Ruby, pushed 2026-10-16; the product has far more users than the repo stars suggest).
- How it works: a student submits an iteration and a mentoring request stating what they want; a volunteer mentor replies with "the most important one to three pieces of feedback on any iteration"; the student iterates; "Conversations tend to be more productive when they are approached as two peers discussing a topic". Student guide: growth mindset, "sometimes it might take a couple of days before they'll have chance to get back to you", work on something else while waiting, "It's always better to walk away from a conversation than getting into an argument". ([give great feedback](https://exercism.org/docs/mentoring/how-to-give-great-feedback), [guide to being mentored](https://exercism.org/docs/using/feedback/guide-to-being-mentored))
- Borrow: (a) the *request* is structured: the learner states what they want feedback on; our claim/PR templates should carry a "what I want reviewed" line. (b) "1-3 things per iteration" is a good self-review discipline and matches R15 (patience). (c) Explicit "mentors are volunteers; days, not hours" expectation copy.
- Avoid: Exercism's model assumes a dedicated mentor pool; GSoC applicants have none, so do not promise "a mentor will respond".

### 4.2 roadmap.sh
- [kamranahmedse/developer-roadmap](https://github.com/kamranahmedse/developer-roadmap) (redirects to nilbuild/developer-roadmap), ~370k stars, TypeScript, license listed as "Other" by GitHub (check before reuse), pushed 2026-10-20. "Roadmaps are now interactive, you can click the nodes"; separate *beginner* variants of each roadmap; a "get started" page to pick a path. ([README](https://github.com/kamranahmedse/developer-roadmap))
- Borrow: the beginner/full split (our journey could expose a 4-phase "beginner" path and the full 10-phase path); clickable nodes each with "why / resources / done criteria" (our PHASE_GUIDES already have goal/actions/success, so a rendered node view is cheap).
- Avoid: generic, non-personalised nodes; roadmap.sh does not use the user's own repos or an org's reality.

### 4.3 Hacktoberfest's anti-spam evolution (2014 → 2020 → 2026)
- 2014: "open four pull requests in October, earn a t-shirt". 2020: a viral low-effort-PR video; initial response put labelling burden on maintainers ("Spammy pull requests can be given a label that contains the word 'invalid' or 'spam'"), then from 3 Oct 2020 opt-in: only repos with the `hacktoberfest` topic, PRs merged/approved/labelled `hacktoberfest-accepted` count; later years: two spam-labelled PRs = disqualification (secondary sources; official 2025 wording not retrieved). ([developerrelations.com case study](https://developerrelations.com/case-studies/overcoming-hacktoberfest-spam), [dev.to](https://dev.to/adiatiayu/hacktoberfest-making-it-enjoyable-for-contributors-and-maintainers-54gk))
- **2026: PRs no longer count at all.** "Pull requests and merge requests will no longer count toward Hacktoberfest rewards. It's easier than ever to submit low-effort spam PRs to projects, so we're listening to maintainer feedback and no longer actively incentivizing PRs." "open source was never defined by a PR counter." ([hacktoberfest.com/llms-full.txt](https://hacktoberfest.com/llms-full.txt))
- Borrow: the opt-in principle. Our issue search already restricts to GSoC orgs; add an explicit "this repo/org opted into newcomers" signal (GFI labels used in the last 90 days, CONTRIBUTING mentions newcomers, office hours). Treat "two spam PRs = disqualified" as the behavioural model to explain to users: reviewers remember.
- Avoid: counting PRs anywhere in our UX.

### 4.4 Outreachy's application process
- [outreachy.org/docs/applicant](https://www.outreachy.org/docs/applicant/): initial application (eligibility + five essays) → contribution period (4 weeks) → final application. "Only applicants who make a contribution will be eligible to be selected as an intern." Contributions are *recorded on the site* and editable. Mentors evaluate: "Have your contributions shown you can complete complex work?" "Do you communicate in a clear, welcoming, and professional manner?" "Have you asked for help when stuck in a timely manner?" whether you help other applicants. Rules: "All applicants need to be the first one to reach out to mentors"; stuck "more than a couple of hours" → ask; try public channels if private messages are unanswered; "We don't recommend applying to more than two projects"; avoid "big, last minute contribution"; final application asks for a timeline with milestones "at least every two weeks"; AI use must be documented (tool, version, prompts) and explainable.
- Internship ([docs/internship](https://www.outreachy.org/docs/internship/)): weekly real-time mentor meeting; interns "required to blog every two weeks"; three mandated reports with prompts (introduce yourself/community/project, "List your proudest contributions"; mid-point: progress with links, "adjustments to project scope, timeline or tasks"; final: results and "career prospects and post-internship plans"); blogging "shouldn't take more than 1-3 hours".
- Borrow: the **recorded-contribution ledger** (the single best idea in this stream for our "contribution-evidence collection for proposals" gap), the "asked for help in a timely manner" criterion, the "help other applicants" criterion, the two-project cap, and the report prompts.

### 4.5 Linux kernel "first patch" tutorial
- [kernelnewbies.org/FirstKernelPatch](https://kernelnewbies.org/FirstKernelPatch): task discovery is *mechanical*: run `checkpatch.pl --strict` on a staging driver and pick one CHECK/WARNING; "For your first patch, only pick one change"; recipients from `get_maintainer.pl` ("If you simply send it off to linux-kernel@vger.kernel.org, it will get ignored"); send the first patch to yourself as a test; respond inline; resend as `[PATCH v2]` with a changelog below `---`; "Do not include a version change log in the patch description"; avoid licence-warning patches and `CONFIG_BROKEN` drivers.
- Borrow: a deterministic "find a legitimate micro-task" generator per repo (lint/`--strict` output, failing docs examples, missing tests) *only when the project explicitly welcomes such cleanups* (the kernel does; Kubernetes says discuss linter fixes first). Also the "rehearse the send" idea: dry-run your PR description through a checker before posting.

### 4.6 Contributor ladders (CNCF, Apache)
- [cncf/project-template CONTRIBUTOR_LADDER.md](https://github.com/cncf/project-template) (Apache-2.0, 82 stars, pushed 2026-08-11): roles Community Participant → Contributor → Organization Member → Reviewer → Maintainer, each with Responsibilities / Requirements / Privileges; "Contributions need not be code"; Contributor requirements include "Answer questions from other community members", "Test releases and patches and submit reviews", "Show up at meetings, takes notes".
- [cncf/mentoring](https://github.com/cncf/mentoring) (Apache-2.0, 3,123 stars, pushed 2026-10-19): mentors/mentees guidance; stats: 2025 LFX 176 mentorships vs GSoC 11, the CNCF now runs far more mentorships through LFX than GSoC (useful "alternative path" datum for users).
- Apache: ladder user → developer → committer → PMC member; "A committer is a developer who has write access"; "how people respond [to your intro] can be a good indicator of how welcoming the project is"; non-code contributors get "the same rights and privileges". ([how it works](https://www.apache.org/foundation/how-it-works/), [community.apache.org](https://community.apache.org/contributors/))
- Borrow: show the user the project's ladder (if `CONTRIBUTOR_LADDER.md`/`GOVERNANCE.md`/`MAINTAINERS` exist) and frame GSoC as a rung, not the goal; count non-code acts (triage, review, answering) as evidence in the ledger.

### 4.7 Recognition and welcome bots
- **All Contributors** ([spec repo](https://github.com/all-contributors/all-contributors), MIT, 8.1k stars on the org site repo): "recognizing contributors... in a way that rewards every contribution, not just code"; emoji key for contribution types; bot invoked from comments. Borrow: the contribution-type taxonomy for our ledger (code, doc, test, review, question, bug, ideas, maintenance, mentoring...).
- **actions/first-interaction** (MIT, 899 stars, TypeScript, pushed 2026-01-21): posts a configurable comment on a first-time contributor's first issue/PR. ([README](https://github.com/actions/first-interaction)) Borrow: detect its presence in a repo's workflows as a "welcomes newcomers" signal.
- **actions/stale** (MIT, 1,722 stars, pushed 2026-10-17): defaults "Stale" after 60 days, close after 7 more; "If an update/comment occur... the stale label will be removed and the timer will restart." ([README](https://github.com/actions/stale)) Interaction with availability: a stale label is *not* evidence the task is unwanted (DeVault), and any "is this still open?" comment resets the timer, so claim-comments can keep zombie issues alive; a GFI that was auto-closed by stale may be reopenable. Borrow: parse `.github/workflows/*.yml` for `actions/stale`, `first-interaction`, and the `days-before-stale` value; show "stale-bot: 60d/7d" in `repo` and treat `stale`-labelled GFIs as "ask before working".
- **first-timers-only** ([firsttimersonly.com](https://www.firsttimersonly.com/), [Kent C. Dodds' post](https://kentcdodds.com/blog/first-timers-only)): the label means "I'm willing to hold your hand so you can make your first PR", "This issue is a bit easier than normal", "anyone who's already contributed to open source isn't allowed to touch this one!"; maintainers "Say exactly where the code needs to go and recommend a good approach"; a First Timers app turns `first-timers-*` branches into fully-formed issues. Borrow: treat `first-timers-only` as top-tier availability for true newcomers; and the *format* (exact file, exact change, steps) is what our future issue→code pointers should emulate.
- **firstcontributions/first-contributions** (MIT, 56k stars, pushed 2026-10-21): a practice repo whose whole flow is "add your name to Contributors.md" then "Congrats! You just completed the standard fork -> clone -> edit -> pull request workflow". ([README](https://github.com/firstcontributions/first-contributions)) Borrow: offer it as the *sandbox* for git mechanics so that users never practise on a real org's repo (this directly reduces "add my name" vanity PRs, which our quality bar already bans).

### 4.8 Reflection practices used by GSoC programs
- python-gsoc.org: weekly public status posts answering "What did you do this week?", "What is coming up next?", "Did you get stuck anywhere?"; "If you do not post consistently, we may assume that you have gone inactive"; limit 4,004 chars. ([blogs.html](https://python-gsoc.org/blogs.html))
- Outreachy: see 4.4. GSoC guide: "Set up a blog"; keep a progress log; "Have mini-goals for each week". GSoC work product: required contents listed in section 2.

### 4.9 Streak/habit tools
- Evidence is thin and mostly vendor-reported (Duolingo's "2.4x more likely to return after a 7-day streak" is unverified). Academic work by Jackie Silverman recommends emphasising intact streaks and offering "streak repair"; a 2021 *Computers in Human Behavior* study (cited second-hand, unverified) links rigid streaks to guilt and abandonment. ([podcast summary](https://pocketcasts.com/podcasts/35f14df0-e276-0135-c259-7d73a919276a/cef26964-b0ba-4439-a057-6cf555fe30fc), [Smashing Magazine](https://shop.smashingmagazine.com/2026/02/designing-streak-system-ux-psychology/))
- Verdict: **no daily streaks.** A weekly cadence with "repair" (log last week late, no penalty) matches python-gsoc/Outreachy and avoids the guilt failure mode. Streak-like feedback that *is* grounded: "weeks with at least one public interaction" (which is what mentors actually see).

### 4.10 Automated first-issue recommenders
- GFI-Bot (PKU) could not be resolved on GitHub (**unverified**); Xiao et al. (2023) describes the personalised approach. Our `issues` already does availability verification, which the recommenders do not; the missing half is personalisation (skills, prior experience, activity) and the evidence-based ranking in section 1.2.

---

## 5. What beginners get wrong (from applicants' and orgs' posts)

| Mistake | Source and detail | Fix we can ship |
|---|---|---|
| Choosing an org that then is not accepted / first-year org with 3-4 ideas | "Four months of work, pointed at an arena that wasn't open"; "competing for maybe one or two seats per org without realizing the board was that small" ([dev.to, undated](https://dev.to/aswanisahoo/5-mistakes-that-cost-me-gsoc-and-lfx-1g5a)) | `org` shows years participating, slot history, first-year flag; `discover` advises 2-3 orgs with continuity |
| Side idea vs flagship | "when slots are scarce, a strong proposal on a minor idea loses to an average one on the flagship" (same) | Flag the flagship idea (most-mentioned repo/idea, repeated across years) |
| Treating all orgs the same | "Proposal-first orgs and code-first orgs are different sports" (same) | Classify orgs: required prereqs (PR count, template) parsed from ideas page / CONTRIBUTING |
| Hopping orgs, one PR by end of January, inactive on channel | 2020 story ([substack](https://swiftlysingh.substack.com/p/gsoc-proposal-rejected-my-story-a635a01e014f)) | Weekly log with "public interactions this week" and a commit-to-org checkpoint |
| Exam overlap / over-planning | "I was busy, not effective" (dev.to) | Time-budget planner with exam dates |
| Shallow proposals | "lack of enough substance or depth" (Jenkins) | Proposal checklist item: "explain *how*, per milestone, with code pointers" |
| Multiple generic / AI proposals | Google admin page; mentor substack | Refuse to generate proposals; detect ideas-list paraphrase in user's draft |
| Waiting for labels / vague questions | SymPy: don't wait for "easy to fix"; ask "Specific and more focused questions" | Question template requires "what I tried" |
| "Please assign me" / claim without plan | stdlib stopped assigning; pandas wants intention + activity; K8s uses `/assign` | Claim-comment template; detect project's claim convention |
| Giant first PR / new feature first | R3 contradicted on GitHub; Joplin closes PRs needing design discussion | Issue scoring penalises features, rewards bug/small |
| Typo-only PRs | Joplin: "don't submit a PR just to fix some typo"; "Typos are sometimes hard to fix" (ICSE 2018) | Already in quality bar; add "docs fixes must be verified by running the example" |
| DMing mentors, LinkedIn | GSoC communication guide | Already in rules; add to intro template |
| Not responding to review / resolving others' comments | Tan 2023 quote; R14/R15 strongest predictors | New `iterate` phase; review-reply etiquette |
| Impersonation, sabotage | stdlib | Out of scope, but reinforces "public channels only" |

r/GSoC threads could not be fetched; the above is from blogs, Discourse, mailing lists and org retrospectives, with dates where available.

---

## 6. Answers to the key questions

### 6.1 Are our eight phases mis-ordered or missing anything?

Current: `learn → discover → evaluate → find_issues → contribute → community → proposal → track`.

Problems, each with evidence:
1. **`community` is too late.** Every authority puts first contact *before* task selection: GSoC guide (lurk, read archives, ask "at least a few legitimate questions"), Outreachy ("be the first one to reach out"), Google ("TALK TO THE ORG"), Steinmacher ("Keep the community informed... send a comment in the issue"), Apache (introduce yourself and say what you want to work on). Tan 2023 shows experts redirect newcomers to unassigned tasks when asked, i.e. the community *is* the task-finding mechanism.
2. **No orientation phase.** FLOSScoach showed guidance helps orientation; Tan's top newcomer challenge is "unclear how to start"; stdlib's fix was a devcontainer; GSoC guide says "Do a few practice commits". Setting up the environment and reading the code deserve their own phase with a success criterion ("the unchanged project runs; I can locate the file for one issue").
3. **No iterate phase.** R14/R15 (responding, patience) have the highest explanatory power; quasi-contributors who "disappeared shortly after proposing the pull-request" lost otherwise-mergeable PRs; Outreachy judges "ability to receive and act on feedback"; Mozilla guides contributors "towards their next bug" after r+. The second contribution is also where the newcomer-specific recommendations flip (move from docs/low complexity to real code).
4. **No "ask" skill.** Asking well is a cross-cutting skill (sections 1.3, 3); it should be a reference and a template, used from the orient phase onward.
5. **`track` is mislabelled.** It describes bonding/coding after acceptance; the log habit should start in phase 1 (GSoC's own advice to blog begins at bonding, but applicants' logs are what *produce* the proposal's evidence). Rename the post-acceptance phase `deliver` (bonding, coding, evaluations, work product) and add `after` (not selected: being-turned-down playbook; selected: staying engaged).

Proposed sequence (10 phases, with the 4-phase beginner view in bold):

`learn → discover → evaluate → **orient** → **community** → find_issues → **contribute** → iterate → **proposal** → deliver → after`

(`community` stays a loop phase: it can be re-entered any time, but its *first* pass must precede claiming an issue.)

### 6.2 What should a weekly-log / reflection feature look like?

Fields (one entry per ISO week; all optional except the three python-gsoc questions):
- `week` (auto), `hours` (int; feeds project-size realism against 90/175/350 h sizes), `goal_set_last_week` (carried over).
- `did`, "What did you do this week?" with links (PRs, issues, comments, chat threads). Links are validated against GitHub and tagged by type using the All-Contributors taxonomy.
- `next`, "What is coming up next?" (becomes next week's goal).
- `stuck`, "Did you get stuck anywhere?" plus `tried` (what you tried) and `asked_where` (channel/issue URL, date; response received y/n and after how long). This captures Outreachy's "asked for help in a timely manner" and Tan's "no response" metric for the user's own experience.
- `learned`, one sentence (feeds the final report's "challenges or important things you learned").
- `public_interactions` (auto-derived count of comments/reviews by the user's GitHub login in tracked repos).
- `confidence` 1-5 ("can I explain my last change without notes?"), mirrors our "Author can walk through the change on a voice call" bar.

Cadence and tone: weekly; a missed week can be back-filled with no penalty (streak repair); the CLI shows "weeks with a public interaction" rather than a streak. Cap guidance: "15 minutes; Outreachy says blogging should not take priority over the work."

How it feeds the proposal and the final report:
- `log export --proposal` emits the "About you / prior contributions" section as a dated, linked list (exactly what Google's admin page says orgs ask for: "links to 1-3 of the applicant's most meaningful contributions") plus a measured hours/week figure for the timeline section.
- `log export --report` emits a GSoC work-product skeleton with the six required headings and the user's merged/unmerged link lists; `log export --status` emits a python-gsoc-style weekly post.
- `log summary` surfaces risk: two weeks without public interaction; a `stuck` with no `asked_where` older than 72 h ("Outreachy: ask after a couple of hours; GSoC: escalate after 5 days").

### 6.3 Presenting uncertainty and anti-spam ethics without preaching

- **Show the inbox, not the rule.** Where we currently list eight "never" rules, show numbers with sources: 23,559 proposals for 1,272 slots; stdlib's 1,000+ PRs for 4 slots; Godot's 17 months without GFI labels; Hacktoberfest ending PR counting. One line each, linked.
- **Quote the consequence from the org itself** (SymPy's "will either be ignored or closed", Joplin's "we are likely to close", Google's "automatic rejection"), pulled from the org's CONTRIBUTING/PR template when we have it, generic otherwise.
- **Make the honest path the easy path.** Templates require an evidence field (what I ran, what I read, duplicate PR check); the CLI refuses to emit a claim or PR description with those fields empty. This is how Outreachy and Google's admin page already structure the applicant side.
- **Express uncertainty as a labelled estimate with the evidence on both sides.** `issue` already does availability statuses; add "what we cannot know" (whether the maintainer will accept; whether an assignee is active) and the freshness of each datum. Use calibrated words ("likely", "no evidence either way") and never a percentage we did not compute.
- **Frame AI as responsibility, in Google's words:** "The human contributor retains 100% responsibility for the work." Offer a one-line AI-usage disclosure template for orgs that require it and detect the org's policy when a PR template or CONTRIBUTING mentions it.

### 6.4 Templates grounded in maintainers' words

**Introduce yourself (public channel, once).** Based on FLOSScoach's evaluated template ("I liked the message template, showing how to introduce myself"), Apache's "say what you want to work on", GSoC's "at least a few legitimate questions":
```
Hi, I'm <name> (<GitHub login>). I'm new to <project> and preparing for GSoC <year>.
I have read <CONTRIBUTING / the dev guide> and got <component> running locally on <OS>.
I'm interested in <area> because <one concrete reason tied to the ideas page or your use>.
I'm looking at <issue URL>; before I start, <one specific question>.
```
Rules shown next to it: public channel only (GSoC: "Never private-message someone you don't know"); no "hello" alone ([nohello.net](https://nohello.net/en/)); no "any experts around?" ([dontasktoask.com](https://dontasktoask.com/)).

**Ask a good question.** Synthesised from ESR's FAQ sections (Before You Ask; Describe the research you did; Describe the problem's symptoms, not your guesses; Describe the goal, not the step; Volume is not precision; Be explicit about your question; Follow up with a brief note on the solution, [catb.org](http://www.catb.org/~esr/faqs/smart-questions.html)), the XY problem ("Always include information about a broader picture along with any attempted solution", [xyproblem.info](https://xyproblem.info/)), Steinmacher's core-member quote, and Outreachy's timing rule:
```
Goal: <what I am trying to achieve, not the step I am stuck on>
What happens: <exact error / observed behaviour, trimmed, no private data>
Expected: <...>
Environment: <OS, versions, commit SHA>
What I tried: <2-3 bullets, including the docs/archives I searched>
Question: <one explicit question>
```
Timing copy: "Try for a couple of hours (Outreachy), then ask; after 5 days without an answer, follow up once or try the secondary channel (GSoC guide)."

**Write a good claim comment.** From pandas ("leave a comment with your intention"), Steinmacher ("inform others that you are trying to address it... inform them whenever you give up"), Tan 2023 (experts redirect to unassigned issues; "unclear about issue assignment" is a top confusion), stdlib (do not rely on GitHub assignment), Kubernetes (`/assign` where supported):
```
I'd like to work on this. I reproduced it on <commit> with <steps>; the cause looks like <file:line / hypothesis>.
Plan: <1-2 lines>. I expect a PR by <date>. If someone is already on it, tell me and I'll pick another issue.
<If the project uses a bot: /assign>
```
One comment, after reading the thread and checking `-linked:pr`; if no reply within the project's norm (pandas: 2-3 weeks of inactivity before takeover), start anyway on a fork and open a draft PR, since Joplin/Kubernetes-style projects judge the work, not the claim.

**Write a good PR description.** From Google's CL guide ("A CL description is a public record of change"; first line "short, focused, and to the point", imperative; body says what and why, "If there are any shortcomings to the approach, they should be mentioned"; "Fix bug" is inadequate, [eng-practices](https://google.github.io/eng-practices/review/developer/cl-descriptions.html)), Gousios (quality, conventions, tests), ICSE 2018 (check duplicates, tests, side effects), Jenkins ("Clearly explain what you intended to do in your PR and request guidance"):
```
Title: <imperative, < 70 chars, matches project subject conventions>
Problem: <what was broken/confusing>; Fixes #<issue>
Change: <what and why; alternatives considered; known shortcomings>
Validation: <commands run and results; new/updated tests; CI status>
Duplicates checked: <searched open PRs for ...; none / #123 superseded because ...>
Review guidance: <where to look first; one thing I'm unsure about>
<AI disclosure line if the org's template or policy requires it>
```
Size rule shown with the evidence: fewer added lines, few files, one logical change (R8, kernel "only pick one change", Gousios "one commit about a single subsystem").

**Respond to review.** "Reply to every comment; do not resolve threads you did not start" (Tan 2023 expert quote); "Try not to be defensive but rather, 'I really don't understand what you mean, would you please explain?'" (GSoC guide); push fixups promptly (R14); stand for the change when you have evidence (ICSE 2018); send a one-line note when done.

**Weekly status (python-gsoc format)** and **final report (GSoC work-product headings)**: as in 6.2.

---

## 7. Synthesis

### 7.1 Ideas worth adapting
1. Outreachy's *recorded contributions ledger* as the spine of proposal evidence.
2. Google's admin-side spam rubric mirrored on the applicant side (join chat, 1-3 linked contributions, draft early, org-specific questions answered, no ideas-list paraphrase).
3. python-gsoc's three-question weekly post as the log schema.
4. Exercism's "state what you want feedback on" and "1-3 things per iteration".
5. Kernel-style mechanical micro-task discovery, gated by the project's stated welcome.
6. first-timers-only's issue format as the target for future issue→code pointers.
7. Contributor-ladder display (CNCF/Apache) to reframe GSoC as a rung.

### 7.2 Proven patterns
- Prior public engagement before the application period (Google, stdlib, mentor blog, ICSME 2017: 23% contributed before acceptance).
- Small bug fixes / GFIs, few lines, few files, tests, conventions (Turzo 2025, Gousios, ICSE 2018).
- Prompt, public, specific communication; reply to every review comment (R14/R15, Tan 2023, GSoC guide).
- Less popular projects retain newcomers better (Zhou & Mockus; Tan 2023), "prestige" is the wrong filter.

### 7.3 Pitfalls to avoid
- Counting PRs or encouraging claim comments as activity (Hacktoberfest 2026; stdlib).
- Polishing titles/descriptions as a strategy (R10-R13 null).
- Daily streaks (guilt/abandonment risk; mentors do not see them).
- Treating stale labels or GFI labels as ground truth (DeVault; 73% of GFIs untouched; labels lag triage, per SymPy).
- Any suggestion of DMs, LinkedIn, or mass messaging.

---

## 8. Feature proposals for git-into-gsoc

Effort: S (< 1 day), M (1-3 days), L (> 3 days). Each lists the evidence that motivates it.

1. **Re-sequence the journey to 10 phases with a 4-phase beginner view** (`learn, discover, evaluate, orient, community, find_issues, contribute, iterate, proposal, deliver, after`; beginner view = orient, community, contribute, proposal). Update `JourneyPhase`, `PHASE_GUIDES`, docs/journey.md, SKILL.md. **S/M.** Evidence: section 6.1 (GSoC guide, Outreachy, Steinmacher, Turzo R14/R15, Mozilla "next bug").
2. **`log` command (weekly reflection) with evidence capture and exports** (`log add`, `log summary`, `log export --status|--proposal|--report`). Schema in 6.2; stores in the existing local JSON store; auto-collects the user's public GitHub activity in tracked repos via the search API (`commenter:USER`, `author:USER`, `reviewed-by:USER`) with ETag caching. **M.** Evidence: python-gsoc, Outreachy, GSoC work product, Google admin rubric ("links to 1-3 meaningful contributions").
3. **Contribution ledger (`evidence`)**: `evidence collect --github USER --org ORG` lists the user's PRs/issues/reviews/comments in the org's repos with state, first-response time, merge status, and contribution type (All-Contributors taxonomy); `evidence proposal-section` renders it. Also warns when evidence is all typos/docs after N merges (R7 newcomer-specific). **M.** Evidence: Outreachy recorded contributions; Google admin page; Turzo 2025.
4. **`draft` templates with mandatory evidence fields**: `draft intro|question|claim|pr|review-reply|status|final`, interactive prompts; refuses to render without "what I tried" / "validation" / "duplicates checked"; inserts the org's own claim convention (`/assign`, "take", comment) when detected in CONTRIBUTING or `.github`. Also exposed as MCP *prompts*. **S/M.** Evidence: section 6.4 sources.
5. **Evidence-weighted issue ranking and newcomer-fit signals** in `issues`/`issue`: prefer labels GFI/first-timers-only, `bug` over `enhancement`/`feature`, issues whose linked PRs historically had few insertions/files (sample last 20 merged PRs referencing GFIs in the repo), penalise "design/RFC/epic" words; show per-repo "median time to first maintainer comment on newcomer issues/PRs" and "% of GFIs with maintainer participation"; flag `stale` label and the repo's stale-bot config. **M.** Evidence: Turzo 2025 (R2/R4/R8/R3), Tan 2023 (70%, 8.5 h), Hoshikawa 2026, actions/stale defaults.
6. **Repo health: add a "newcomer responsiveness" dimension**: median first-response time to first-time contributors' PRs, % newcomer PRs merged in last 12 months, presence of `first-interaction` workflow, devcontainer (already), office-hours mention, PR template with AI-disclosure field, CONTRIBUTOR_LADDER/GOVERNANCE presence, GFI labels applied in last 90 days (supply signal). **M.** Evidence: Mozilla retention line, Jensen 48 h, stdlib retrospective, Hoshikawa GFI decline.
7. **Org selection model and slot realism** in `org`/`orgs`: first-year flag, years participating, slot count history, number of ideas, "flagship" idea (idea/repo recurring across years), parsed prerequisites ("must have a merged PR", "must use template", "join Zulip") from the ideas page and CONTRIBUTING; a "proposal-first vs code-first" hint when prerequisites mention PR counts. **M** (depends on ideas-page parsing from another stream). Evidence: dev.to "5 mistakes"; Google admin rubric; Google "3-5 research, 1-2 engage".
8. **`next` ("what should I do right now") synthesis**: combines timeline phase, journey phase, log recency (days since last public interaction), open claims without PRs, unanswered questions > 5 days, and proposal deadline proximity into three ranked actions with links. **M.** Evidence: GSoC responsibilities ("alive and working daily"), guide ("5 days"), brief's stated gap.
9. **Time-budget planner** (`plan --hours-per-week N --busy 2027-04-10:2027-04-25`): maps to 90/175/350 h sizes and 12-22 weeks, flags exam overlap with application and coding windows, and produces the weekly-milestone skeleton (Outreachy: milestones at least every two weeks). **S.** Evidence: GSoC FAQ sizes; "I was busy, not effective".
10. **Second-contribution advisor** after a first merge: suggest non-doc, slightly larger tasks in the same subsystem; explain why (newcomer-specific recommendations flip). **S.** Evidence: Turzo 2025 (R6/R7/R9); Mozilla "good next bugs".
11. **Maintainer-view pre-flight for a PR or claim** (`preflight pr --repo --branch` or paste): checks diff size (insertions/files), presence of tests, link to issue, duplicate open PRs touching the same files, convention adherence (commit subject style sampled from `git log`), and the CONTRIBUTING checklist; outputs a reviewer's-eye summary. **M/L.** Evidence: Gousios; ICSE 2018 (superseded/duplicate = top reason); kernel "send to yourself first".
12. **Ethics copy as "the reviewer's inbox" panel** in `issue`, `proposal` and the skill: five sourced numbers and three org quotes instead of eight rules; link to org policy when known. **S.** Evidence: section 6.3.
13. **Post-decision playbooks** (`after --result selected|not-selected`): not selected → polite feedback questions (GSoC guide), stay subscribed, smaller independent version, LFX/Outreachy alternatives (CNCF stats); selected → bonding checklist (env, practice commits, agree reporting cadence, blog), evaluation/work-product requirements. **S.** Evidence: GSoC guide chapters; cncf/mentoring stats; Outreachy.
14. **Sandbox pointer for git mechanics**: in `orient`, send true beginners to firstcontributions/first-contributions (or a local throwaway repo) to practise fork/branch/PR, so they never practise on a real org. **S.** Evidence: first-contributions; Joplin/ICSE 2018 on typo/vanity PRs.
15. **MCP prompts and resources**: expose `draft` templates as MCP prompts and the quality bar / official sources as resources, with annotations marking read-only tools. **S.** (Addresses the brief's MCP gap; no external evidence needed.)

### Licensing and attribution notes
We adapt ideas only; no code is copied. For the record: cncf/project-template and cncf/mentoring are Apache-2.0; all-contributors, actions/first-interaction, actions/stale, firstcontributions/first-contributions are MIT; exercism/website is AGPL-3.0 (do not copy code); developer-roadmap's license shows as "Other" on GitHub (verify before quoting content). The FLOSScoach message template comes from an academic paper (Steinmacher et al., JCSCW) and should be cited, not presented as ours. ESR's FAQ is copyrighted text; quote briefly with attribution. Google's guides are Google's; we quote short lines with links. Hacktoberfest copy is quoted from its own `llms-full.txt`.
