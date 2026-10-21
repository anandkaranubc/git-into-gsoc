<!-- Research working notes. Written 2026-10-20/21 during the ecosystem research pass; kept as the evidence base for ../research.md. Claims marked unverified were not confirmed against a primary source. Plain-language rules apply loosely here; these are notes, not a guide. -->

> Working notes from the research pass of October 2026. Repository health metrics, GraphQL costs, ecosyste.ms, and what predicts a merged newcomer pull request. The checked conclusions are in [the research summary](../research.md); these notes keep the evidence, numbers, and URLs behind them. Items marked unverified were not confirmed against a primary source.

# Stream C: Repository health, community-health metrics, and project-discovery engines

Research date: 2026-10-20/21 (all live probes ran 2026-10-21 ~03:28-03:40 UTC with `curl` and the authenticated `gh` CLI). Raw probe outputs are saved under `(session working files, not included)` (GraphQL queries `q1.graphql`..`q4.graphql`, JSON responses, ecosyste.ms OpenAPI specs).

Anything I could not confirm from a primary source is marked **unverified**.

---

## TL;DR

1. **git-into-gsoc's two "newcomer" signals are structurally broken, not just noisy.** GitHub computes `author_association` *at query time*; once a PR is merged its author becomes `CONTRIBUTOR` ("has previously committed to the repository"), so `FIRST_TIME_CONTRIBUTOR` essentially never appears on a merged PR and `newcomers_merged` is ≈0 by construction. Conversely `NONE` on a closed PR means "never got anything merged", so `outsider_merge_rate` is biased downward in a way that depends on how many rejected drive-by PRs a repo attracts. Verified on sympy/sympy (50 closed PRs: merged = 23 CONTRIBUTOR + 8 MEMBER, zero NONE; closed-unmerged = 13 NONE + 5 CONTRIBUTOR + 1 MEMBER). Fix: define *insiders* as `assignableUsers ∪ {OWNER,MEMBER,COLLABORATOR}` (one GraphQL field, public on public repos) and measure outsiders against that.
2. **One GitHub GraphQL query replaces the ~7 REST calls in `repo_health` and costs 3-4 rate-limit points** (measured with `rateLimit{cost}`). It returns in one round trip: 50 recent closed PRs with author association, size, and the first 6 timeline items (so you can compute *time to first human response*, skipping bots and the author), 30 labelled issues with first comment author/association, up to 100 `assignableUsers` (maintainer/triage set, on sympy the 7 "active maintainers" that ecosyste.ms derives independently were all inside this set), CONTRIBUTING/CoC/templates, the `.github/workflows` tree, the last 30 commit messages (DCO sign-off and Conventional-Commits ratio for free), and `statusCheckRollup` contexts of recent merged PRs (CLA/DCO check names). A 6-repo aliased version 504'd; keep one repo per query.
3. **The strongest empirical predictors of a newcomer's PR being merged/reviewed fast are social and process signals, not popularity.** Across 3.35M PRs (Zhang et al., TSE): whether submitter == integrator (31% of explained variance), PR lifetime (21%), integrator's review experience (13.5%), presence of comments (12%, negative), core membership (5%); project-level factors explain ~1%. Across 659k PRs (Tsay et al., ICSE'14): stars *reduce* acceptance (OR 0.648/unit), long diffs reduce it (OR 0.738), prior interaction (OR 1.356) and following the integrator (OR 2.87) raise it, tests help (OR 1.171). Time-to-first-*human*-response explains 64.7% of PR-lifetime variance vs 0.33% for bot responses, and newcomers who get a human reply within a day keep contributing ~15% more often (Hasan et al., 111k PRs). So: measure first *human* response, outsider merge rate against a real insider set, open-PR workload, and PR size norms; stop rewarding stars.
4. **ecosyste.ms is a legitimate zero-GitHub-token data source for most of what `repo` and `repos ORG` need**, with a 15,000 req/h "polite" tier and 24h cache headers: `repos.ecosyste.ms` (metadata file detection incl. `dco`, `cla`, `governance`, `maintainers`, `codeowners`, `security`; `commit_stats.dds`; embedded Scorecard), `issues.ecosyste.ms` (per-repo past-year PR/issue counts, merged PR count, distinct PR authors, avg time to close, bot counts, label histograms; *org-level* `maintainers`/`active_maintainers` from author association), `commits.ecosyste.ms` (past-year committers with counts, one-commit committers ≈ drive-through newcomers, and `past_year_dds`). `timeline.ecosyste.ms` 500'd on a large repo; don't depend on it. It does **not** expose time-to-first-response.
5. **CLA/DCO/commit-convention requirements are cheaply detectable and currently invisible to the tool.** Observed status-check names: `cla/google` (angular), `EasyCLA` (kubernetes), `DCO` (envoy), `Verify CLA` (oppia). Commit-message probes: envoy 27/30 recent commits `Signed-off-by`, angular 30/30 Conventional Commits. Config files: `.github/dco.yml`, `.clabot`, the 16 commitlint config filenames, `.cz.toml`, `release-please-config.json`, CODEOWNERS. A "before you open a PR" card built from these is the single most beginner-protective feature in this stream.
6. OpenSSF Scorecard's public API (`api.scorecard.dev`, mirror `api.securityscorecards.dev`) is useful only for repos in the ~1.3M weekly scan (sympy, oppia: 200; sympy/planet-sympy: 404) and omits CI-Tests/Contributors in weekly runs; its `Maintained` formula (commits + maintainer issue activity in 90 days, normalised to 12) is worth copying, the rest is security-oriented and should be informational only.

---

## 1. Baseline: what git-into-gsoc computes today

Source: `src/git_into_gsoc/github/client.py` (`repo_health`, lines 268-313), `src/git_into_gsoc/github/repos.py` (`pull_stats`, `pick_beginner_label`, `repo_lead_score`), `src/git_into_gsoc/scoring/health.py`.

REST calls per `repo` (≈7, plus 1 if a beginner label exists): `GET /repos/{o}/{r}`, `/community/profile`, `/actions/workflows?per_page=1`, `/pulls?state=closed&per_page=60&sort=updated&direction=desc`, `/labels?per_page=100`, `/issues?labels=X&state=open&per_page=100`, `/contents/` (root listing for toolchain), raw CONTRIBUTING.

Weights (sum 100): push recency 20 / CONTRIBUTING 12 / CoC 4 / templates 4 / CI (workflow count > 0) 8 / open beginner issues 10 (label-only 4) / human merge rate 12 / outsider merge rate 12 / median hours-to-merge 10 / license 4 / stars band 4. `newcomers_merged` is displayed but unweighted. Grades: A≥85, B≥72, C≥58, D≥45.

Definitions that matter for the critique in §5: `OUTSIDER_ROLES = {CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, FIRST_TIMER, NONE}`, `FIRST_TIMER_ROLES = {FIRST_TIME_CONTRIBUTOR, FIRST_TIMER, NONE}`; `median_hours` is open→merge over *merged* human PRs only; the sample is the 60 most recently *updated* closed PRs.

---

## 2. Project deep-dives

### 2.1 OpenSSF Scorecard (ossf/scorecard)

- URL: https://github.com/ossf/scorecard, Apache-2.0 (code); result data licensed CDLA-Permissive-2.0 (README). Go. Very active (API result for sympy dated 2026-10-12, scorecard v5.6.0).
- **What it does:** runs ~19 checks per repo and scores each 0-10; a weekly cron scans "more than 1.3 million repositories" and serves results from `api.scorecard.dev` (the README's host; `api.securityscorecards.dev` also answered 200 in my probe), cached on Fastly (`cache-control: max-age=600`). The README states the BigQuery public dataset is **no longer available**. Weekly-scan results **omit CI-Tests, Contributors and Dependency-Update-Tool** "due to API cost", confirmed: sympy's API payload has 14 checks and none of those three.
- **Coverage probe:** `GET https://api.scorecard.dev/projects/github.com/sympy/sympy` → 200 (score 5.6); `oppia/oppia` → 200 (6.7 via the ecosyste.ms mirror); `sympy/planet-sympy` → 404. Small GSoC-org repos will often be 404; the REST API only has pre-computed results (repos join by being in `ossf/scorecard-infra`'s list or by publishing from the GitHub Action).
- **How the relevant checks are computed** (docs/checks.md and source, fetched):
  - *Maintained* (risk High): `lookBackDays = 90`, `activityPerWeek = 1`; threshold `= 1*90/7 = 12` (Go integer division); score `= min(10, 10 * (commits_in_90d + issues_with_member_activity_in_90d) / 12)` with truncating integer division (`checker.CreateProportionalScore`). Archived → 0; created < 90 days ago → 0. "Member activity" = an issue *created or commented* within 90 days by an author whose association is ≥ `COLLABORATOR` (so COLLABORATOR/MEMBER/OWNER), each issue counted once (`probes/issueActivityByProjectMember/impl.go`). Source: https://raw.githubusercontent.com/ossf/scorecard/main/checks/evaluation/maintained.go, https://raw.githubusercontent.com/ossf/scorecard/main/probes/issueActivityByProjectMember/impl.go, https://raw.githubusercontent.com/ossf/scorecard/main/checker/check_result.go.
  - *Code-Review* (High): looks at ~30 most recent changesets; counts GitHub/GitLab approvals, "merger ≠ committer" as implicit review, Prow `lgtm/approved` labels, Gerrit `Reviewed-by`; bot reviews (incl. AI bots) don't count; leveled deductions (−3 unreviewed bot change, −7 one unreviewed human change, −3 more if several). Result for sympy: "Found 17/21 approved changesets -- score normalized to 8".
  - *CI-Tests* (Low): CheckRuns/Statuses on roughly the last 30 commits; a CI system counts if its name contains one of `appveyor, buildkite, circleci, e2e, github-actions, jenkins, mergeable, test, travis-ci, woodpecker`; only *successful* runs count. **Not in weekly data.**
  - *License* (Low): 6 pts license file (LICENSE/LICENCE/COPYING/COPYRIGHT or `LICENSES/`), +3 top-level, +1 FSF/OSI-approved. sympy got 9/10 because GitHub reports its license as `NOASSERTION`/"other".
  - *Contributors* (Low): last 30 commits must include ≥3 companies (profile "Company" field) each with ≥5 commits. **Not in weekly data**, and the signal is about corporate diversity, not newcomer-friendliness.
  - *Branch-Protection*: tiered 3/6/8/9/10 (force-push/deletion → ≥1 reviewer → status check → 2 reviewers + CODEOWNERS → dismiss stale + include admins); without an admin token, admin-only settings are assumed met.
- **Payload shape:** `{date, repo{name,commit}, scorecard{version,commit}, score, checks[{name,score,reason,details[],documentation{url,short}}]}`.
- **UX worth copying:** every check has a one-line `reason` with the raw counts ("30 commit(s) and 13 issue activity found in the last 90 days") plus `details[]`, an explainable score. git-into-gsoc's `signals[]/warnings[]` is the same idea; keep it, and show counts rather than adjectives.
- **Critical assessment:** high-quality, well-maintained, authoritative. Relevance to GSoC newcomers is narrow: *Maintained*, *Code-Review* and *License* are useful context; *Branch-Protection*/*Token-Permissions*/*Pinned-Dependencies* are security posture and would mislead a beginner if folded into an onboarding grade. Also, the ecosyste.ms mirror embeds an older Scorecard run (sympy: 2025-08-11, score 3.8) than the live API (2026-10-12, score 5.6), prefer the API when present.

### 2.2 CHAOSS metrics, Augur and 8Knot

- CHAOSS metric definitions (https://chaoss.community/kb/…, all fetched):
  - **Time to First Response** (https://chaoss.community/kb/metric-time-to-first-response/): time from creation of a PR/issue/email to the first response; filters: responder role (e.g. maintainers only), *exclude bots*, activity type. No aggregator or threshold mandated.
  - **Issue Response Time** (https://chaoss.community/kb/metric-issue-response-time/): first comment by someone *other than the author*; filters: responder role, bot vs human, opener's role (new vs long-time), status.
  - **Change Request Acceptance Ratio** (https://chaoss.community/kb/metric-change-request-acceptance-ratio/): merged vs closed-without-merge; filter by *fork vs branch origin* (fork ≈ outsider). Explicitly: "ratios should be interpreted in the context of each project".
  - **Contributor Absence Factor** (formerly Bus Factor; https://chaoss.community/kb/metric-bus-factor/): smallest number of contributors whose contributions sum to >50% of the total; per contribution type and time window.
  - **New Contributors** (https://chaoss.community/kb/metric-new-contributors/): first contribution of any type (commit, issue, PR, review) in a period.
  - **Newcomer Experience** (DEI focus area; https://raw.githubusercontent.com/chaoss/wg-dei/main/focus-areas/project-and-community/newcomer-experience.md): quantitative indicators are *subsequent contributions from first-time contributors* and *New Contributors Closing Issues*; the rest is survey-based. There is no CHAOSS metric literally named "Project Onboarding" (searched `org:chaoss`; the hits are `wg-dei/.../newcomer-experience.md`, `wg-metrics-development/focus-areas/time/time-to-first-response.md`, `wg-data-science/practitioner-guides/responsiveness.md`).
  - **Responsiveness practitioner guide** (https://raw.githubusercontent.com/chaoss/wg-data-science/main/practitioner-guides/responsiveness.md): read Time to First Response, Time to Close (median, not mean, "the median is closer to what contributors experience"), and Change Request Closure Ratio *together*; example benchmark "a human response within two business days"; growing the reviewer pool via OWNERS/CODEOWNERS, publishing expected response times in CONTRIBUTING, and templates that aren't so demanding they scare newcomers.
- **Augur** (https://github.com/chaoss/augur) collects into Postgres; **8Knot** (https://github.com/oss-aspen/8Knot, MIT, ~80 stars, Red Hat OSPO, "alpha") visualises it. From its source tree (listed via `gh api repos/oss-aspen/8Knot/contents/8Knot/pages/...`): `contributors/`: `new_contributor.py` (a contributor's first "rank-1" action of any type, counted per interval), `contrib_drive_repeat.py` ("drive-through" = fewer than N actions in a repo, "repeat" = ≥N; N is a UI parameter), `first_time_contributions.py`, `active_drifting_contributors.py`, `contrib_importance_pie.py`; `contributions/`: `pr_first_response.py` (share of PRs opened per day that received ≥1 message within N days; a `bot-switch` removes known bots), `pr_review_response.py`, `pr_staleness.py`, `issue_staleness.py`, `self_merge_rate.py`; `chaoss/`: `project_velocity.py`. These are exactly the newcomer-relevant metrics, defined simply enough to reimplement over a 50-PR GraphQL sample.
- **GrimoireLab** (https://github.com/chaoss/grimoirelab): same metric family, Elasticsearch/Kibana; has "retention newcomers" panels (`grimoirelab-sigils/panels/json/gerrit_retention_newcomers.json`). Heavy infrastructure; not a data source for a CLI. Not studied further.
- **Assessment:** CHAOSS gives the vocabulary and the *interpretation* rules (medians, bots excluded, responder role filter, context-dependence). Nothing here is a hosted API you can call; the value is in adopting the definitions verbatim so the tool's numbers are explainable and comparable.

### 2.3 ecosyste.ms (repos / issues / commits / timeline)

All four services are open source (AGPL-3.0 per the ecosyste-ms org repos; **unverified** for each individual repo, I read model/controller source but not LICENSE files). OpenAPI specs: `https://{repos,issues,commits,timeline}.ecosyste.ms/docs/api/v1/openapi.yaml` (saved locally). Swagger UI pages are JS-only; fetch the YAML.

**Rate limits and caching (observed headers):** `x-ratelimit-limit: 15000`, `x-ratelimit-tier: polite`, `x-ratelimit-consumer: anonymous` on issues/commits/timeline; the tier was "polite" with or without an email in the User-Agent. Responses carry `cache-control: public, max-age=86400, stale-while-revalidate=…, stale-if-error=86400` and ETags, exactly what git-into-gsoc's disk cache already honours.

**repos.ecosyste.ms**, `GET /api/v1/hosts/GitHub/repositories/{owner}/{repo}` (or `/api/v1/repositories/lookup?url=…`). Fields of interest (sympy probe): `archived, fork, pushed_at, stargazers_count, open_issues_count, forks_count, subscribers_count, default_branch, last_synced_at (2026-10-14), language, license ("other"), topics, pull_requests_enabled, created_at, tags_count, scm, purl`; **`metadata.files`** with detected paths for `readme, changelog, contributing, funding, license, code_of_conduct, threat_model, audit, citation, codeowners, security, accessibility, support, governance, roadmap, authors, dei, publiccode, codemeta, zenodo, notice, maintainers, copyright, agents, claude, gemini, cursor, copilot, dco, cla, disclosure`; `metadata.funding`; **`commit_stats {total_commits, total_committers, mean_commits, dds, last_synced_commit}`**; **`scorecard {data: full Scorecard payload}`** (may be stale vs the live API). Owner endpoint `/hosts/GitHub/owners/{login}` (sympy: `last_synced_at 2024-05-01`, owner records can be very stale) and `/owners/{login}/repositories?per_page=…&sort=…` returning the full repo objects (metadata + commit_stats + scorecard), one page can replace `list_owner_repos` + per-repo probing for `repos ORG`. Detection regexes (https://raw.githubusercontent.com/ecosyste-ms/repos/main/app/models/repository.rb): `dco: ^(docs/)?(.github/)?(.gitlab/)?DCO(?:\.(md|txt))?$`, `cla: …(CLA|CONTRIBUTOR[-_ ]LICENSE[-_ ]AGREEMENT)(?:\.(md|txt))?$`, `maintainers: …MAINTAINERS(…)`, `governance: …GOVERNANCE`, `codeowners: …CODEOWNERS`, `contributing: …CONTRIBUTING`, `security: …SECURITY`, `support`, `roadmap`, `code_of_conduct: …CODE[-_]OF[-_]CONDUCT`, all case-insensitive and rooted at `/`, `docs/`, `.github/`, `.gitlab/`.

**issues.ecosyste.ms**, endpoints: `/hosts/{h}/repositories/{repo}`, `/…/issues?pull_request=&state=&label=&created_after=&updated_after=&sort=&order=`, `/…/issues/{n}`, `/…/labels`, `/hosts/{h}/owners/{o}`, `/hosts/{h}/owners/{o}/maintainers`, `/hosts/{h}/authors/{login}`, `POST /jobs {url}` (request a sync for a repo not yet indexed; 302 to the job). Repo summary fields (sympy, `last_synced_at 2026-10-20`): `issues_count 1959, pull_requests_count 3605, avg_time_to_close_issue (s), avg_time_to_close_pull_request (s), issues_closed_count, pull_requests_closed_count, pull_request_authors_count 726, issue_authors_count 892, avg_comments_per_*, merged_pull_requests_count 1686, bot_issues_count, bot_pull_requests_count 21`, and the same for `past_year_*` (sympy: 517 PRs, 159 merged, 208 distinct PR authors, avg PR close 2,682,428 s ≈ 31 days), plus `issue_labels_count` / `pull_request_labels_count` histograms (sympy: `"Easy to Fix": 100`, `"good first issue": 7`, `"GSoC": 20`). Per-issue fields: `number, title, user, labels, assignees, comments_count, pull_request, author_association, state, state_reason, time_to_close, merged_at, locked, created_at, updated_at, closed_at`. **No first-response or comment-author data.** Owner payload adds `issue_author_associations_count`, `pull_request_author_associations_count`, `maintainers` and `active_maintainers`, defined in code as authors of issues/PRs whose `author_association ∈ {MEMBER, OWNER, COLLABORATOR}` (`MAINTAINER_ASSOCIATIONS`, `app/models/issue.rb`), "active" = created in the last year (`app/controllers/api/v1/owners_controller.rb`). Org-level only; the repo-level `/maintainers` path is 404. Note: this definition includes anyone who ever had collaborator status when they filed something; it is a proxy, but on sympy the 7 "active maintainers" ⊆ GitHub's 31 `assignableUsers`.

**commits.ecosyste.ms**, `/hosts/{h}/repositories/{repo}` returns `total_commits, total_committers, total_bot_commits, total_bot_committers, mean_commits, dds, past_year_total_commits, past_year_total_committers, past_year_mean_commits, past_year_dds, last_synced_at, committers[{name,email,login,count}], past_year_committers[…]`, plus `/commits?since=&until=` and `/committers/{login}`. Computed from a real clone with `git shortlog -s -n -e --no-merges [--since="1 year ago"]`; **`dds = 1 − (top committer's commits / total)`**, bots = names ending in `[bot]` (https://raw.githubusercontent.com/ecosyste-ms/commits/main/app/models/repository.rb). oppia probe: `past_year_total_committers 87`, `past_year_dds 0.914`, and the `past_year_committers` list shows dozens of logins with 1-3 commits, a direct, zero-GitHub-call proxy for "how many newcomers landed a commit this year" (CHAOSS New Contributors) and for the Contributor Absence Factor (walk the sorted list to 50%).

**timeline.ecosyste.ms**, `/api/v1/events/{repoName}?page=&per_page=` returns GH-Archive-style events (`actor, event_type, payload{…full GitHub object…}`). Worked on `ossf/scorecard-webapp`; **returned HTTP 500 after 30 s on `sympy/sympy`** (`x-runtime: 30.4`). Not reliable for large repos; unsuitable as the backbone of a digest feature.

**Assessment:** mature, well-structured, generous limits, cacheable, and already doing the expensive work (cloning for commit stats; file detection with sane regexes). Weaknesses: freshness varies per service (repos 1-7 days, owners can be >1 year stale), `license` is GitHub's string ("other"), no first-response data, timeline unreliable. It is the right *complement* to GitHub for org-wide ranking and for maintainer/bus-factor signals; it cannot replace GitHub for responsiveness.

### 2.4 OSS Insight (pingcap/ossinsight)

- https://github.com/pingcap/ossinsight, Apache-2.0, ~2.5k stars, TypeScript; data = GH Archive events loaded into TiDB ("10+ billion rows"). Docs: https://ossinsight.io/docs/api.
- **Public API v1 (beta, no key):** base `https://api.ossinsight.io/v1`; observed headers `x-ratelimit-limit: 600` (per hour, per IP) and `x-ratelimit-limit-minute: 100` (docs say 1,000/min global). Endpoint groups: collections, trends, `repos/{owner}/{repo}/issue_creators/{…,countries,history,organizations}`, `pull_request_creators/{…}`, `stargazers/{countries,history,organizations}`. Response shape `{type:"sql_endpoint", data:{columns[],rows[]}}`. No responsiveness metrics in v1.
- **Legacy query endpoints (undocumented but live):** `GET https://api.ossinsight.io/gh/repo/{owner}/{repo}` (proxied GitHub repo JSON, gives `id`), then `GET https://api.ossinsight.io/q/analyze-issue-open-to-first-responded?repoId=640534` → monthly `p0,p25,p50,p75,p100` **in hours** (sympy Oct 2026: p50 9.5 h, p75 42.5 h); `/q/analyze-pull-request-open-to-merged` (same shape; sympy Oct 2026 p50 6.1 h); `/q/analyze-pull-requests-size-per-month` (xs/s/m/l/xl/xxl by additions+deletions); `/q/analyze-issue-opened-and-closed`. The response includes the SQL, which reveals the caveats: "first response" counts **`IssueCommentEvent created` OR `IssuesEvent closed`** by *anyone including the author*, and **bot exclusion is commented out**; the "merged" query counts PRs *closed*, not merged (comment in SQL cites mongodb's workflow). `analyze-pull-request-open-to-reviewed` → 404.
- **Assessment:** great for trend charts and a fast "what does the p50 first response look like per month" fallback that costs zero GitHub tokens; but its first-response definition violates CHAOSS (no bot/author exclusion) and the undocumented `/q/` endpoints may vanish. Use as a cross-check, not a primary.

### 2.5 GitHub-native sources

- **Community profile** `GET /repos/{o}/{r}/community/profile` (https://docs.github.com/en/rest/metrics/community): `health_percentage`, `description`, `documentation`, `files{code_of_conduct, code_of_conduct_file, contributing, issue_template, pull_request_template, license, readme}`, `updated_at`; not available for forks. The docs don't publish the percentage formula. Already used by git-into-gsoc; GraphQL exposes the same facts (`contributingGuidelines`, `codeOfConduct`, `issueTemplates`, `pullRequestTemplates`, `licenseInfo`).
- **Statistics endpoints** (https://docs.github.com/en/rest/metrics/statistics): `/stats/contributors` (per-author totals + weekly `w,a,d,c`; additions/deletions are 0 for repos with ≥10k commits), `/stats/commit_activity` (52 weeks), `/stats/code_frequency` (422 for ≥10k commits), `/stats/participation` (owner vs all per week, the only one that never 202s), `/stats/punch_card`. **202 behaviour:** if not cached, GitHub returns 202, kicks off a background job, and expects you to retry; cache keyed by default-branch SHA. Merge commits excluded. For a CLI this means a retry loop with a deadline; `participation` is the safe one (gives "non-owner commits per week" = `all − owner`).
- **author_association semantics** (GraphQL introspection of `CommentAuthorAssociation`, run 2026-10-21): `OWNER` "Author is the owner of the repository"; `MEMBER` "member of the organization that owns the repository"; `COLLABORATOR` "has been invited to collaborate on the repository"; `CONTRIBUTOR` "has previously committed to the repository"; `FIRST_TIME_CONTRIBUTOR` "has not previously committed to the repository"; `FIRST_TIMER` "has not previously committed to GitHub"; `NONE` "no association"; `MANNEQUIN` placeholder. The definitions are stative ("has previously committed"), i.e. evaluated now, not at PR creation. Empirical confirmation in §5.
- **GraphQL costs and limits** (https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api): 5,000 points/h per user token; cost ≈ (sum over connections of max nodes requested) / 100, min 1; ≤100 per connection, ≤500,000 nodes per query; secondary limits 2,000 points/min for GraphQL and 90 s CPU per 60 s. Measured (see `C-data/q1.graphql`, `q4.graphql`): the full health query cost **3**; the variant with `timelineItems(first:6)` on 50 PRs and `assignableUsers(first:100)` cost **4**; per-repo "requirements" query (tree lookups + 30 commits + 8 merged PRs × 50 status contexts) cost **1**. `collaborators` → `FORBIDDEN` on repos you don't admin, but the rest of the query still returns (partial data + `errors[]`). `assignableUsers` ("users that can be assigned to issues") and `mentionableUsers` are public.
- **Search API** is what `issues` uses today; unchanged here.

### 2.6 GH Archive, BigQuery, ClickHouse playground

- https://www.gharchive.org/: hourly `https://data.gharchive.org/YYYY-MM-DD-H.json.gz` since 2011-02-12 (Events API from 2015); BigQuery `githubarchive.{day,month,year}` updated hourly, 1 TB/month free tier; payloads are JSON strings that change shape over time.
- ClickHouse's public playground (`https://play.clickhouse.com/?user=play`, table `github_events`) answered SQL anonymously but its copy of sympy's events ends **2026-07-02** (≈3.5 months stale; 0 rows in the last 90 days). Fine for research, not for a live CLI.
- **Assessment:** the right tool for *offline* calibration (e.g., fitting weights on thousands of GSoC-org repos) and nothing else for this project, requires GCP billing or a stale mirror.

### 2.7 Discovery and ranking sites

- **star-history** (https://github.com/star-history/star-history, MIT, ~9.6k stars): chart/badge at `api.star-history.com/chart?repos=…`; "We do not accept external contribution". Fetch mechanism not documented on the README (**unverified**: it samples `/stargazers` pages with the `starred_at` media type). Stars are the wrong signal for newcomers anyway (Tsay: OR 0.648).
- **trendshift.io**: daily/weekly/monthly momentum ranking by Julian Li; methodology and API not published; ad-supported. Not usable as a source.
- **ossrank.com**: both fetch attempts failed (socket closed / curl exit 000). **Unverified; skipped.**
- **libraries.io** (https://libraries.io/api): `api_key` required, 60 req/min; package endpoints expose `rank` (SourceRank), `stars`, `forks`, `contributions_count`, `dependents_count`, `repository_status`; the repository endpoints were beyond the 100k characters I read (**unverified**). Package-centric; ecosyste.ms covers the same ground without a key.
- **deps.dev v3** (https://docs.deps.dev/api/v3/): `GET /v3/projects/github.com%2F{o}%2F{r}` returns `openIssuesCount, starsCount, forksCount, license, description, homepage, scorecard{date, checks[], overallScore}, ossFuzz`; "clients are expressly permitted to cache"; no documented rate limit or auth; only projects linked to a known package. A second Scorecard mirror with explicit caching permission.
- **grep.app** (`https://grep.app/api/search?q=…` returned 429 behind a "Vercel Security Checkpoint", the JSON API exists but is bot-gated; **unverified** beyond that) and **Sourcegraph** (`https://sourcegraph.com/.api/graphql`, token-based; docs don't promise anonymous access). Neither is suitable as a dependency; both are good *links to offer the user* for "find where X is implemented".
- "GitHub semantic search projects": not researched beyond the above; no primary source read, **unverified / out of scope**.

### 2.8 Bus-factor tooling

- **Truck-Factor** (https://github.com/aserg-ufmg/Truck-Factor, MIT, ~242 stars, Java + shell/AWK; Avelino et al. ICPC 2016): computes degree-of-authorship per file from `git log`, then greedily removes top authors until 50% of files are orphaned. Needs a clone; the README doesn't restate the DOA coefficients (**unverified** here). Overkill for a CLI; `commits.ecosyste.ms` already serves the cheap variant.
- **git-fame** (https://github.com/casperdcl/git-fame, ~827 stars, Python): per-author surviving lines/commits/files via `git blame`; `--since`, `--bytype`, `--excl`; no bus factor, but its `distribution` column is the same concentration idea. Useful only once the user has a clone (a "post-clone" command could run it).
- **Cheapest adequate approach:** CHAOSS Contributor Absence Factor over `commits.ecosyste.ms past_year_committers` (sorted; count authors until >50%), plus `past_year_dds`.

### 2.9 Good-first-issue research and recommenders

- Tan, Zhou, Sun, "A First Look at Good First Issues on GitHub" (ESEC/FSE 2020; https://2020.esec-fse.org/details/fse-2020-papers/172/A-First-Look-at-Good-First-Issues-on-GitHub): 9,368 GFIs across 816 popular projects; **almost half of GFIs are not solved by newcomers**; GFIs take longer to resolve than ordinary issues; problems: inappropriate GFIs (mechanism), insufficient GFIs (project), uneven skills (newcomer); recommendation: pick GFIs with an informative description and available support.
- Xiao et al., "Recommending Good First Issues in GitHub OSS Projects" (ICSE 2022; RecGFI; https://conf.researchr.org/details/icse-2022/icse-2022-papers/158/Recommending-Good-First-Issues-in-GitHub-OSS-Projects): 53,510 resolved issues, 100 projects, XGBoost over content/background/dynamics features, AUC up to 0.853. Tool: **GFI-Bot** (https://github.com/osslab-pku/gfi-bot, "pre-alpha", ~57 stars). Idea to borrow: label text is a weak proxy; *who actually resolved past "good first issue" tickets* (outsider vs insider) is the real quality signal for a repo's GFI label.
- Alderliesten & Zaidman (CHASE 2021): GFIs are effective for onboarding, but the task types could better match what newcomers actually do first (search summary; https://research.tudelft.nl/en/publications/an-initial-exploration-of-the-good-first-issue-label-for-newcomer).

---

## 3. Evidence: which signals predict that a newcomer's PR gets merged and reviewed quickly

| Signal | Evidence (effect) | Source | Measurable cheaply? |
|---|---|---|---|
| Submitter is also the integrator / has write access | Strongest factor: OR 0.52 for "same_user"; explains 31% of explained variance; `core_member` OR 1.29 [5.3%] | Zhang et al., TSE (arXiv 2105.13970, Table 5; 1,765,730 PRs) | Yes, `assignableUsers` + association |
| PR lifetime / review latency | OR 0.61 [21%]; time-to-first-*human*-response explains 64.7% of PR-lifetime variance (bots 0.33%) | Zhang; Hasan et al. 2023 (arXiv 2304.08426, 111,094 PRs) | Yes, GraphQL `timelineItems(first:6)` |
| Integrator's review experience | `prior_review_num` OR 1.53 [13.5%], i.e., projects with experienced reviewers merge more | Zhang | Proxy: active maintainers (ecosyste.ms) / assignable users |
| Discussion volume | `has_comments` OR 0.63 [12%]; comments OR 0.454 per unit (−54.6%) | Zhang; Tsay et al. ICSE'14 (659,501 PRs) | Yes, `comments.totalCount` |
| Prior interaction with the project | +35.6% per unit (OR 1.356); strongest moderator of the comment penalty; newcomers who got a human reply within 1 day kept contributing 2.63-37.44% more (median 15.14%) | Tsay; Hasan 2023 RQ4 | For the *user*: yes (search `commenter:USER repo:X`) |
| Social distance (submitter follows the integrator) | OR 2.87 (+187%) | Tsay | Yes but creepy; skip, or just advise "engage first" |
| PR size | lines changed OR 0.738 (−26.2%/unit); files changed small; long descriptions and more files/commits/churn → longer waits for first human response (significant in 4-5 of 10 projects) | Tsay; Hasan 2023 RQ3 | Yes, `additions/deletions/changedFiles` of merged outsider PRs |
| Tests included | OR 1.171 (+17.1%) in Tsay; negligible (OR 1.02 [0.01%]) in Zhang | Tsay vs Zhang | Weak; mention in guidance only |
| CI exists / CI failures | `ci_exists` OR 1.16; when CI exists `ci_failed_perc` OR 0.65 explains 18% | Zhang | CI presence: yes (check runs on PR commits) |
| Project workload | `open_pr_num` OR 0.82 [0.47%] | Zhang | Yes, open PR count ÷ active maintainers |
| Popularity / maturity | stars OR 0.648 (−35.2%/unit), repo age OR 0.820, team size OR 0.954 | Tsay | Yes, **invert** the current +4 for stars |
| Author's experience | acceptance climbs with PR count (ansible 54.2%→80.0% over first 50 PRs); novices (few prior PRs, low acceptance) abandon more; `gh_account_duration` top-3 feature for returning | Legay et al. (arXiv 1812.06269, search summary); Li et al. TOSEM (arXiv 2110.15447); arXiv 2104.02933 | For the *user*: yes (`recommend`) |
| Why PRs die | 45.8% difficulty addressing maintainer comments; 22.6% no review; 20.9% CI failures; 14.1% merge conflicts; 9.3% no answer | Li et al., 354 abandoned PRs | Guidance: small PRs, ask first, keep rebasing |
| Day of week / description length | Earlier-in-week submissions and concise descriptions get faster maintainer replies | arXiv 2311.07786 (abstract) | Guidance only |

Caveats: Zhang's `first_pr` (OR 0.95 [0.36%]) and `followers` (OR 1.04) are small; project-level factors explain ~1% of variance, so *any* repo-level grade is a weak predictor compared with how the user behaves (small PR, prior interaction, responsiveness). The grade should therefore be framed as "how this project treats outsiders", and the tool should pair it with behavioural guidance.

---

## 4. Detecting pre-PR requirements (CLA / DCO / conventions / templates / CODEOWNERS)

Empirical probe (`C-data/q3.graphql`, one GraphQL query per repo, cost 1 each, 2026-10-21):

| Repo | Status-check names on recent merged PRs | Last 30 commits `Signed-off-by` | Last 30 commits Conventional-Commits headline | Files found |
|---|---|---|---|---|
| angular/angular | `cla/google`, `lint` | 0 | **30/30** | `husky` in package.json |
| kubernetes/kubernetes | **`EasyCLA`**, `pull-kubernetes-linter-hints` (Prow; 0 Actions workflows) | 0 | 0 | none |
| envoyproxy/envoy | **`DCO`** | **27/30** | 1 | `CODEOWNERS` (root) |
| oppia/oppia | **`Verify CLA`**, `Custom ESLint checks` | 0 | 0 | `.github/CODEOWNERS`, `all_lint_checks.yml`, `lint-staged` |
| microsoft/vscode | none CLA-like in the 8 sampled PRs (50 distinct checks) | 0 | 0 | `.github/CODEOWNERS`, `husky` |
| apache/airflow | none CLA-like (115 distinct checks) | 1 | 0 | `.github/CODEOWNERS` |

How the tools surface themselves (primary sources): EasyCLA appears in the PR "Checks" as `EasyCLA` (LF docs: https://docs.linuxfoundation.org/v2/easycla/getting-started/easycla-troubleshooting); `contributor-assistant/github-action` runs as a workflow usually named `cla.yml` on `pull_request_target` + `issue_comment` with a signatures JSON (example workflow: https://glama.ai/mcp/servers/@deleonio/public-ui-kolibri/blob/78d0232959bff667ab3b01296bd6fb7babcf4cb7/.github/workflows/cla.yml); DCO workflows check every commit for `Signed-off-by` and tell you to `git commit -s`. ecosyste.ms detects `DCO`/`CLA` *files* with the regexes in §2.3. commitlint config filenames (https://commitlint.js.org/reference/configuration.html): `.commitlintrc{,.json,.yaml,.yml,.js,.cjs,.mjs,.ts,.cts,.mts}`, `commitlint.config.{js,cjs,mjs,ts,cts,mts}`, or a `commitlint` key in `package.json`.

**Detection recipe (ordered by reliability):**
1. `statusCheckRollup.contexts` names on the head commits of the last ~8 merged PRs: regex `(?i)\b(cla|easycla|dco|license/cla|verify cla|commitlint|semantic|conventional|pr title)\b`.
2. Commit-message ratios over `history(first:30)`: `Signed-off-by:` share ≥ 0.5 → "DCO sign-off expected (`git commit -s`)"; Conventional-Commits headline share ≥ 0.7 → "commit/PR titles follow `type(scope): subject`".
3. Tree lookups (`object(expression:"HEAD:<path>")`): `.github/dco.yml`, `.clabot`, commitlint configs, `.cz.toml`/`.cz.json`, `release-please-config.json`, `.releaserc*`, `cliff.toml`, `CODEOWNERS` in `/`, `.github/`, `docs/`; `.github/workflows/*` names matching `cla|dco|semantic|commitlint`.
4. CONTRIBUTING / PR-template text: `Developer Certificate of Origin|Signed-off-by|git commit -s|Contributor License Agreement|\bCLA\b|conventional commits|commitlint|squash|rebase|one commit per|PR title`; count `- [ ]` checklist items in `pullRequestTemplates{body}`.
5. ecosyste.ms `metadata.files.{dco,cla,codeowners,governance,maintainers}` as a free cross-check.

Present these as **requirements, not score deductions**, a CLA is a hurdle, not a sign of unfriendliness (angular and kubernetes both merge outsiders routinely).

---

## 5. Critique of git-into-gsoc's current health signals

| Signal (weight) | Problem | Evidence | Recommendation |
|---|---|---|---|
| `newcomers_merged` (shown) | ≈0 by construction: merged authors become `CONTRIBUTOR` at query time | sympy sample: merged = 23 CONTRIBUTOR + 8 MEMBER, 0 FIRST_TIME_CONTRIBUTOR/NONE; enum definitions are stative | **Remove.** Replace with "distinct outside authors merged in last 50 PRs" and "one-commit committers in the past year" (commits.ecosyste.ms) |
| `outsider_merge_rate` (12) | `NONE` ≡ "nothing ever merged", so the denominator is inflated by rejected drive-bys and the rate is not comparable across repos; `CONTRIBUTOR` includes long-time non-member regulars | sympy: outsiders-by-association 41 PRs/56% vs outsiders-by-`assignableUsers` 39/54% (close); oppia: 40/20% vs 35/**9%** (association flatters oppia because 9 merged regulars are `CONTRIBUTOR`) | Define insiders = `assignableUsers ∪ {OWNER,MEMBER,COLLABORATOR}`; keep weight high (≈18) and show both n and rate; require n≥10 |
| `merge_rate` (12) | Correlates with outsider rate; mostly measures how many PRs are self-merged | Zhang: `same_user` is the dominant factor, insiders' merge rates are ~90% everywhere (sympy 91%, oppia 87%) | Drop as a scored signal; show "insider vs outsider" merge rates side by side instead |
| `median_pr_hours` (10) | Survivorship (merged-only), open→merge not open→first response, mixes insiders | CHAOSS: use first response + median time-to-close together; Hasan: first *human* response is the predictor | Replace with median **time to first human response** (skip bots and author) over outsider PRs + share answered within 2 business days |
| Sample = 60 most recently *updated* closed PRs | "updated" surfaces old PRs touched by bots/labels; not the recent flow | `list_pulls(sort=updated)` | Use `pullRequests(last:50, orderBy CREATED_AT)` |
| `has_ci` = workflow count > 0 (8) | Any workflow (release/publish only) counts; Prow-based repos (kubernetes: 0 workflows) score 0 | Scorecard CI-Tests uses check runs on recent commits | Count distinct `statusCheckRollup` contexts on recent merged PR heads; fall back to workflow tree |
| Push recency (20) | Over-weighted; pushes by bots count; no maintainer-activity dimension | Scorecard Maintained: commits + member issue activity in 90 d | Adopt Scorecard's Maintained (12 weekly-activity units) at ~12 pts |
| Stars band (+4 for 50-30k) | Popularity *reduces* acceptance odds | Tsay OR 0.648; Zhang stars OR 0.86 | Weight 0; keep the ">50k stars: expect competition" warning |
| `open_beginner_issues` (10) | Counts open-labelled issues regardless of age/assignment/claims; label histograms show e.g. sympy's real pipeline is "Easy to Fix": 100 vs "good first issue": 7 | Tan 2020: ~half of GFIs aren't solved by newcomers | Score fresh + unassigned + unclaimed GFIs (reuse `availability`), and add "share of closed GFIs resolved by outsiders" |
| CoC/templates/CONTRIBUTING (20 total) | Fine, but a CONTRIBUTING that states expected response time / review SLA is a stronger indicator than mere presence | CHAOSS responsiveness guide | +2 for an explicit response-time statement; parse "we aim to respond within N days" |
| License (4) | GitHub's `NOASSERTION`/"other" (sympy) is treated as a license; a non-OSI license should warn | Scorecard License: +1 only for FSF/OSI | Use `licenseInfo{spdxId, isOsiApproved?}`, note GraphQL `License` has `spdxId`, `pseudoLicense`; flag `NOASSERTION` |
| Missing entirely | maintainer capacity (active maintainers, open PRs per maintainer, bus factor), CLA/DCO/conventions, PR-size norms, first-response time | Zhang `prior_review_num` [13.5%], `open_pr_num`; CHAOSS CAF; §4 | Add (see §6) |
| Call budget | ~7 REST calls + per-repo probing in `repos ORG` | measured GraphQL cost 3-4 | GraphQL path + ecosyste.ms org page |

---

## 6. Proposed health model v2

Signals, weights (sum 100), and source. Every scored item must print its raw count so the grade stays explainable (Scorecard-style `reason`).

| # | Signal | Weight | Source (primary / fallback) | Rule |
|---|---|---|---|---|
| 1 | Maintained (Scorecard rule) | 12 | GraphQL `history(since: now-90d){totalCount}` + issues with insider activity in 90 d / ecosyste.ms `past_year_total_commits` | `min(1, (commits90 + insiderIssueActivity90)/12)` × 12; archived → grade F |
| 2 | Outsider merge rate | 18 | GraphQL 50 closed PRs; insiders = `assignableUsers ∪ {OWNER,MEMBER,COLLABORATOR}` | n≥10: ≥50% → 18, ≥30% → 12, ≥15% → 6, else warn; n<10 → "insufficient evidence" (no points, no penalty) |
| 3 | Time to first human response (outsider PRs) | 15 | GraphQL `timelineItems(first:6, [ISSUE_COMMENT, PULL_REQUEST_REVIEW, PULL_REQUEST_REVIEW_THREAD])`, skip `__typename == Bot`, `[bot]`, known bots, and the author / OSS Insight `/q/analyze-issue-open-to-first-responded` (hours) as a cross-check | median ≤ 24 h → 15; ≤ 2 business days → 11; ≤ 7 d → 5; else warn. Also print "% answered within 2 business days" (CHAOSS benchmark) |
| 4 | Newcomer throughput | 10 | distinct outside authors merged in the 50-PR sample; commits.ecosyste.ms `past_year_committers` with count ≤ 2 | ≥8 distinct outside authors merged → 10; ≥4 → 6; ≥1 → 3 |
| 5 | Maintainer capacity | 10 | `assignableUsers.totalCount`; ecosyste.ms owner `active_maintainers`; `past_year_dds`; open PR count | ≥3 active insiders and open PRs per active insider ≤ 15 → 10; CAF (50% rule) = 1 → warn "single-maintainer project" |
| 6 | Beginner-issue pipeline | 12 | GraphQL `issues(labels:[GFI label], states:[OPEN])` with `assignees.totalCount`, `comments`, `updatedAt`; closed GFIs' resolver association | fresh (updated ≤ 180 d) unassigned GFIs: ≥5 → 8, ≥1 → 5; +4 if ≥40% of the last 30 closed GFIs were closed via an outsider PR |
| 7 | Onboarding docs | 14 | GraphQL `contributingGuidelines`, `codeOfConduct`, `issueTemplates`, `pullRequestTemplates` + CONTRIBUTING text | CONTRIBUTING 6, templates 3, CoC 2, explicit response-time/review-expectations statement 2, dev-container or one-command setup 1 |
| 8 | CI runs on PRs | 6 | distinct `statusCheckRollup` contexts on last 8 merged PR heads / `.github/workflows` tree | ≥1 non-CLA check → 6 |
| 9 | License | 3 | `licenseInfo{spdxId}` | OSI/FSF SPDX → 3; `NOASSERTION`/other → 1 + warning; none → 0 + warning |
| none | Requirements (CLA/DCO/conventions/CODEOWNERS/PR checklist) | 0 | §4 recipe | Printed as a "before you open a PR" card, never scored |
| none | Popularity | 0 | stars | Warnings only (>50k: competition; <20: confirm maintained) |
| none | PR-size norm | 0 | median additions+deletions of merged outsider PRs | Printed: "merged outsider PRs here are typically ≤ N lines" |

Grade thresholds can stay (A≥85…). Validate the re-weighting offline against GSoC orgs: for each org repo, compute v1 and v2 grades and compare with `past_year_merged_pull_requests_count / past_year_pull_request_authors_count` from issues.ecosyste.ms as a crude ground truth; ClickHouse/BigQuery can give true newcomer-merge labels if someone wants to fit weights properly.

---

## 7. The GraphQL path: concrete spec

**Query A, health (cost 3-4, one round trip)**: `repository(owner,name){ nameWithOwner isArchived pushedAt stargazerCount licenseInfo{spdxId} codeOfConduct{name} contributingGuidelines{resourcePath} issueTemplates{name} pullRequestTemplates{filename body} defaultBranchRef{target{... on Commit{history(first:30){nodes{messageHeadline message author{user{login}}}} }}} object(expression:"HEAD:.github/workflows"){... on Tree{entries{name}}} assignableUsers(first:100){totalCount nodes{login}} pullRequests(last:50,states:[MERGED,CLOSED]){totalCount nodes{number createdAt closedAt mergedAt authorAssociation author{login __typename} additions deletions changedFiles comments{totalCount} timelineItems(first:6,itemTypes:[ISSUE_COMMENT,PULL_REQUEST_REVIEW,PULL_REQUEST_REVIEW_THREAD]){nodes{__typename ... on IssueComment{createdAt author{login __typename}} ... on PullRequestReview{createdAt author{login __typename}} ... on PullRequestReviewThread{comments(first:1){nodes{createdAt author{login __typename}}}}}}}} issues(last:30,filterBy:{labels:["good first issue"]}){totalCount nodes{number state createdAt updatedAt closedAt authorAssociation assignees{totalCount} comments(first:1){totalCount nodes{createdAt author{login __typename} authorAssociation}} timelineItems(first:1,itemTypes:[CROSS_REFERENCED_EVENT]){nodes{__typename}}}} rateLimit{cost remaining resetAt} }`. Skip `collaborators` (FORBIDDEN). Pass the beginner label discovered from `labels(first:100)` in the same query or from issues.ecosyste.ms `issue_labels_count`.

**Query B, requirements (cost 1)**: tree lookups for `.github/dco.yml`, `.clabot`, commitlint configs, `.cz.toml`, `release-please-config.json`, `CODEOWNERS`×3 locations, `package.json` text (`commitlint|husky|semantic-release|commitizen`), plus `pullRequests(last:8,states:[MERGED]){nodes{commits(last:1){nodes{commit{statusCheckRollup{contexts(first:50){nodes{__typename ... on CheckRun{name} ... on StatusContext{context}}}}}}}}}`.

**Query C, user side (for `recommend`/`issue`)**: `search(type:ISSUE, query:"repo:o/r commenter:USER", first:1){issueCount}` and `… author:USER is:pr`, aliased per candidate repo → prior-interaction count (Tsay +35.6%/unit).

Operational notes: (1) a 6-repo aliased query with 60 contexts × 25 PRs each returned HTTP 504, stay at one repo per query and ≤ ~5k requested nodes; (2) GraphQL needs a token (no anonymous tier), so keep the REST path as the unauthenticated fallback and ecosyste.ms as the zero-token enrichment; (3) partial results arrive with `errors[]`, parse `data` even when `errors` is present; (4) first-response detection must look past the first comment: on sympy `sympy-bot` was the first commenter on 50/50 PRs; with 6 timeline items a human response was found for 40/50 (median 7.3 h, p75 29.7 h); on oppia only 19/50 (median 2.0 h), report "no human response within the first 6 events" as its own count rather than treating it as missing data.

---

## 8. Feature proposals for git-into-gsoc

| # | Proposal | Effort | Motivating evidence |
|---|---|---|---|
| P1 | **Fix the insider/outsider definition** (`assignableUsers ∪ {OWNER,MEMBER,COLLABORATOR}`), delete `newcomers_merged`, add "distinct outside authors merged" and require n≥10 before scoring | S | §5 rows 1-2; sympy/oppia probes; GraphQL enum definitions |
| P2 | **GraphQL health path** (Query A) with REST fallback; store `rateLimit.cost` in `--output json` | M | measured cost 3-4 vs ~7 REST calls; docs on points/nodes |
| P3 | **Time to first human response** (median + "% within 2 business days", outsider PRs only, bots/author excluded) replacing `median_pr_hours` | S (on top of P2) | Hasan 2023 (64.7% of lifetime variance; +15% newcomer retention), CHAOSS TTFR + responsiveness guide |
| P4 | **"Before you open a PR" card** in `repo`, `issue`, and the MCP tool: CLA/DCO/sign-off, commit/PR-title convention, PR checklist length, CODEOWNERS (who will review), required-looking checks | M | §4 probes (`cla/google`, `EasyCLA`, `DCO`, `Verify CLA`; envoy 27/30 sign-offs; angular 30/30 conventional) |
| P5 | **Maintainer capacity + bus factor** block: active insiders, open PRs per active insider, CAF from commits.ecosyste.ms `past_year_committers`, `past_year_dds` | S | Zhang `prior_review_num` [13.5%], `open_pr_num`; CHAOSS Contributor Absence Factor |
| P6 | **ecosyste.ms enrichment layer** (`repos`, `issues`, `commits`; `lookup?url=`; `POST /jobs` when 404) used by `repos ORG` so ranking an org needs ~1 ecosyste.ms page per 100 repos and zero GitHub calls; cache 24 h per their headers | M | §2.3 (15k/h polite tier, 24 h cache, `metadata.files`, `commit_stats`, label histograms, `past_year_*`) |
| P7 | **Re-weighted health model v2** (§6) with Scorecard-style `reason` strings carrying raw counts; stars → warnings only; CI via check contexts | M | §3 table; Tsay OR 0.648 for stars; Scorecard Maintained formula |
| P8 | **GFI-label quality**: fresh/unassigned/unclaimed open GFIs (reuse `availability`), share of recently closed GFIs resolved by outsiders, median GFI time-to-close; also surface the org's *real* beginner label from `issue_labels_count` (sympy: "Easy to Fix" 100 vs "good first issue" 7) | M | Tan 2020 ("almost half of GFIs not solved by newcomers"); RecGFI |
| P9 | **PR-size norm + behavioural guidance** printed with the grade: "merged outsider PRs here are typically ≤ N lines; comment on the issue first; keep one focused commit; reply within a day" | S | Tsay (size OR 0.738, prior interaction +35.6%, comments −54.6%), Li et al. abandonment reasons |
| P10 | **Scorecard context line** (`api.scorecard.dev`, 404-tolerant; deps.dev as a second mirror): show Maintained, Code-Review, License only; link the rest | S | §2.1; CDLA-Permissive-2.0 data; weekly scans lack CI-Tests/Contributors |
| P11 | **`recommend` uses the user's prior interaction**: aliased GraphQL `search` for `commenter:USER`/`author:USER` per shortlisted repo; rank repos where the user already has a footprint higher; account age as a soft factor | M | Tsay prior interaction; arXiv 2104.02933 `gh_account_duration` top-3 feature; Legay 54→80% with experience |
| P12 | **Digest of new issues/PR activity in tracked repos** via GraphQL `issues(orderBy:{field:UPDATED_AT}, filterBy:{since})` (not timeline.ecosyste.ms, which 500'd) | M | §2.3 timeline probe; brief's listed weakness |
| P13 | Offline **weight calibration script** (BigQuery `githubarchive` or ClickHouse playground, which is ~3.5 months stale) over GSoC-org repos: label = outsider PR merged within 30 d; fit/validate v2 weights | L | §2.6; Zhang/Tsay methodology |

Top 5 if only five can ship: P1, P2+P3 (together), P4, P6, P7.

---

## 9. Licensing and attribution notes

- OpenSSF Scorecard: code Apache-2.0; result data CDLA-Permissive-2.0 (attribution-friendly). Copying the *Maintained* rule is an idea, not code.
- ecosyste.ms services: open source under the ecosyste-ms org (AGPL-3.0 per org convention, **unverified per repo**); consuming the public API has no licensing implication for a client; be a good citizen (identify via User-Agent, respect `cache-control`).
- OSS Insight: Apache-2.0; the `/q/` endpoints are undocumented, don't make them load-bearing.
- CHAOSS metric definitions: CC-BY-4.0 (CHAOSS metrics are published under CC BY; **unverified** on each page), cite when reusing wording such as "Contributor Absence Factor".
- 8Knot MIT, Truck-Factor MIT, git-fame OSI-approved (name **unverified**), star-history MIT. No code is being copied from any of them.
- Research papers are cited for their findings only (arXiv/ACM links above).

---

## Appendix A: Probe numbers (2026-10-21)

- `gql_sympy.json` (Query A prototype): `rateLimit.cost 3`, `remaining 4866/5000`; `assignableUsers.totalCount 31`; `mentionableUsers 1412`; `pullRequests.totalCount 14643`; GFI issues total 58; `collaborators` → FORBIDDEN; `issueTemplates []`, `pullRequestTemplates [PULL_REQUEST_TEMPLATE.md]`, `licenseInfo.spdxId NOASSERTION`, `codeOfConduct Contributor Covenant`, workflows: checkconflict, emscripten, nightly-wheels, release, runtests, zizmor.
- `gql4_sympy.json` / `gql4_oppia.json`: cost 4 each. sympy: first human response found 40/50, median 7.3 h, p75 29.7 h; outsiders(by assignable) 39 PRs, 54% merged; insiders 11, 91%. oppia: 19/50 found, median 2.0 h, p75 11.0 h; outsiders 35, **9%** merged; insiders 15, 87%; association distribution NONE 31 / CONTRIBUTOR 9 / MEMBER 7 / COLLABORATOR 3.
- ecosyste.ms sympy: repos `last_synced_at 2026-10-14`, `commit_stats {47932 commits, 1336 committers, dds 0.904}`; issues `last_synced_at 2026-10-20`, past-year 517 PRs / 159 merged / 208 PR authors / 214 issues / 77 issue authors; commits `past_year_total_committers 147`, `past_year_dds 0.928`; owner `maintainers 68`, `active_maintainers 7` (all 7 ∈ assignableUsers).
- Scorecard API sympy: date 2026-10-12, v5.6.0, score 5.6, 14 checks (Maintained 10: "30 commit(s) and 13 issue activity found in the last 90 days"; Code-Review 8: "17/21 approved changesets"; License 9).
- OSS Insight sympy (`repoId 640534`): issue first-response p50 9.53 h (Oct 2026), PR open→closed p50 6.1 h; API v1 headers `x-ratelimit-limit 600`, `x-ratelimit-limit-minute 100`.
- ClickHouse playground: `max(created_at)` for `sympy/sympy` = 2026-07-02.
