<!-- Research working notes. Written 2026-10-20/21 during the ecosystem research pass; kept as the evidence base for ../research.md. Claims marked unverified were not confirmed against a primary source. Plain-language rules apply loosely here; these are notes, not a guide. -->

> Working notes from the research pass of October 2026. Beginner-issue finders, claim conventions, label taxonomies, and newcomer-issue research. The checked conclusions are in [the research summary](../research.md); these notes keep the evidence, numbers, and URLs behind them. Items marked unverified were not confirmed against a primary source.

# Stream B: Beginner-issue discovery, newcomer-issue recommendation, contributor-project matching

> Verification status. Re-checked first hand on 2026-10-21: the crawlers' sources (DeepSource, up-for-grabs YAML, forgoodfirstissue), CodeTriage's live re-check in `app/models/issue.rb`, the claim bots' commands, a label census over the most-starred repository of 149 organizations, and full reads of OSS-Skills and FindUnderstandFix. Not re-opened: the redirect chains of the dead sites beyond what this note recorded. Links: 31 of 33 resolved with HTTP 200 on 2026-10-21; the rest are URL templates with placeholders, endpoints that need a token, or sites that block scripts. Everything else here is the research stream's working record as written.

Research date: 2026-10-20. All repo metadata (stars, license, pushed_at) is from `gh api repos/...` on that date. Every claim about a project cites the source file or URL it came from. Where I could not verify something it is marked **unverified**.

Working material kept in the scratchpad:
- Clones (read-only, never executed): `(session working files, not included)`
- Label sample (48 GSoC-org repos, 6,873 labels, TSV `repo<TAB>name<TAB>description`): `(session working files, not included)`

---

## TL;DR

1. **The field is mostly static aggregators that re-crawl `label:"good first issue"` on a cron.** goodfirstissue.dev (daily), forgoodfirstissue.github.com (every 6 h), up-for-grabs.net (stats Mon/Wed/Fri, stale cleanup weekly), youzi-forge (every 3 days). None of them verifies whether an issue is *actually free* (claims, linked PRs, assignment), git-into-gsoc's timeline-based availability check is already ahead of every shipping tool I found. Only CodeTriage re-fetches the issue live right before it emails it (and skips issues the user already commented on / that have a PR attached).
2. **Half of the "issue finder" ecosystem is dead or pivoted**: goodfirstissues.com now 301-redirects to an unrelated domain; contribute.dev 308-redirects to ona.com (Gitpod's rebrand); quine.sh carries a "sunsetting Quira" notice; gfibot.io answered HTTP 522 twice; OpenSauced's app repo is archived (team moved to the Linux Foundation / LFX); cutenode/good-first-issue has not been pushed since 2024-03. Survivors: goodfirstissue.dev, up-for-grabs.net, CodeTriage, github/forgoodfirstissue, awesome-for-beginners, first-contributions, Mozilla Codetribute (code pushed 2026-10-20).
3. **Research gives a usable, cheap signal set.** RecGFI (ICSE 2022, basis of GFI-Bot) reaches 0.853 AUC with content + background + dynamics features; its interpretability analysis says an issue is more likely newcomer-resolvable when (a) the reporter has "just enough" project experience (<200 commits) and reports many issues, (b) experienced developers participate (label/edit), (c) the project has an active owner and recently onboarded newcomers. Huang et al. (ESEM 2021, 79 features, RF median AUC 0.88) find GFIs have **fewer and shorter comments, more readable text, more code snippets in the body, fewer modified files**, and are more often `enhancement` than `bug`. Tan et al. (FSE 2020, as quoted by RecGFI): **40.9 % of labelled GFIs are not solved by newcomers and 31.2 % of newcomers fail to solve a GFI even after several attempts**; median share of labelled GFIs in projects is ~4 %.
4. **Claim conventions are a zoo, and most of them end in a real `assigned` event**, zulipbot `@zulipbot claim`, rustbot `@rustbot claim`, Prow `/assign`, pandas `/take` (max 2 open, 7-day auto-release), Apache Beam `.take-issue`, bdougie/take-action `.take`, takanome-dev `/assign-me` (3 max, per-label limit 2, 7-day auto-unassign, used by JabRef with 8 days), Palisadoes `/assign` (org-wide max 2), gemini-cli `/assign` (help-wanted only, max 3, 7-day unassign). git-into-gsoc's `_CLAIM_PATTERNS` currently matches none of these command forms, and treats `assigned` only via the `assignees` field; it should also parse the commands, the bots' acknowledgement comments, the `in progress`/`📍 Assigned`/`State: Work In Progress` labels and the "auto-unassigned for inactivity" comments (which *free* an issue).
5. **Verified GitHub search behaviour (live experiments, 2026-10-20):** without `advanced_search=true`, `org:zulip org:oppia label:"good first issue"` returns 120 results (OR semantics); with `advanced_search=true` it returns **0** (AND semantics); `(org:zulip OR org:oppia)` returns 120 again. Same for sympy+checkstyle (6 / 0 / 6). git-into-gsoc's multi-`org:` query in `find_beginner_issues` therefore depends on the legacy default, which GitHub announced it would flip, it has not flipped yet for REST (my test), but the code should move to explicit `(org:a OR org:b)` + `advanced_search=true` now. `label:"a","b"` (legacy) and `(label:"a" OR label:"b")` (advanced) both work (187 = 187); `no:assignee -linked:pr archived:false` behave identically in both modes.
6. **Label taxonomies in GSoC orgs are not just "good first issue".** Across 48 sampled GSoC-2025/26 org repos: 38 spellings/variants of GFI (`good first issue` ×27, `Good First Issue` ×7, `Good first issue` ×3, `🌱 Good first issue`), plus difficulty ladders (`Difficulty: Easy/Medium/Hard` matplotlib; `difficulty: easy|medium|hard` CCExtractor; `difficulty: 1..5` stdlib; `E-easy/E-medium/E-hard/E-mentor` rust-lang), effort ladders (`effort: few hours | few days | few weeks | ∞` OpenCV and OpenVINO; `effort/1-day … 2-weeks+` kubeflow), size ladders (`size: XS…XL` zulip; `size/XS…XXL` with line-count definitions in musicblocks; `Size: S/M` openlibrary; `SIZE: very small…very large` kolibri), and GSoC-specific labels (`gsoc-prerequisite-task` OpenVINO, `reserved for GSoC` Oppia, `GSoC Priority` talawa, `gsoc-2026` webpack/CGAL/stdlib/CircuitVerse). Important negatives: LLVM's `help wanted` description literally says "Not [good first issue]"; Oppia has `Impact: Low -- ONLY DO IF GOOD FIRST ISSUE`; JabRef's GFI "Varies in difficulty".
7. **What beginners complain about** (from the trackers): inaccurate issue counts (DeepSource #2561, 28 comments), no filter by stars/recency (DeepSource #2615, 30 comments, and the thread itself is four "please assign me" comments in three days), no "recently updated" sort or activity signal (up-for-grabs #1142 open since 2019, #175 open since 2015), stale/closed issues delivered (CodeTriage #525), inability to use custom labels (cutenode #1085), and curation spam (forgoodfirstissue's "[New Project]" issues).
8. **Top proposals for git-into-gsoc**: (P1) advanced-search-safe query builder; (P2) claim-bot-aware availability with per-repo "how to claim here" policy; (P3) per-repo label discovery with normalised difficulty/effort/size; (P4) research-backed newcomer-fit score with LIME-style "why" lines; (P6) local issue digest for tracked repos with CodeTriage-style backoff. Full list with effort estimates in §9.

---

## 0. Status of every tool in scope (checked 2026-10-20)

| Tool | Repo / URL | Alive? | Stars | License (API) | Last push | Notes |
|---|---|---|---|---|---|---|
| goodfirstissue.dev | DeepSourceCorp/good-first-issue (was deepsourcelabs) | yes | 3,544 | MIT | 2026-03-02 | daily cron, Nuxt + Python populate |
| up-for-grabs.net | up-for-grabs/up-for-grabs.net | yes | 6,034 | NOASSERTION (has LICENSE file, check before reuse) | 2026-10-20 | Jekyll + Ruby tooling gem |
| CodeTriage | codetriage/CodeTriage | yes | 1,471 | MIT | 2026-10-01 | Rails/Sidekiq; 100,532 devs / 10,648 repos on homepage |
| For Good First Issue | github/forgoodfirstissue (forgoodfirstissue.github.com) | yes | 254 | MIT | 2026-10-21 | GitHub-owned fork of DeepSource + lucavallin/first-issue; rubyforgood/forgoodfirstissue.dev is just a redirect |
| cutenode/good-first-issue (+ libgfi) | cutenode/good-first-issue | dormant | 835 | none in API (package.json MIT) | 2024-03-06 | npm CLI; open issues still attract "assign me" comments |
| awesome-for-beginners | MunGell/awesome-for-beginners | yes | 90,510 | none in API | 2026-10-01 | data.json → README via Jinja in CI |
| first-contributions | firstcontributions/first-contributions | yes | 56,447 | MIT | 2026-10-21 | tutorial repo, not a finder |
| GFI-Bot | osslab-pku/gfi-bot (not "gfibot") | code yes, site **down (HTTP 522 ×2)** | 57 | GPL-3.0 | 2026-04-21 | "pre-alpha"; ML recommender |
| OpenSauced app | open-sauced/app | **archived** | 457 | Apache-2.0 | 2025-03-21 | README: team now supports LFX |
| OpenSauced pizza-cli | open-sauced/pizza-cli | semi | 52 | MIT | 2025-04-29 | Go; `insights contributors/repositories/user-contributions` |
| OpenSauced docs | open-sauced/docs | yes | 90 | none | 2026-10-18 | metric definitions (OSCR, lottery factor…) |
| Quine / Quira | quine.sh | **sunsetting** (403 to fetch; search snippets show "We're sunsetting Quira") | none | none | none | DevRank, Quests, matching, details unverified |
| goodfirstissues.com | none | **dead** (301 → btbsbend.com/main-menu) | none | none | none | could not recover source/author (Wayback blocked for this agent) |
| contribute.dev | none | **redirect** (308 → ona.com/open-source) | none | none | none | was Gitpod's list |
| Mozilla Codetribute | mozilla-frontend-infra/codetribute | code alive | 58 | none | 2026-10-20 | GitHub GraphQL + bugzilla-graphql-gateway; site is JS-rendered |
| hkirat/gsoc-good-first-issues | none | stale | 689 | none | 2023-08-04 | hand-curated GSoC-2023 GFI list, markdown |
| youzi-forge/good-first-issue-autoUpdate | none | yes | 116 | MIT | 2026-10-19 | GraphQL rolling windows to beat 1000 cap, every 3 days |
| yankeexe/good-first-issues (`gfi`) | none | yes | 156 | none | 2026-09-07 | Python CLI, org/user/repo/hacktoberfest, `--period` |
| EddieHubCommunity/good-first-issue-finder | none | stale | 631 | MIT | 2024-08-11 | SvelteKit, GitHub OAuth |
| Algora | algora-io/algora, algora.io | pivoted to hiring | none | none | none | GitHub app with bounties/tips still in README |
| Polar issue funding | docs.polar.sh | **unclear** (new docs path 404; older docs still describe it) | none | none | none | unverified whether still offered |
| Opire | opire.dev / github.com/opire | yes (per listings) | none | MIT (docs repo) | none | 100 % to dev, ~4 % fee (2024 listing) |
| IssueHunt | oss.issuehunt.io | site up; company pivoted to security bug bounties (2025 funding) | none | none | none | AlternativeTo lists it as discontinued, conflicting, unverified |

---

## 1. Project profiles

### 1.1 goodfirstissue.dev: DeepSourceCorp/good-first-issue

- URL: https://goodfirstissue.dev · repo https://github.com/DeepSourceCorp/good-first-issue · MIT · 3,544 ★ · Python populate script + Nuxt/Tailwind front end · last push 2026-03-02.
- **What it does:** static list of repositories (not issues) that currently have beginner-labelled open issues, browsable by language.
- **Inclusion criteria (README):** ≥3 open issues with beginner labels, ≥10 contributors, README with setup, CONTRIBUTING.md, recent activity, OSI license. Submission via a Google Form; a maintainer appends `github.com/owner/repo` to `data/repositories.toml` (~1,000+ entries).
- **How it works (`gfi/populate.py`):**
  - Label list in `data/labels.json`: `good first issue`, `good-first-issue`, `beginner`, `beginner-friendly`, `easy`, `first-timers-only`, `starter`, `help wanted`, `low-hanging-fruit`.
  - For each repo: skip if `archived`; skip if `pushed_at` older than `MAX_INACTIVITY_DAYS = 90`; for each label call `repository.issues(labels=label, state="open", number=ISSUE_LIMIT=10, sort="created", direction="desc")`; union the results; require ≥1 issue **and** a primary language.
  - Stores per repo: name, owner, description (emojized), language + slug, url, stars (+ numerized display), `last_modified = pushed_at`, id, and per issue: title, url, number, `comments_count`, `created_at`. No assignee/PR/claim data at all.
  - Repos are `random.shuffle`d before processing; language tags need ≥3 repos to appear.
  - Rate limiting: custom thread-safe `GitHubRateLimiter` (1 req/s, 5 workers, proactive pause when `remaining < 100`, coordinated pause on `ForbiddenError`, 3 retries).
  - Output: `data/generated.json` + `data/tags.json`, pushed to Vercel Blob (`sync.js`), then a deploy hook. `.github/workflows/cron.yml` runs daily at 08:00 UTC and on dispatch; CI only runs `test_data.py` (TOML sane, no duplicates).
- **UX (live page):** language chips with counts (Python ×90, TypeScript ×69, Go ×68 …), each repo as a text block with "N issues", description, language, stars, "last activity 8 hours ago". Per-issue titles/comments are not shown on the index. No sort control, no activity filter.
- **Community feedback:** #2561 "[Bug] Amount of issue not accurate" (28 comments; cause is `ISSUE_LIMIT=10`, so every busy repo shows "10 issues"); #2615 "Filter repositories by stars and last activity" (30 comments, most of them "Hi! I would like to work on this issue. Could you please assign it to me?", four claimants in three days); #2568 "Highlight recently active repositories"; #2246 "show top-3 languages"; many unnamed "[Bug]" issues from template misuse.
- **Assessment:** simple, robust, cheap to run; the data model is the weak point (no freshness per issue beyond `created_at`, no availability, capped counts). Good patterns: inactivity cut-off, label union, tag threshold, coordinated rate limiter. Security: token in CI secret only; fine.

### 1.2 up-for-grabs.net: up-for-grabs/up-for-grabs.net

- URL: https://up-for-grabs.net · repo https://github.com/up-for-grabs/up-for-grabs.net · 6,034 ★ · Jekyll + vanilla JS (+ Astro beta) + Ruby tooling gem `up_for_grabs_tooling` (repo up-for-grabs/tooling) · last push 2026-10-20.
- **What it does:** list of ~1,384 projects (`_data/projects/*.yml`) each pointing at **one label URL** in its tracker; the site shows per project the open-issue count for that label.
- **Project YAML schema** (`docs/list-a-project.md`, e.g. `_data/projects/rust.yml`):
  ```yaml
  name: Rust
  desc: A systems programming language focused on safety, speed, and concurrency.
  site: https://www.rust-lang.org
  tags: [oss, systems, rust, language]        # lower case, a-z0-9+#.-
  upforgrabs:
    name: E-easy                                # the label
    link: https://github.com/rust-lang/rust/labels/E-easy
  stats:                                        # generated, never hand-written
    issue-count: 31
    last-updated: '2026-10-19T09:06:04Z'
    fork-count: 19106
  ```
- **Curation criteria:** "available maintainers who are interested in guiding new contributors", "the project curates a list of small tasks", "maintainers are happy and willing to review". PRs idle 2 weeks with blocking feedback are closed. Validation (`scripts/validate_data_files.rb` → tooling `CommandLineValidator`, schema + tags validators) runs on every PR; `review_changes.rb` checks changed projects.
- **Stale-project checks:**
  - `scripts/update_stats_only.rb` (cron `0 13 * * 1,3,5`) calls `GitHubRepositoryLabelActiveCheck`: one GraphQL query per project, `repository{ hasIssuesEnabled forkCount label(name:$label){ issues(states: OPEN, first: 1, orderBy:{field: UPDATED_AT, direction: DESC}){ totalCount nodes{ updatedAt } } } }`, giving count + last-updated for ~1 point of GraphQL cost. Rewrites the label link if it drifted; warns when the label is missing. Commits as `shiftbot`, then re-validates before pushing.
  - `scripts/cleanup_projects.rb` (cron `0 18 * * 0`) calls `GitHubRepositoryActiveCheck`: `archived` → deprecated; `has_issues == false` → deprecated; 404 → deprecated ("missing"); renamed → "redirect" (report only); `repo.updated_at` older than 3 years → "lack-of-activity" (report only; note the variable is misnamed `five_years_ago` but computes `3 * YEAR_IN_SECONDS`). Deprecated projects are deleted on a branch and a PR "Remove projects detected as deprecated" is opened; if such a PR is already open the job exits.
- **Client-side freshness (`javascripts/fetchIssueCount.js`):** browser fetches `https://api.github.com/repos/{owner}/{repo}/issues?labels={label}&per_page=30` unauthenticated, caches `{count, etag, date}` in `localStorage` for 24 h, sends `If-None-Match`, derives "30+" counts from the `Link: rel="last"` header, and stores `X-RateLimit-Reset` so no further calls are made until reset. `project-ordering.js` hides projects whose `stats.issue-count == 0` and randomises the order once per session (`sessionStorage`).
- **Feedback:** #930 "Improving Frontend" (87 comments), #665 pagination, #175 "Show repo activity" (open since 2015), #1142 "Sort by Recently updated" (open since 2019), #244 multiple repos per project, #250 filter AND vs OR, #4917 popular-tag counts stale.
- **Assessment:** best-in-class *operational* hygiene (validators, bot PRs, scheduled stats, ETag caching, rate-limit backoff) with a deliberately thin data model (one label per project). The "one label per project" design is exactly how GSoC orgs behave (Rust uses `E-easy`, SymPy `Easy to Fix`), so the idea of **storing the beginner label per repo** rather than assuming `good first issue` is directly applicable. Weakness: no per-issue data, no activity ranking (users have asked for 10 years).

### 1.3 CodeTriage: codetriage/CodeTriage

- URL: https://www.codetriage.com · repo https://github.com/codetriage/CodeTriage · MIT · 1,471 ★ · Ruby on Rails + Sidekiq + Postgres · last push 2026-10-01.
- **What it does:** you subscribe to repos; once a day you get an email with a few open issues (and, for Ruby repos, methods missing docs) to *triage*, reproduce, comment, review, not necessarily to fix. Homepage lists repos by open-issue count with a language filter; "Submit a Repo" adds any GitHub repo.
- **How it works (source):**
  - `PopulateIssuesJob` pages through `/repos/{o}/{r}/issues?state=open&sort=comments&direction=desc`, upserting `title,url,state,html_url,number,last_touched_at,pr_attached` (`pr_attached` = the `pull_request` hash has non-nil values). `schedule:populate_issues` runs for all active repos; `schedule:mark_closed` marks issues not touched in 24 h as closed (`Issue.queue_mark_old_as_closed!`) and resyncs counts; `update_repos` refreshes language/description/archived/renamed.
  - `IssueAssigner` picks `email_limit` (≤20) random open issues per subscription that were never assigned to that subscription (`ORDER BY random()`), then `Issue#valid_for_user?` **re-fetches the issue live**, skips it if closed, skips it if the user is among the commenters (`commenting_users`), and skips PR-attached issues if the user set `skip_issues_with_pr?`. Rejected issues are recorded as delivered so they are not retried.
  - `SendDailyTriageEmailJob` honours the user's time of day, "sent within 24 h", and `EmailRateLimit`: clicked a link in the last 3 days → daily; 7-13 days → twice a week; 14-30 → weekly; >30 → monthly; the user's own minimum frequency wins if it is lower. The email template carries a **streak counter** and coaching copy ("Your goal is to observe and learn…").
  - `Repo.order_by_need` ranks repos by `issues_count / subscribers` ("where is help most needed"); `weight` buckets issue counts into low/medium/high badges; `RepoLabelAssigner` mirrors repo labels so pages like `#hacktoberfest` can be built (#1680; 513 repos had the label in 2022).
- **Feedback:** #525 closed issue delivered (race between daily import and send; maintainer suggested re-checking issues updated in the last 30 min before sending), #489 description/language stale, #1704 remove archived repos, #131 subscribe to a language, #304 exclude own issues/PRs, #1619 missing emails.
- **Assessment:** the only tool that treats *fresh delivery* as the product. Patterns worth copying: live re-check before surfacing, "skip what you already commented on", PR-attached filter, engagement-based backoff, streaks. Weaknesses: issue selection is random (no difficulty/fit), it is triage-oriented, Ruby-only docs features, and it needs a server + OAuth.

### 1.4 For Good First Issue: github/forgoodfirstissue

- URL: https://forgoodfirstissue.github.com · repo https://github.com/github/forgoodfirstissue · MIT · 254 ★ · Next.js/TypeScript static export · last push 2026-10-21 (cron commits). Credits DeepSource's good-first-issue and lucavallin/first-issue as its basis (README).
- **Scope:** social-impact / civic-tech / Digital Public Goods repos; each must tag issues `help wanted`/`good first issue`, declare SDG topics (`sdg-1`…`sdg-17` as GitHub topics), have README + CONTRIBUTING, and be "actively maintained (last update less than 1 month ago)".
- **How it works (`generate.ts`):** reads `happycommits.json` `{repositories: ["owner/name", …], labels: [...]}`; chunks of 25 repos per **GraphQL search** `repo:a repo:b … archived:false is:public pushed:>=<today-1 month>` fetching `stargazerCount, primaryLanguage, issues(states: OPEN, filterBy:{labels}, orderBy: CREATED_AT DESC, first: 10){ totalCount, edges{ title number url comments.totalCount createdAt labels(first:10) } }, pushedAt, licenseInfo, repositoryTopics(first:20)`; Octokit throttling + retry plugins; 1 s sleep between chunks. Derives `has_new_issues` = any listed issue created within 7 days, keeps only SDG topics, drops repos with no primary language, **randomly shuffles** repositories; sort options are only "most/least stars". The deploy workflow runs every 6 h, force-commits `generated.json` to the `deploy` branch and publishes GitHub Pages. Repos failing the criteria "are automatically removed from happycommits.json" (README).
- **Types (`types.ts`):** besides `Repository`/`Issue`, an `Organization` type with `volunteers_needed`, `stakeholder_available`, `project_ask`, `issue_url`, `is_claimed`, a "project asks" board where an org request can be claimed.
- **Feedback:** #440 "last activity shows as 2 years ago for all projects" (7 comments, still open) and a stream of "[New Project]: <student project>" submissions (#562-#570) that do not meet the criteria, curation spam.
- **Assessment:** cleanest example of a **single GraphQL round trip per 25 repos** that returns repo health + first 10 labelled issues with comment counts; the `pushed:>=1 month` guard is stricter than DeepSource's 90 days. UX: the "new issues this week" badge is a cheap, useful freshness signal. The project-ask / claim concept is interesting for GSoC "org asks" but out of scope.

### 1.5 GFI-Bot / RecGFI / PFIRec: osslab-pku/gfi-bot and the PKU papers

- Repo https://github.com/osslab-pku/gfi-bot · GPL-3.0 · 57 ★ · Python (mongoengine, XGBoost, FastAPI) + React front end · last push 2026-04-21 · README: "currently in pre-alpha stage"; gfibot.io returned HTTP 522 on both attempts today. Papers: GFI-Bot demo (ESEC/FSE 2022, https://hehao98.github.io/files/2022-gfibot.pdf), RecGFI (ICSE 2022, https://hehao98.github.io/files/2022-recgfi.pdf), PFIRec (ASE 2023, https://arxiv.org/abs/2308.09038). Dataset: Zenodo 10.5281/zenodo.6665931 (license not checked, **unverified**).
- **Architecture (README):** `gfibot.data` incrementally collects issue/commit/star/user data (REST + GraphQL, multiple tokens) into MongoDB; `gfibot.data.dataset` restores each resolved issue's state at two time points (creation; "before being worked on"); `gfibot.model` trains per newcomer-threshold models (k = 1…5 commits) and predicts a probability for every open issue; backend exposes `/api/repos`, `/api/issue`, a badge endpoint, and a GitHub App that can label issues above a configurable threshold (`USE_CASES.md`: `.github/gfibot.yaml` with newcomer threshold, candidate-issue filter such as `triaged`, labels to add, probability threshold, optional comment).
- **Feature set actually implemented (`gfibot/model/dataloader.py::_get_issue_features`, mirrors the paper):**
  - *Content*: `len_title`, `len_body`, `n_code_snips`, `n_urls`, `n_imgs` (bug: assigned from `n_urls`), four readability indices (Coleman-Liau, Flesch reading ease, Flesch-Kincaid grade, ARI), 12 label-category counts (bug, feature, test, build, doc, coding, enhance, gfi, medium, major, triaged, untriaged), optional hashed/TF-IDF text vectors of title/body/comments.
  - *Background*: reporter features (is-newcomer, commits/issues/PRs in project and GitHub-wide, repos owned, max stars of repos they committed/issued/PR'd/reviewed in, ratio and count of their reported issues that were resolved by newcomers), the same for the repo owner, `prev_resolver_commits` → project newcomer-resolution ratio/count, repo stars/PRs/commits/contributors, open/closed issue counts and ratio, median issue close time.
  - *Dynamics*: `comment_num`, `event_num`, and averaged experience features of commenters and event actors (including their "gfi_ratio").
  - Ground truth: issue resolved (closed by commit/PR) by a developer with ≤ k prior commits in the project.
- **Paper results worth quoting:** 53,510 resolved issues from 100 projects; up to 0.801 AUC at issue creation and 0.853 AUC at the "before worked on" time point; only ~10 % of issues have labels at creation vs 67 % later, so label-only models are weak early. LIME analysis: reporter experience is negatively correlated overall, but reporters with <200 project commits and many reported issues produce the most newcomer-resolvable issues ("just enough" experience); participation by experienced developers (labelling, editing) and an active owner plus recently onboarded newcomers raise the probability. Real-world check: 60 unlabeled predicted issues sent to maintainers, 33 responses, 16 confirmed as GFIs, 3-5 resolved by newcomers. The intro quotes Tan et al.: 40.9 % of GFIs not solved by newcomers; 31.2 % of newcomers fail a GFI after several attempts; median 4 % of issues labelled GFI.
- **PFIRec (ASE 2023):** personalised ranking (LambdaMART) over 68,858 issues/100 projects; the newcomer-side factors are **expertise preference, OSS experience, activeness, sentiment**; issues solved by the same newcomer share task type, language and domain; roughly doubles the probability the top issue suits the newcomer and cuts failed attempts by a third (abstract). Full feature list not retrieved, **unverified beyond the abstract**.
- **Feedback (issues):** outdated run/deploy docs (#39), transparency of model training (#35), empty frontend page (#45), systematic evaluation request (#40), recent crash fixes in `rest.py`/`dataset.py` (#70-#73, Aug 2026).
- **Assessment:** scientifically the strongest; operationally unusable (site down, GPL, MongoDB, multi-token crawler). The lesson is the *feature list* and the *ground-truth definition* ("resolved by someone with ≤k commits"), both reproducible with a handful of REST calls per issue, and git-into-gsoc already computes `newcomers_merged` / outsider merge rate at repo level. GPL-3.0: do not copy code.

### 1.6 cutenode/good-first-issue + libgfi

- https://github.com/cutenode/good-first-issue · npm `good-first-issue` · 835 ★ · last push 2024-03-06 · commander + inquirer + boxen; `libgfi` does the search.
- **How it works:** `data/projects.json` maps a project key to a hand-written GitHub search query, e.g. `repo:babel/babel is:issue is:open label:"good first issue" -label:"Has PR" -label:"claimed"` or CRA's `-label:"contributions: claimed"`. Unknown names fall back to `org:NAME` / `repo:OWNER/NAME` + `state:open label:"good first issue"`. `libgfi/lib/search.js` sorts `updated desc`, `per_page 30`, and if there are more results picks a **random page ≤ 34** (1,000-result cap) and the CLI prints one random issue ("feeling lucky"); `--first` returns the top one, `--open` opens the browser. Output box shows title, repo, number, state and a hard-coded "Assigned to: unassigned!" (comment admits assigned issues are filtered at search level, but the default query does not include `no:assignee`).
- **Feedback:** rate limiting unhandled (#34, #132), `--label` flag request (#1085: four "can I work on this" comments plus one bare `/assign` comment that does nothing, the convention confusion in miniature), #1100 random pick never returns the last issue (`Math.random() * (issues.length - 1)` bug).
- **Assessment:** the per-project query strings are the valuable artefact: they encode each project's **claim-state labels** (`Has PR`, `claimed`, `contributions: claimed`) as exclusions. Otherwise dormant.

### 1.7 MunGell/awesome-for-beginners

- https://github.com/MunGell/awesome-for-beginners · 90,510 ★ · `data.json` → README rendered by `.github/scripts/render-readme.py` (Jinja) on every push; PRs that edit README directly are auto-closed and labelled `invalid: README.md edited` (`invalid.yml`).
- **Schema:** `{name, link, label, technologies[], description}`, again one beginner label per repo (`first-timers-only`, `good first issue`, `low-hanging-fruit`…). `cghi.py` is a tiny helper that counts open issues for a label via `search/issues`.
- **Criteria (CONTRIBUTING):** established repo, active maintenance, beginner labels whose meaning is confirmed with the owner if non-obvious, supportive community; "not for small personal projects". Feedback: duplicates across sections (#1900), requests for AI/LLM section (#2044), link-check CI.
- **Assessment:** pure curation; no freshness or counts on the page. Useful as a seed list of label names.

### 1.8 firstcontributions/first-contributions

- https://github.com/firstcontributions/first-contributions · MIT · 56,447 ★ · a step-by-step fork→clone→branch→edit `Contributors.md`→PR tutorial with GUI-tool variants and ~80 translations. Not a finder; CodeTriage and firsttimersonly.com link to it as the "learn the mechanics first" step. Worth linking from git-into-gsoc's phase-1 guidance rather than re-implementing.

### 1.9 OpenSauced: app (archived), docs, pizza-cli, StarSearch

- open-sauced/app archived 2025-03 (README: "This project has been archived. This team now supports the LFX"); one source dates "OpenSauced joins the Linux Foundation" to 2024-10-15 (thinly corroborated). Docs repo still updated (2026-10-18); pizza-cli (Go, MIT) last push 2025-04-29.
- **Metric definitions (docs/welcome/glossary.md, key-metrics-guide.md):**
  - **OSCR** (Open Source Contributor Rating): 0-300, rolling 90 days, "quality of contributions, their contributor confidence, and their sway, the ability to drive conversation". Docs warn being flagged as spam lowers the score.
  - **Contributor Confidence**: % of users who starred/forked a repo that later contribute; forks weighted more than stars; marketed as "whether the project welcomes new contributors".
  - **Lottery Factor** (bus factor): high if ≤2 contributors author 50 % of PRs.
  - **PR Velocity**: mean time from PR open to merge. **Activity ratio**, **New / Active / Alumni contributors** (per 30/7/90-day windows), **spam PR** counts, **YOLO coders** (direct pushes to default branch), OpenSSF Scorecard.
  - **Contributor Insights**: curated lists of contributors (from explore, GitHub team sync, or following) with commit/PR/issue activity graphs. **Repo Insights**: dashboards per repo. **StarSearch**: natural-language queries over git history ("What type of pull requests has {username} worked on?", "Who are the best developers that know {technology}…", "Show me the lottery factor for {repository}"); docs say "most accurate from March 1, 2024" and "may not always be accurate".
  - **pizza-cli**: `pizza insights contributors url… --range 30` (new/recent/alumni/repeat contributors per repo), `insights repositories`, `insights user-contributions --users … --sort total|commits|prs`; `generate codeowners` from git blame; `generate insight`. Output table/yaml/csv/json. Separate repo `open-sauced/repo-query` (Rust, 80 ★, 2024) "ask questions about a repo", relevant to the codebase-understanding stream.
- **Assessment:** the metrics vocabulary (lottery factor, contributor confidence, new/alumni contributors, PR velocity) is a good fit for git-into-gsoc's repo grade; they are all computable from PR/commit lists. The contributor-matching part (StarSearch) was LLM-over-warehouse and is gone with the app. Apache-2.0/MIT.

### 1.10 Quine/Quira, goodfirstissues.com, contribute.dev, Codetribute, and smaller finders

- **Quine → Quira** (quine.sh): fetch blocked (403). Search snippets: "We're sunsetting Quira… AI coding tools have made many of our core assumptions obsolete"; DevRank "a reputation system for developers inspired by PageRank, applied to the GitHub open source graph"; Quests (creator/solver bounties); contributor matching described as "an experiment that recommended developers to GitHub repositories and issues based on their previous contributions". All **unverified** beyond snippets; treat as dead.
- **goodfirstissues.com**: 301 → `https://btbsbend.com/main-menu/` (domain lapsed). I could not recover its source or author (archive.org is blocked for this agent), **unverified history**.
- **contribute.dev**: 308 → `ona.com/open-source` (Gitpod rebrand). Dead as a finder.
- **Mozilla Codetribute** (https://codetribute.mozilla.org, repo mozilla-frontend-infra/codetribute, pushed 2026-10-20): "helps new contributors find a project… and then find a task that is suitable to their skills and interests and not already assigned to someone else"; data from GitHub GraphQL and a `bugzilla-graphql-gateway`. Its design (project pages → task lists across two trackers, hide assigned) is the closest analogue to a multi-tracker GSoC finder.
- **youzi-forge/good-first-issue-autoUpdate** (116 ★, MIT, updated 2026-10-19): GraphQL search in **rolling 5-day `created:` windows** to get around the 1,000-result cap, default filters last 90 days + ≥1000 ★, labels `good first issue`/`good-first-issue`/`first-timers-only`, every 3 days; publishes a React page and a standalone HTML.
- **yankeexe/good-first-issues** (`gfi`, 156 ★, Python, 2026-09): org/user/repo search, `--hacktoberfest` topic mode, `--period "30 days"`, browser open; fine-grained PAT stored in `~/.gfi`.
- **EddieHubCommunity/good-first-issue-finder** (631 ★, SvelteKit, 2024-08): GitHub OAuth, EddieHub org crawler.
- **hkirat/gsoc-good-first-issues** (689 ★, 2023): a hand-curated markdown list of GFIs "from previous year organizations for GSoC 2023 aspirants", grouped by language (musicblocks, Rocket.Chat, zulip, element-web, jitsi, Submitty, joomla, oppia, inkscape, …). Demand signal: 689 stars for a static list, the GSoC-scoped finder is wanted.
- **firsttimersonly.com** (Kent C. Dodds / Scott Hanselman): defines the `first-timers-only` label ("very small and easy… described in great detail… tested by the maintainer"), links the First Timers GitHub app (creates such issues from `first-timers-*` branches), up-for-grabs, goodfirstissue.dev, CodeTriage, first-contributions, firstpr.me.
- **GitHub's own surfaces:** docs say "GitHub uses an algorithm to identify the most approachable issues in each repository and shows them in various places" and that adding `good first issue` "can increase the likelihood that your issues are surfaced" (https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels). The repo `/contribute` page (e.g. https://github.com/zulip/zulip/contribute) says "Each issue displayed here is a 'good first issue,' selected for its relative approachability for first-time contributors", for zulip it showed a single item that is actually a labelled PR, so it is not a reliable feed. Explore offers "personalized recommendations for projects and good first issues based on your past activity" (https://docs.github.com/en/get-started/exploring-projects-on-github/finding-ways-to-contribute-to-open-source-on-github).

### 1.11 Bounty platforms (brief)

- **Algora** (algora-io/algora, Elixir, self-hostable): README, "a GitHub app to create bounties & reward tips on issues and PRs"; the 2023 launch post describes `/bounty $N` on issues and `/claim #issue` in PR bodies with auto-pay on merge via Stripe. algora.io now markets itself as a hiring platform ("Hire the top 1% open source engineers"). For claim parsing: a PR containing `/claim #123` is a strong "taken" signal.
- **Polar**: older docs describe issue funding via a badge/`polar.new`, rewards split among contributors, 5 % → later "4 % + 40¢" fees; the new docs path returns 404 and no sunset notice was found, status **unverified**.
- **Opire**: GitHub bot + web; "the developer always gets 100 % of the accumulated rewards"; 4 % + Stripe fee per a 2024 listing; docs site is JS-only (not readable here), command names **unverified**.
- **IssueHunt**: oss.issuehunt.io still describes "the issue-based bounty platform for open source projects"; the company's 2025 funding announcement positions it as a security bug-bounty/ASPM vendor; AlternativeTo lists it as discontinued, **conflicting, unverified**.
- Relevance to GSoC: bounties attract AI-generated drive-by PRs (a Hackernoon experiment reported an agent earning $0 in three days and finding closed/unavailable Opire rewards); GSoC orgs explicitly discourage this. git-into-gsoc should treat bounty labels/comments (`/bounty`, `💎 Bounty`, `/claim`) as "likely contested" and not recommend them to beginners.

---

## 2. Research: which signals predict that a newcomer can finish an issue

### 2.1 Sources

| Paper | Venue | Data | Model / result | Where read |
|---|---|---|---|---|
| Tan, Zhou, Sun, "A First Look at Good First Issues on GitHub" | ESEC/FSE 2020 | 9,368 GFIs from 816 projects + surveys | descriptive; "almost half of GFIs are not solved by newcomers"; GFIs take longer than ordinary issues; recommends informative descriptions, available support, limited scope/skill | abstract via SUTD repository + Semantic Scholar (ACM PDF blocked); numbers 40.9 % / 31.2 % / 4 % quoted from RecGFI's introduction |
| Huang, Wang, Wang, Liu, Wang, Wang, "Characterizing and Predicting Good First Issues" | ESEM 2021 | 74,780 issues, 10 projects (babel, bitcoin, jest, lighthouse, skaffold, packer, graphql-engine, minikube, react-admin, nextcloud server) | 79 features, Random Forest best, median AUC 0.88; inspecting top-5 % of predictions retrieves a median 42 % of all GFIs; 10 of 16 maintainer responses confirmed predicted GFIs | full text (pdftotext of https://www.eecs.yorku.ca/~wangsong/papers/esem21b.pdf) |
| Xiao, He, Xu, Tan, Dong, Zhou, "Recommending Good First Issues in GitHub OSS Projects" (RecGFI) | ICSE 2022 | 53,510 resolved issues, 100 projects, two time points | XGBoost, AUC 0.801 (creation) / 0.853 (before work starts); LIME interpretation | full text (pdftotext of https://hehao98.github.io/files/2022-recgfi.pdf) |
| He, Su, Xiao, He, Zhou, "GFI-Bot" | ESEC/FSE 2022 demo | none | deployment of RecGFI as GitHub App | README + code |
| Xiao, Li, He, Qiu, Zhou, "Personalized First Issue Recommender" (PFIRec) | ASE 2023 | 68,858 issues, 100 projects; 37 newcomers' first issues | LambdaMART ranking; factors: expertise preference, OSS experience, activeness, sentiment | abstract only (arXiv 2308.09038) |
| Alderliesten, Zaidman, "An Initial Exploration of the GFI Label for Newcomer Developers" | CHASE 2021 | none | GFIs "effective at developer onboarding", perceived useful; task types could better match real first contributions | abstract only (TU Delft portal) |

### 2.2 Feature-level findings (what to compute, in which direction)

**Huang et al. (ESEM 2021), three dimensions, 79 features, Wilcoxon + Cliff's delta (Table 2 of the paper):**
- *Clearness of description* (45): reporter role (member/contributor/collaborator, **no** significant difference), `has_gfi` (reporter previously filed GFIs, significant), text length of title/body/all comments/avg comment (all significant; **comments** medium effect), `comments_num` (significant, medium; GFIs have **fewer and shorter comments**), 36 readability indices (comment readability consistently medium effect: easier-to-read threads → GFI).
- *Complexity of changes* (11): `url_num`, `code_num_body` (GFIs have **more code snippets in the body**), `code_num_comments`, `modified_files` (fewer for GFIs, small effect), `file_complexity` (lower), `change_num` (how often the touched file changes), inserted/deleted/modified lines (negligible).
- *Skills required* (23): issue-type labels (`is_enhancement` significant, GFIs lean to enhancements; `is_bug`/`is_documentation` **not** significant), topic counts (GFIs have *more* topics in title/body, more detailed descriptions), Naive-Bayes "GFI likelihood" scores on title/body/comments (small→large effects; indicative words exist).
- Model notes: RF > LR/SVM/MLP; semantics, readability and text-richness categories contribute most; post-hoc features (modified files) only exist after closure, so a live recommender must rely on text + labels + dynamics.

**Xiao et al. (RecGFI, ICSE 2022), three dimensions:**
- *Content*: `len_title`, `len_body`, `#urls`, `#code_snips`, `#imgs`, four readability indices, counts of 50 "newcomer" vs "non-newcomer" keywords, TF-IDF of title/description, 12 label categories (bug, documentation, test, build, enhancement, coding, new feature; GFI-signalling, medium difficulty, difficult/important; triaged, untriaged) + `#labels`.
- *Background*: reporter (newcomer?, project commits/issues/PRs, GitHub-wide commits/issues/PRs, repos, stars, followers, non-GFI/GFI ratio of their past issues, has_comment/has_event); project (stars, contributors, commits, closed PRs, owner experience, open issues, median issue close time, number/ratio of issues resolved by newcomers).
- *Dynamics*: `#comments`, TF-IDF of comments, `#events` + top-25 event-type counts (subscribed, mentioned, labeled, …), labeler/event-actor experience and their GFI-reporting history, number/ratio of newcomers among participants.
- Interpretation (LIME on vscode, Figures 3-5): reporter experience is negatively correlated overall, but **reporters with <200 project commits are the best GFI reporters** ("just enough" experience); experienced participants labelling/editing raise the probability; more recently onboarded newcomers in the project raise it; at creation time 89.68 % of issues have no labels (33.01 % at the later time point), so label-only ranking is weak for fresh issues.

**Tan et al. (FSE 2020), as quoted in RecGFI:** 40.9 % of GFIs not solved by newcomers; 31.2 % of newcomers fail a GFI after several attempts; median ≈4 % of a project's issues carry a GFI label. Maintainer recommendations: informative descriptions, available support (mentor/pointers), limited scope and skill.

**PFIRec (ASE 2023):** issues solved by the same newcomer share task type, language and domain; personalisation needs the newcomer's expertise preference (languages/file types from their history), OSS experience, activeness, and sentiment.

### 2.3 Mapping to what git-into-gsoc can compute cheaply

| Signal (research) | Direction | Cheap source | In git-into-gsoc today? |
|---|---|---|---|
| Comment count / comment length | fewer, shorter → better | search item `comments`; timeline bodies | partially (`comments <=2` +5, `>=10` −5) |
| Code snippets / URLs / images in body | more → better | regex on `body` (```` ``` ````, `http`, `![`) | no (only "steps to reproduce"/"expected" keyword check) |
| Readability of body/comments | easier → better | Flesch/ARI via `textstat`-like formula (pure Python) | no |
| Body length | longer (but readable) → better | `len(body)` | only "<40 chars" penalty |
| Label category: enhancement/docs/test vs bug; GFI-signalling; untriaged | enhancement/docs ↑; `needs triage` ↓ | labels | partially (`POSITIVE_LABELS`, `NEGATIVE_LABELS`) |
| Reporter is maintainer with moderate experience; reporter has history of newcomer-resolved issues | ↑ | `author_association` of issue author; `search/issues author:X repo:R is:closed` count | no |
| Experienced participants labelled/edited the issue | ↑ | timeline `labeled`/`renamed` events with `actor` role | partially (`maintainer_engaged` from comments only) |
| Project: ratio of issues resolved by newcomers, median close time, active owner | ↑ | repo health already samples PRs: `newcomers_merged`, `outsider_merge_rate`, `median_pr_hours` | yes at repo level, not fed into issue score |
| Event dynamics: `subscribed`/`mentioned` many → complex | ↓ | timeline event counts | no |
| Linked PR / assignee / claims | taken | timeline `cross-referenced`, `assigned`, comments | yes (availability) |
| Issue age with no PR | old + untouched → stale/abandoned opportunity; very fresh → competition | `created_at`, `updated_at` | yes (updated-in-30d bonus, 180d penalty) |
| Newcomer-issue personalisation (language, file types, task type) | match ↑ | user's repos/PRs via `infer_profile_languages` | shallow (languages only) |

---

## 3. Claim / assignment bot conventions (and what they mean for the claim parser)

### 3.1 Conventions found in the wild

| Project / tool | Claim command (exact) | Release | Guard rails | Auto-unassign | Source |
|---|---|---|---|---|---|
| Zulip (zulipbot) | `@zulipbot claim` (comment or issue body) | `@zulipbot abandon` | assigns + adds `in progress` label; grants read-only collaborator; new contributors may hold **one** issue until first PRs merge; unclaimed = `-label:"in progress" no:assignee` | 1-week inactivity prompt, then 3 days → unassigned + label removed | https://zulip.readthedocs.io/en/latest/contributing/zulipbot-usage.html, https://zulip.readthedocs.io/en/latest/contributing/contributing.html |
| Zulip claiming rules | none | none | "you should not claim an issue" before you can tackle it; an issue is abandoned if "the assigned contributor has not opened or updated a PR for the issue in the past 2 weeks"; ask, wait 2-3 days, then take over | none | same |
| Rust (triagebot) | `@rustbot claim` (anyone) | `@rustbot release-assignment` / `@rustbot unclaim`; `@rustbot assign @user` (team) | if GitHub refuses the assignment, bot assigns `@rustbot` and edits the top comment to say the issue is claimed; `triagebot.toml` `[assign]` with `contributing_url`, `llm_policy_url` | not documented | https://forge.rust-lang.org/triagebot/issue-assignment.html, rust-lang/rust `triagebot.toml` |
| Kubernetes / CNCF (Prow `assign` plugin) | `/assign` or `/assign @user`; `/cc` for reviewers | `/unassign` | regex `^/(un)?assign(( @?[-\w]+?)*)\s*$`; target must be org member, collaborator, or have commented on the issue; max 10 assignees | none | kubernetes-sigs/prow `pkg/plugins/assign/assign.go` |
| pandas | `/take` (exact body) | `/untake` (refused while you have an open PR for it) | declined if labelled `Needs Triage`, `Needs Discussion`, `Needs Info`, `Closing Candidate`; max **2** open issues (maintainers exempt); PR to an unclaimed issue gets `Needs Issue Assignment` | **7 days** without linked PR or activity → unassigned (daily job `unassign-inactive.yml`) | pandas-dev/pandas `.github/workflows/comment-commands.yml`, contributing guide |
| Apache Beam | `.take-issue` | `.free-issue`; also `.close-issue`, `.reopen-issue`, `.add-labels 'x','y'` | removes `awaiting triage` | none | apache/beam `.github/workflows/self-assign.yml` |
| bdougie/take-action (OpenSauced-era, 55 ★, MIT) | `.take` (configurable `trigger`) | none | `blockingLabels` list; custom `message` | none | https://github.com/bdougie/take-action |
| takanome-dev/assign-issue-action (MIT) | `/assign-me` (default); maintainers `/assign @user` | `/unassign-me`, `/unassign @user` | `required_label`, `max_assignments` 3, per-label limit (`good first issue,good second issue` → 2 each), `block_assignment` after an unassignment, newcomer-specific welcome text, adds label `📍 Assigned`, `📌 Pinned` exempts; **`enable_auto_suggestion`: replies to free-text "can I work on this?" comments telling people to use the command** | `days_until_unassign` 7 (reminder at half-time) | README; used by JabRef with 8 days (`unassign-issues.yml`), which also moves freed issues to a "Free to take" project column |
| Palisadoes Foundation (talawa) | `/assign` only (no username) | `/unassign` | **org-wide** `MAX_OPEN_ASSIGNMENTS = 2`; checks merged-PR history; ignores bot comments except CodeRabbit-authored issues | none | PalisadoesFoundation/.github `auto-assign.yml` |
| google-gemini/gemini-cli | `/assign` | `/unassign` | only issues labelled `help wanted`; max 3 open assignments (`advanced_search: true` search) | daily: no non-draft linked PR within **7 days** → unassigned + comment; maintainers exempt | `.github/workflows/gemini-self-assign-issue.yml`, `unassign-inactive-assignees.yml` |
| OWASP BLT | `/assign` | none | one issue at a time, auto-unassign after 5 days (search snippet; repo returned 404 for me, **unverified**) | 5 days | search result for OWASP-BLT/BLT-Action |
| openwisp | bot command `issue_assignment` via `openwisp-companion` app (reusable workflow) | none | python bots in openwisp-utils `.github/actions/bot-autoassign/` (issue assignment, PR reopen, stale PR) | yes (stale PR bot) | openwisp/openwisp-controller `bot-autoassign-issue.yml` |
| Oppia | no command: comment with **a video of the fix working locally**, root cause and planned changes, @-mention leads; then you get assigned | none | only `Impact: High/Medium` unassigned issues; avoid `Impact: Low`, `Backlog`, `triage needed` | de-assigned if PR stale / no activity | https://github.com/oppia/oppia/wiki/Contributing-code-to-Oppia |
| scikit-learn | plain comment "with your idea of how you plan to approach it" | none | rarely uses `good first issue` ("often prove more complex than anticipated"); check linked PRs and conversation first; `Needs Triage` → do not open a PR | claim expires: PR expected within **2 weeks (new contributor) / 4 weeks (contributor)**; stalled PRs may be taken over after 2 weeks of silence | https://scikit-learn.org/dev/developers/contributing.html |
| AsyncAPI | `/please-take-a-look` or `/ptal` on PRs pings code owners (not a claim) | none | none | none | asyncapi/spec workflow |
| Algora | `/claim #123` in PR body (bounty claim) | none | none | none | 2023 launch post (secondary) |

Also observed: Jupyter (jupyterlab, notebook) only have `auto_author_assign.yml` (PR author auto-assign), no issue-claim bot; Apache Airflow, SymPy, matplotlib, checkstyle, LLVM, OpenMRS, Rocket.Chat, musicblocks, CircuitVerse, wagtail, OpenLibrary, superset/pulsar/dolphinscheduler/shardingsphere have **no** assign/take workflow file (humans assign after a comment). OpenLibrary uses labels `Needs: Assignee Check-in`, `Needs: Assignment Review`, `State: Work In Progress` to manage claims.

### 3.2 Implications for `src/git_into_gsoc/github/availability.py`

1. **Command claims are missed.** `_CLAIM_PATTERNS` only matches English prose. Add exact-command patterns (anchored at line start, case-insensitive): `@zulipbot claim`, `@rustbot claim`, `/assign` (bare or `/assign @me`), `/assign-me`, `/take`, `.take`, `.take-issue`, `/claim`, `/attempt`, `claiming`. Treat the bot's acknowledgement (`author.type == Bot` comment containing "assigned"/"claimed"/"you've been assigned") as a *grant* even though the current code skips bot comments entirely.
2. **Releases free the issue.** `/untake`, `/unassign`, `/unassign-me`, `@zulipbot abandon`, `@rustbot release-assignment`, `.free-issue`, and bot comments "has been unassigned due to inactivity" / "automatically unassigned" should *clear* that user's claim. Today `claims[login]` can only be set, never cleared, so an auto-released issue still reads `claimed` for 30 days.
3. **Labels are claim state.** Treat `in progress`, `📍 Assigned`, `State: Work In Progress`, `wip`, `WIP`, `claimed`, `contributions: claimed`, `Has PR`, `Needs: Assignee Check-in` as *taken* (unless `no:assignee` and the label is stale); treat `Needs Triage`, `needs-triage`, `awaiting triage`, `triage needed`, `Needs Discussion`, `Needs Info`, `Closing Candidate`, `Status: Needs confirmation` as *blocked* (pandas and scikit-learn both forbid PRs on them). Treat `Free to take` (JabRef project column), `help wanted` + `no:assignee` as positive.
4. **Policy per repo is discoverable.** The presence of `.github/workflows/*assign*|*take*` or a `triagebot.toml` `[assign]` table or `@zulipbot` in CONTRIBUTING tells the user *how* to claim and what the limits are (max 2-3 open, 7-8-day inactivity). git-into-gsoc already fetches CONTRIBUTING and the root listing in `contribution_guide`; extend it to detect the command and emit "To claim here: comment `/take`; you may hold 2 issues; auto-released after 7 days".
5. **"Five people claimed it" is a policy problem the best orgs solve with limits, not with prose.** Zulip (1 issue for newcomers), pandas (2), gemini-cli (3), takanome (3 + per-label 2), Palisadoes (2 org-wide). The recommender should (a) rank uncontested issues first (already), (b) show the claimant count and the age of the newest claim, (c) say explicitly when an older claim has lapsed under the repo's own rule (pandas 7 d, Zulip 2 weeks, scikit-learn 2 weeks), and (d) generate the right claim text instead of "please assign me".

---

## 4. GitHub issue search: qualifiers, limits, and the advanced-search trap (verified)

### 4.1 Live experiments (2026-10-20, authenticated `gh api search/issues`)

| Query | legacy (no param) | `advanced_search=true` |
|---|---|---|
| `is:issue is:open label:"good first issue" org:zulip org:oppia` | **120** (= 20 + 100, OR) | **0** (AND) |
| `… (org:zulip OR org:oppia)` | n/a | **120** |
| `is:issue is:open label:"good first issue" org:sympy org:checkstyle` | 6 | 0 (OR form: 6) |
| `org:zulip is:issue is:open no:assignee label:"good first issue","help wanted"` | 187 | none |
| `org:zulip is:issue is:open no:assignee (label:"good first issue" OR label:"help wanted")` | none | 187 |
| `org:zulip is:issue is:open no:assignee -linked:pr archived:false label:"good first issue"` | 3 | 3 |
| `… label:"good first issue" -label:"in progress"` (advanced) | none | 15 (vs 20 without the exclusion) |
| `… comments:<3 created:>2026-04-01` (advanced) | none | 0 (works; just no fresh GFIs) |
| `sort=interactions&order=asc` (advanced) | none | returns items with `comments`/`reactions.total_count` |
| `gh search issues --owner sympy --owner checkstyle --label "good first issue"` | 1 result at `--limit 1` (CLI handles multi-owner) | |

Reading: GitHub's changelog (https://github.blog/changelog/2025-03-06-github-issues-projects-api-support-for-issues-advanced-search-and-more/) says "a space between multiple `repo`, `org`, and `user` filter qualifiers is treated as an `AND` operator" under advanced search and that advanced search would become the default on 2025-09-04; the REST docs today document `advanced_search` as an optional string with no default and no deprecation note (https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests). **Empirically the REST default is still legacy today**, but `find_beginner_issues` in `src/git_into_gsoc/github/client.py` appends `org:{owner}` repeatedly and would silently return zero results the day the default flips. GraphQL already exposes `type: ISSUE_ADVANCED`.

### 4.2 Qualifier cheat-sheet relevant to beginner-issue search (docs: https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests and the issues filtering page)

- Scope: `repo:o/r`, `org:o`, `user:u` (issues page limits to 16 `user`/`org` qualifiers; `repo` unlimited), `archived:false`, `is:public`, `language:`.
- State: `is:issue is:open`, `reason:completed|"not planned"`, `is:locked`.
- Missing metadata: `no:assignee`, `no:label`, `no:milestone`, `no:project`, cannot be negated with `-`.
- Links: `linked:pr` / `-linked:pr` (closing-keyword links only; "connected" via the Development sidebar also counts for `linked:`, but plain mentions do not, hence the timeline check stays necessary).
- Labels: AND = repeated `label:` qualifiers; OR = comma inside one qualifier `label:"good first issue","help wanted"` (legacy) or `(label:a OR label:b)` (advanced); exclusion `-label:"in progress"`.
- Counts and dates: `comments:<3`, `interactions:<5` (reactions + comments), `reactions:>2`, `created:>=YYYY-MM-DD`, `updated:>=`, `closed:`, ranges `n..m`.
- People: `author:`, `-author:app/dependabot`, `assignee:*` (single repo only), `commenter:`, `involves:`, `mentions:`, `@me`.
- Text: `in:title,body,comments`; `NOT term`.
- Boolean (advanced): `AND`, `OR`, parentheses nested up to 5 levels; `-` for exclusion.
- API: 30 requests/min authenticated (10 unauthenticated), `per_page ≤ 100`, hard cap **1,000 results per query** (youzi-forge works around it with rolling `created:` windows; libgfi picks random pages ≤ 34), `sort` ∈ comments, reactions, reactions-+1, reactions--1, reactions-smile, reactions-thinking_face, reactions-heart, reactions-tada, interactions, created, updated; default best-match.

### 4.3 Recommended query templates for git-into-gsoc

- Default beginner search (advanced mode, one request instead of two):
  `is:issue is:open no:assignee -linked:pr archived:false updated:>=<1y> (org:a OR org:b OR …) (label:"good first issue" OR label:"help wanted" OR label:"E-easy" OR label:"Easy to Fix" OR label:"difficulty: easy" OR label:"beginner friendly" OR label:"first-timers-only" OR label:"low-hanging-fruit") -label:"in progress" -label:"needs triage" -label:"Needs Triage"`, note the per-repo label vocabulary from §5 should be substituted when the repo is known.
- "Quiet, fresh, specific" variant for the contested season (Feb-Mar): add `comments:<3 created:>=<60d>` and sort by `created desc`; the experiment shows this returns few results per org, which is the point.
- "Lapsed claim" variant: `comments:>=3 updated:<=<21d>` + timeline check for claims older than the repo policy; present as "ask if still active".

---

## 5. Label taxonomies in real GSoC-org repos (48 repos sampled; GSoC 2025/2026 orgs per the project's own `orgs --year 2025` list)

Sampled repos (org → repo): Zulip, Oppia, SymPy, checkstyle, LLVM, OpenMRS, OpenCV, Sugar Labs (musicblocks), Rocket.Chat, Internet Archive (openlibrary), Rust Foundation (rust), Keploy, Palisadoes (talawa-api), Jenkins, Julia, Processing (p5.js), CircuitVerse, MetaBrainz, OpenWISP, JabRef, Wagtail, NumFOCUS (matplotlib), ArduPilot, CCExtractor, ASF (airflow, beam), AsyncAPI, stdlib, OpenVINO, Learning Equality (kolibri), Graphite, Mixxx, FreeCAD, OSGeo (QGIS), Jitsi, AnkiDroid, Organic Maps, Electron, Kubeflow, Catrobat, CERN-HSF (root), Mifos (web-app), Scala Center (scala3), MariaDB, CGAL, Open Robotics (gz-sim), webpack, OWASP (BLT). Raw TSV in the scratchpad path above.

### 5.1 Beginner-signalling labels actually used

| Family | Examples (repo → label, description) |
|---|---|
| GFI spelling variants | `good first issue` (27 repos), `Good First Issue` (7), `Good first issue` (3), `🌱 Good first issue` (matplotlib: "Open a pull request against these issues if there are no active ones!"), `Good First PR` (stdlib: PRs resolving a GFI) |
| Easy synonyms | checkstyle `easy`; mixxx `easy`; QGIS `Easy fix`; SymPy `Easy to Fix` ("good issue for new contributors. Feel free to work on this if no one else has already") and `Easy to Revive` (abandoned PRs with minor details left); electron `beginner friendly`; scala3 `exp:novice`; kubeflow `starter`; root `new contributor`; AnkiDroid `New contributor`; Graphite `Paper Cut`; rust `D-papercut`, `Libs-Small` |
| Difficulty ladders | matplotlib `Difficulty: Easy|Medium|Hard` (link to devdocs); CCExtractor `difficulty: easy|medium|hard`; stdlib `difficulty: 1…5` with definitions; rust `E-easy` ("Experience needed to fix: Not much. Good first issue."), `E-medium`, `E-hard`, `E-tedious`, plus `E-mentor` ("This issue has a mentor"), `E-help-wanted`, `E-needs-mcve/test/bisection/design/investigation` |
| Effort ladders | OpenCV `effort: few hours` ("Ideal issue for rainy weekend"), `few days`, `few weeks`, `∞` ("Do not start this alone"); OpenVINO same four; kubeflow `effort/1-day` … `effort/2-weeks+` |
| Size ladders | zulip `size: XS|S|M|L|XL`; musicblocks `size/XS` (<10 lines) … `size/XXL` (1000+); openlibrary `Size: S|M`; kolibri `SIZE: very small … very large`; JabRef `size: small|medium|big` + `Review effort 1/5…4/5`; wagtail `size:Small`; mixxx `size/s` (hours), `size/m` (days), `size/l` (weeks) |
| Help wanted | 20+ repos; **LLVM**: "Indicates that a maintainer wants help. Not [good first issue]."; gz-sim "We accept pull requests!"; AnkiDroid "Requesting Pull Requests from volunteers" |
| Mentoring | rust `E-mentor`; beam `mentor`; matplotlib `mentored: GSOC`, `mentored: sprint`, `mentored: student project`; zulip `mentor review` / `buddy review` ("GSoC buddy review needed") |
| GSoC-specific | `gsoc`/`GSoC` (ArduPilot, CGAL, LLVM, MariaDB, OpenCV, stdlib, kolibri, asyncapi, jitsi "Appropriate for GSoC students to tackle"); year labels `gsoc-2026`/`GSoC'26`/`gsoc: 2026` (CGAL, CircuitVerse, stdlib, webpack, Catrobat "assigned to the GSoC contributor"); OpenVINO `gsoc-prerequisite-task`; Oppia `reserved for GSoC`; talawa `GSoC Priority`; keploy `GSoC` ("Issues up for GSoC"); Rocket.Chat `gsoc-project`; electron `GSoC 2025` |
| Warnings / anti-signals | Oppia `Impact: Low -- ONLY DO IF GOOD FIRST ISSUE`, `Work: Medium` ("isn't at good-first-issue level yet"); JabRef GFI "Varies in difficulty"; LLVM `potentially good for outreach` ("for someone that has spoken to an experienced LLVM dev"); matplotlib `hacktoberfest: spam`; QGIS `PossiblyAiBot⚠️🚨` ("New contributor, with potentially suspicious GitHub activity"); mixxx `AI` ("heavy use of AI… extra attention to review"); airflow `closed because of open PR limit` |
| Claim / status | zulip `in progress` (bot-managed); JabRef `📍 Assigned`; openlibrary `State: Work In Progress`, `Needs: Assignee Check-in`, `Needs: Assignment Review`; ArduPilot/Catrobat `WIP`; CGAL `Work in progress`; pandas `Needs Triage`, `Needs Issue Assignment`; beam `awaiting triage`; FreeCAD `Status: Needs triage|confirmation|steps to reproduce`; many `stale` |
| Non-GitHub orgs (not sampled) | python/cpython `easy` (verified via API; PSF is an umbrella org); GNOME GitLab "Newcomers", LibreOffice Bugzilla "EasyHack" (page blocked by Anubis, **unverified**), Mozilla Bugzilla `good-first-bug` via Codetribute, Wikimedia Phabricator "good first task" (**unverified**) |

### 5.2 Consequences

- `POSITIVE_LABELS` in `src/git_into_gsoc/scoring/issues.py` (16 entries) misses `E-easy`, `Easy to Fix`, `Easy fix`, `difficulty: easy`, `Difficulty: Easy`, `difficulty: 1`, `effort: few hours`, `size: XS/S`, `beginner friendly`, `exp:novice`, `new contributor`, `Paper Cut`, `low-hanging-fruit`, `first-timers-only` variants with emoji, and treats `help wanted`/`bug`/`documentation` as uniformly positive although LLVM says the opposite for `help wanted` and ESEM finds `bug` not predictive.
- Difficulty/effort/size ladders are structured data: parse into `difficulty ∈ {easy, medium, hard}`, `effort ∈ {hours, days, weeks, open-ended}`, `size ∈ {XS…XXL}` and show them; penalise `hard`, `weeks`, `∞`, `L/XL`.
- The beginner label should be discovered **per repo** (git-into-gsoc already has `pick_beginner_label` for repo health and `beginner_issue_labels` in `ContributionGuide`); the issue search should use that repo-specific label, like up-for-grabs' `upforgrabs.name`.

---

## 6. Keeping results fresh: cron, caching, re-checks

| Tool | Refresh | Freshness guards | Cost control |
|---|---|---|---|
| goodfirstissue.dev | daily 08:00 UTC Action → Vercel Blob → deploy hook | skip repos with `pushed_at` > 90 days; 10 newest issues per label | 1 req/s, 5 threads, pause at <100 remaining |
| forgoodfirstissue | every 6 h, commit `generated.json` to `deploy` branch | `pushed:>=1 month`; `has_new_issues` ≤7 days; auto-remove failing repos | GraphQL 25 repos/request, 1 s sleep, Octokit throttle/retry |
| up-for-grabs | stats Mon/Wed/Fri 13:00; deprecation sweep Sun 18:00 as a bot PR | one GraphQL query per project (`totalCount` + newest `updatedAt`); archived/missing/issues-disabled removed; 3-year inactivity reported | browser: localStorage 24 h + ETag + rate-limit-reset memo |
| CodeTriage | Sidekiq daily populate; emails daily per user | issues untouched 24 h → closed; **live re-fetch before send**; skip commented/PR-attached | per-user backoff by click recency; streaks |
| youzi-forge | every 3 days | rolling 5-day `created:` windows; ≥1000 ★ | GraphQL |
| GFI-Bot | scheduled incremental `gfibot.data.update`, periodic retrain | none | multiple tokens |
| git-into-gsoc today | on demand | `updated:>=1y`, timeline check for top N | disk cache + ETag + stale-if-error + search throttle |

Takeaways: nobody does webhooks (all cron); 6-24 h staleness is accepted but **nothing checks the issue right before showing it except CodeTriage**, git-into-gsoc's timeline fetch is the equivalent and should stay. The single GraphQL label query used by up-for-grabs (`label(name:){issues(states:OPEN, first:1, orderBy UPDATED_AT){totalCount nodes{updatedAt}}}`) is the cheapest "how many beginner issues and how fresh" probe available and could replace the per-org `beginner_issue_counts` search call when a repo list is known.

---

## 7. UX: what makes an issue list useful to a beginner (and what users complained about)

**Users asked for, repeatedly:** activity/recency per repo (up-for-grabs #175 since 2015, #1142 since 2019; DeepSource #2568), filters by stars/activity (#2615), accurate counts (#2561), custom labels (cutenode #1085; CodeTriage #1680), not receiving closed/already-taken issues (CodeTriage #525), language subscriptions (#131), excluding things you already touched (#304), and pagination/filters (up-for-grabs #665, #1115, #250).

**Patterns worth copying**
- Show *per issue*: age, comment count, "new this week" badge (forgoodfirstissue), size/difficulty label if present, and, unique to git-into-gsoc, availability status with the reason and the newest claim age.
- Show *per repo*: beginner-label name and link (up-for-grabs), open beginner count with freshness, last push, "newcomers merged" (git-into-gsoc), lottery factor / PR velocity (OpenSauced vocabulary), the project's **claim policy and limits**.
- Deliver, don't just list: CodeTriage's daily email with one or three issues, a streak, and coaching text is the only mechanism that gets people to actually open an issue; its backoff keeps it from becoming spam.
- Give the mechanics: first-contributions for git basics; Oppia-style "reproduce and prove it first" and scikit-learn's "comment with your approach" before claiming; takanome's bot replies to prose claims with "use the command".
- Expose the claim etiquette per project (Zulip: one at a time; pandas: `/take`, 7 days; Oppia: video proof) instead of a generic "comment to claim".

**Patterns to avoid**
- Capped counts presented as totals (DeepSource `10 issues`).
- Random ordering as the only order (up-for-grabs, forgoodfirstissue, cutenode "feeling lucky"), beginners want "fresh and uncontested first".
- Hard-coded "Assigned to: unassigned!" (cutenode) when the query did not filter assignees.
- Emailing issues without a last-second check (CodeTriage #525).
- Accepting any repo submission without automated criteria (forgoodfirstissue "[New Project]" spam), git-into-gsoc should keep scoping to official GSoC orgs.
- Ranking by stars (forgoodfirstissue sort), RecGFI shows project background matters less than issue text and participant experience for *within-project* ranking.

---

## 8. Synthesis

### 8.1 Brilliant ideas worth adapting
1. **Ground truth from history, not labels** (RecGFI/GFI-Bot): an issue "resolved by someone with ≤k prior commits" is the real definition of a newcomer-friendly issue. git-into-gsoc already samples merged PRs per repo; the same sample yields *which closed issues were fixed by first-timers*, i.e. a per-repo list of "issues like this one get merged from newcomers".
2. **"Just enough" reporter experience and experienced participants as a quality signal** (RecGFI LIME): an issue filed by a core maintainer who writes many issues, then labelled/edited by another maintainer, is the best bet; an issue filed by a drive-by user with no maintainer touch is not.
3. **Text evidence beats labels early in an issue's life** (RecGFI: 89.7 % of issues unlabeled at creation; ESEM: readability/text-richness/code-snippet features dominate): a cheap readability + structure score on the body can rank fresh issues before anyone labels them.
4. **Claim limits and auto-release as first-class data** (pandas, Zulip, takanome, gemini-cli): the "five claimants" problem is solved socially by limits and expiry; a recommender can *apply the repo's own expiry rule* to decide whether an old claim still blocks the issue.
5. **Live re-check before surfacing + skip-what-you-touched** (CodeTriage `valid_for_user?`).
6. **One GraphQL query per repo for beginner-label count and freshness** (up-for-grabs tooling).
7. **Per-project beginner label and claim-exclusion labels encoded as data** (up-for-grabs YAML, cutenode queries, awesome-for-beginners `label`).
8. **Engagement-based digest backoff and streaks** (CodeTriage `EmailRateLimit`).
9. **Personalised ranking inputs** (PFIRec): task type, language, domain, activeness, sentiment, most of which git-into-gsoc can derive from the user's own PRs.
10. **Rolling time windows to beat the 1,000-result cap** (youzi-forge).

### 8.2 Proven patterns
- Scope to a curated allowlist (DeepSource/up-for-grabs/forgoodfirstissue), git-into-gsoc's "official GSoC orgs only" is the right analogue.
- Exclude archived repos and inactive repos (90 days / 1 month / 3 years thresholds in use).
- Union of several beginner labels; language tags only when a threshold of repos exists.
- Daily or 6-hourly refresh; ETag revalidation; explicit rate-limit backoff with reset timestamps.
- Validation of curated data in CI and bot-authored cleanup PRs.

### 8.3 Pitfalls to avoid
- Trusting `good first issue` alone: 40.9 % of labelled GFIs are not solved by newcomers; scikit-learn "rarely uses" the label; LLVM's `help wanted` is explicitly *not* beginner; JabRef's GFIs "vary in difficulty".
- Multi-`org:` queries that rely on legacy OR semantics (§4.1).
- Static label lists; emoji/case variants; `help wanted` as a positive everywhere.
- Treating any "I'd like to work on this" as a durable claim: repos expire claims in 7-14 days and bots unassign; conversely treating only prose as claims and ignoring `/take`, `.take`, `@zulipbot claim`.
- Ranking by stars or randomly; showing capped counts; emailing/listing without a last-second check.
- GPL code (gfi-bot), ideas only.
- Encouraging bounty hunting or "please assign me" spam; QGIS/matplotlib/mixxx now label suspected AI/spam contributors.

---

## 9. Feature proposals for git-into-gsoc

Effort: S ≤ 1 day, M = 2-4 days, L ≥ 1 week. File references are to the current tree.

| # | Proposal | Effort | Evidence / source |
|---|---|---|---|
| **P1** | **Advanced-search-safe query builder.** In `GitHubClient.find_beginner_issues` and `beginner_issue_counts`, emit `(org:a OR org:b …)` and `(label:x OR label:y)` and pass `advanced_search=true` explicitly (GraphQL alternative: `search(type: ISSUE_ADVANCED)`); merge the two label searches into one request; add a unit test with the recorded legacy-vs-advanced fixtures; cap owners per query at 16. | S | §4.1 experiments (120 vs 0 results); GitHub changelog 2025-03-06; REST docs |
| **P2** | **Claim-bot-aware availability.** Extend `availability.py`: command-claim regexes (`@zulipbot claim`, `@rustbot claim`, `/assign`, `/assign-me`, `/take`, `.take`, `.take-issue`, `/claim`), release commands and bot "unassigned due to inactivity" comments clear claims; count `assigned`/`unassigned` timeline events (not just the current `assignees` field) to compute "assigned N days ago, no PR"; parse claim-state labels (`in progress`, `📍 Assigned`, `State: Work In Progress`, `Has PR`, `claimed`) and blocking labels (`Needs Triage`, `awaiting triage`, `Needs Info`); apply a **repo-specific expiry** (default 14 d; pandas/gemini 7 d; JabRef 8 d; scikit-learn 14/28 d) so lapsed claims become "ask if still active" instead of `claimed`. | M | §3; pandas `comment-commands.yml`; zulipbot docs; takanome README; scikit-learn contributing |
| **P3** | **Per-repo claim policy + "how to claim here".** In `contribution_guide`, detect `.github/workflows/*{assign,take,claim}*`, `triagebot.toml` `[assign]`, `@zulipbot`/`/take`/`.take-issue` strings in CONTRIBUTING, and the limit/expiry numbers; expose `claim_command`, `max_open_claims`, `auto_unassign_days`, `proof_required` (Oppia) on `ContributionGuide`; have `issue` print a ready-to-paste claim comment that follows the policy (approach + reproduction, never "please assign me"). | M | §3.1 table; Oppia wiki; scikit-learn guide; DeepSource #2615 thread as the anti-pattern |
| **P4** | **Per-repo beginner-label discovery and taxonomy normalisation.** Replace the static `POSITIVE_LABELS` with: (a) repo label list (already fetched in `contribution_guide`) matched against a regex family for GFI variants, easy synonyms, difficulty/effort/size ladders, mentor labels, GSoC labels; (b) normalised fields `difficulty`, `effort`, `size`, `mentored`, `gsoc_tagged` on `IssueCandidate`; (c) description-aware negatives (`help wanted` whose description says "Not [good first issue]"; `Impact: Low`). Ship the regex table as `data/label_taxonomy.json` with the 48-repo sample as test fixtures. | M | §5 label sample (`B-labels.tsv`); up-for-grabs `upforgrabs.name` design |
| **P5** | **Research-backed newcomer-fit score with "why" lines.** Add to `score_issue`: body structure (code fences, URLs, images, numbered steps), a Flesch/ARI readability proxy, comment count/length penalties, label category (enhancement/docs/test ↑, untriaged ↓, hard/weeks/∞ ↓), reporter `author_association` + "reporter has had newcomer-resolved issues" (from the repo PR sample), maintainer labelled/edited events, repo-level `newcomers_merged` ratio; keep weights in `data/scoring_weights.json`; print the top 3 contributing signals per issue (LIME-style). Validate offline with the Zenodo GFI dataset or a self-built set of closed issues resolved by ≤1-commit authors in 20 GSoC repos. | M (L with the offline validation) | §2.2-2.3; RecGFI Table 5/LIME; ESEM Table 2 |
| **P6** | **Local issue digest for tracked repos.** `git-into-gsoc digest` (+ MCP tool/resource): for repos in the progress store, search `created:>=<last run>` with the repo's beginner label, run the availability check, skip issues the user commented on (`commenter:@me`) or already tracked, and print 1-3 "fresh and free" issues with a streak counter; honour a CodeTriage-style backoff (`--quiet` days after no action). No email, no server. | M | CodeTriage `IssueAssigner`, `EmailRateLimit`, `#525`; brief's "no digest" weakness |
| **P7** | **Repo newcomer-friendliness metrics in `repo` grade.** From the PR sample already fetched: lottery factor (share of PRs by top 2 authors), PR velocity, new/alumni contributor counts (30/90 d), % of beginner-labelled issues closed by first-time authors, median first maintainer response on GFIs (one timeline call for a sample of 10). Display next to the grade; feed `gfi_newcomer_ratio` into P5. | M | OpenSauced glossary; GFI-Bot `USE_CASES.md` (median response time, issues resolved by newcomers); RecGFI project features |
| **P8** | **PFIRec-lite personalisation in `recommend`.** From the user's merged PRs (`search/issues author:X is:pr is:merged`): languages, file-extension mix (docs/tests/UI/backend), task-type keywords, activity in last 90 d; rank issues by match to task type + language + domain, and prefer repos where similar newcomers got merged. Keep explainable (no ML). | M | PFIRec abstract (task type, language, domain; expertise preference, OSS experience, activeness) |
| **P9** | **Issue→code pointers.** Extract file paths, symbols, stack-frame lines and `owner/repo#n` references from the issue body/comments; check they exist in the default-branch tree (one `git/trees` call, cached); for closed beginner issues in the same repo, show the median files-changed of the fixing PRs ("fixes here usually touch 1-2 files"); print "start reading at …". | L (overlaps the codebase-understanding stream) | ESEM: fewer modified files/less complex file predicts GFI; Tan: newcomers want pointers; Oppia proof-of-fix |
| **P10** | **Cheap beginner-count probe.** Replace `beginner_issue_counts` search (1 of 30/min) with the up-for-grabs GraphQL label query per repo (count + newest `updatedAt`) when ranking an org's repos; cache 6 h. | S | up-for-grabs `github_repository_label_active_check.rb` |
| **P11** | **Spam / AI-policy awareness.** Detect labels like `PossiblyAiBot`, `hacktoberfest: spam`, `AI`, and CONTRIBUTING/triagebot `llm_policy_url` or "AI tools" sections (scikit-learn, Rust); print the disclosure rule in `issue` and `repo`; demote bounty-tagged issues for beginners. | S | QGIS/matplotlib/mixxx labels; rust `triagebot.toml`; scikit-learn page notice; Hackernoon bounty experiment |
| **P12** | **Non-GitHub tracker awareness.** Many GSoC orgs (GNOME, KDE, Inkscape, Wikimedia, LibreOffice, Blender, Mozilla) are not on GitHub; detect tracker type from org links and point to their newcomer pages/labels (GitLab `Newcomers`, Phabricator `good first task`, Bugzilla `good-first-bug`/EasyHack, Codetribute) instead of returning nothing. Start with links; GitLab API search later. | S (links) / L (GitLab API) | Codetribute design; hkirat list includes gitlab.com/inkscape; label sample gaps |
| **P13** | **Contested-season mode.** When the GSoC phase is "orgs announced → application deadline", default to `comments:<3`, `created:>=60d`, exclude issues with ≥2 claimants in 14 d, and show claimant count + newest-claim age in the table; explain Zulip's "one issue at a time" norm. | S | DeepSource #2615 (4 claimants in 3 days); Zulip/pandas limits; existing `CONTESTED_MIN_CLAIMANTS` |
| **P14** | **MCP resources/prompts for policies and taxonomies.** Expose `gsoc://repo/{owner}/{repo}/claim-policy` and `gsoc://labels/taxonomy` as MCP resources and a "draft a claim comment" prompt so agents stop inventing "assign me" comments. | S | brief's MCP weakness; §3.2 |
| **P15** | **Stale-claim takeover helper.** For `claimed` issues whose claim exceeds the repo's expiry with no PR, generate the polite check-in comment ("Hi @x, are you still working on this? If not I'd like to pick it up") and schedule a 3-day reminder in the progress store, mirroring Zulip's documented procedure. | S | Zulip contributing guide (2 weeks, 2-3 days); scikit-learn 2/4 weeks |

Suggested order: P1 → P2 → P4 → P5 → P13 → P6 → P3 → P7 → P8 → P10/P11/P14/P15 → P9/P12.

---

## 10. Licensing and attribution notes

- We adapt ideas only; no code is copied. Licenses as reported by the GitHub API on 2026-10-20: DeepSourceCorp/good-first-issue **MIT**; codetriage/CodeTriage **MIT**; github/forgoodfirstissue **MIT**; up-for-grabs/up-for-grabs.net **NOASSERTION** (a `LICENSE` file and a `licenses/` folder exist, read before reusing any text or data); up-for-grabs/tooling (not checked); cutenode/good-first-issue **none detected by API** (package.json says MIT); MunGell/awesome-for-beginners **none detected** (list data; treat as all-rights-reserved unless the repo states otherwise); firstcontributions/first-contributions **MIT**; osslab-pku/gfi-bot **GPL-3.0** (ideas and paper findings only; never port code); open-sauced/app **Apache-2.0**; open-sauced/pizza-cli **MIT**; open-sauced/docs (not checked); bdougie/take-action **MIT**; takanome-dev/assign-issue-action **MIT**; youzi-forge/good-first-issue-autoUpdate **MIT**; EddieHubCommunity/good-first-issue-finder **MIT**; mozilla-frontend-infra/codetribute (not checked); apache/beam workflow **Apache-2.0**; pandas workflow **BSD-3-Clause** (project license); kubernetes-sigs/prow **Apache-2.0**.
- Papers are © ACM/IEEE; quoting numbers with citation is fine. The RecGFI/GFI-Bot replication dataset on Zenodo (10.5281/zenodo.6665931) has an unchecked license, verify before using it for offline validation (P5).
- If P4 ships a label-taxonomy table derived from the public label names of GSoC-org repos, cite the sampled repos in the data file header; label names and descriptions are factual metadata, not creative works, but attribution is cheap and consistent with the project's "cite sources" rule.

---

## Appendix A: Reproduction commands

- Label sample: `gh api repos/{owner}/{repo}/labels --paginate --jq '.[] | [.name, .description] | @tsv'` for the 48 repos listed in §5 → `B-labels.tsv`.
- Advanced-search experiment: `gh api -X GET search/issues -f q='is:issue is:open label:"good first issue" org:zulip org:oppia' -f per_page=1 --jq .total_count` (120) vs the same with `-f advanced_search=true` (0) vs `-f q='… (org:zulip OR org:oppia)' -f advanced_search=true` (120).
- Workflow files: `gh api repos/{r}/contents/.github/workflows/{file} --jq .content | base64 -d` for pandas `comment-commands.yml`, `unassign-inactive.yml`; apache/beam `self-assign.yml`; google-gemini/gemini-cli `gemini-self-assign-issue.yml`, `unassign-inactive-assignees.yml`; JabRef `unassign-issues.yml`, `on-issue-unassigned.yml`; PalisadoesFoundation/.github `auto-assign.yml`; openwisp/openwisp-utils `reusable-bot-autoassign.yml`.
- Paper text: `pdftotext -layout` on https://hehao98.github.io/files/2022-recgfi.pdf and https://www.eecs.yorku.ca/~wangsong/papers/esem21b.pdf.

## Appendix B: Things I could not verify
- goodfirstissues.com's former implementation/author (domain lapsed; archive blocked).
- Quine/Quira matching algorithm beyond marketing snippets; whether Quests still run.
- OWASP BLT-Action's exact limits (repo 404 for me); Opire bot command names; Polar issue-funding status; IssueHunt OSS-bounty status.
- LibreOffice EasyHacks and Wikimedia/GNOME newcomer label conventions (pages blocked or not fetched).
- Whether GitHub will still flip the REST `search/issues` default to advanced search (announced for 2025-09-04; not in effect on 2026-10-20 per my tests).
- gfibot.io may be temporarily down rather than dead (HTTP 522 with Retry-After 120, twice).
