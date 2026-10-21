<!-- Research working notes. Written 2026-10-20/21 during the ecosystem research pass; kept as the evidence base for ../research.md. Claims marked unverified were not confirmed against a primary source. Plain-language rules apply loosely here; these are notes, not a guide. -->

> Working notes from the research pass of October 2026. GSoC tools, the official site's API, ideas pages, proposal archives, and what organizations score. The checked conclusions are in [the research summary](../research.md); these notes keep the evidence, numbers, and URLs behind them. Items marked unverified were not confirmed against a primary source.

# Stream A: Direct competitors and GSoC / mentorship-program tooling

> Verification status. Re-checked first hand on 2026-10-21: the official site's JSON (1,191 completed 2025 projects with mentors), every one of the 183 ideas pages through the shipped parser (numbers in the summary), the community archive's commit history, the proposal archives' layouts, and Google's April 2026 announcement (1,142 contributors from 23,371 proposals). Not re-opened: the internals of the hobby explorer sites beyond their public pages. Links: 38 of 39 resolved with HTTP 200 on 2026-10-21; the rest are URL templates with placeholders, endpoints that need a token, or sites that block scripts. Everything else here is the research stream's working record as written.

Research date: 2026-10-20. All HTTP probes, clones and counts below were run on this date; "verified" means I fetched the primary source myself. Raw downloads live in `(session working files, not included)` (official API JSON, `organizations.json`, 183 fetched ideas pages, 43 proposal PDFs converted to text, shallow clones).

## TL;DR

1. **The official site exposes a much richer public JSON API than git-into-gsoc uses.** Verified endpoints: `/api/program/` (all programs 2022-2026 with milestones + `stats`), `/api/archive/programs/` (2016-2025 summary counts), `/api/archive/programs/{year}/organizations/` (list), `/api/archive/programs/{year}/organizations/{slug}/` (org + its `projects[]`), `/api/archive/programs/{year}/projects/` (every passed project with `mentor_names`, `project_code_url`, `tech_tags`, `topic_tags`, `abstract_html`, `id`, `organization_slug`) and `/api/archive/projects/{id}/`. These are the exact calls the Angular SPA makes (`ARCHIVE_PATH="/archive/"`, `PROGRAMS_PATH="/archive/programs/"`, found in `main.*.js`). api.gsocorganizations.dev is a derivative of exactly this data (its 2025 project total, 1,191, equals the official archive count) but drops mentor names, project ids, tags-per-project and slugs. git-into-gsoc can go to the primary source and keep the archive as fallback.
2. **api.gsocorganizations.dev is a hand-updated snapshot, not a pipeline.** No scraper exists in the repo; `api/data/{year}.json` are committed manually (orgs 1-2 days after Google's announcement, projects 2-14 days after, a "program concluded" fix the following January). Merging across years is a disjoint-set union on case-insensitive name or normalized website host+path; topics/technologies keep only the last 3 participation years; tag normalisation is a hand-maintained (now AI-curated via `actions/ai-inference`) mapping. Schema documented precisely in §1.2. Served with `ETag` and `cache-control: public,max-age=0,must-revalidate` (ETag revalidation works; the file is 14.7 MB).
3. **Ideas pages are parseable in tiers, not universally.** Of the 183 GSoC-2026 `ideas_link`s, 168 fetched OK (15 failed: renamed wiki pages, bot walls, TLS). 108 are HTML, 60 markdown/text. Label presence: size/hours 118, mentor 129, skills 113, difficulty 97, expected outcome 74; all four of (difficulty, size, mentor, skills) on 76 pages. A naive heading-split + label-regex parser produced ≥3 well-formed idea blocks on 64/172 pages (735 blocks) and nothing usable on 96, the failures are umbrella index pages (PSF, NumFOCUS, ASF, INCF), tables (Jenkins, R), issue-tracker lists (OHC, Drupal, Eclipse) and label-less prose. Label vocabulary is small and stable (§2.3).
4. **Accepted-proposal archives converge on one structure.** Across 43 accepted 2025 PDFs: Timeline (19), About me (17), Deliverables (13), Abstract (10), References (10), Synopsis (9), Benefits to the community (8), Goals (8); median 3,473 words; 31/43 have a week-by-week timeline; only 7/43 embed PR links (many are shared "without contacts"); 12/43 mention AI/LLM. Org templates (Blender, LLVM, openSUSE, RTEMS-2026, CNCF) add: link to prior PRs, four "why you/why us" questions, maintenance plan, increments that can be upstreamed if time runs out, AI-use disclosure.
5. **What orgs score (official + org admins, 2025-2026):** community contact before applying ("Don't even think about selecting a GSoC contributor with whom you've had no contact"), application-phase contributions over prior ones (Wikimedia), template adherence, non-generic technical content beyond the idea text (OSM pre-filter), realistic scope/time commitments, responsiveness. AI: LLVM/CRIU/JBoss reject LLM-written proposals or code; FOSSology, GRAME, DeepChem, GA4GH, KubeVirt, Metasploit, erofs allow bounded use with disclosure; Google's spam page tells orgs "Super pretty proposals are more likely to be AI-generated". 2026 numbers: 15,245 applicants, 23,371 proposals, 1,141 accepted (~4.9% per proposal); OSM got 136 proposals vs 34 the year before and attributed the rise to AI spam.
6. **No GSoC-specific CLI, bot, or extension of substance exists.** Everything is a web explorer (gsocorganizations.dev 749★, FindMyGSoC 178★/574 forks, gsocorganizationsguide.com, openorganizations.site, gsocanalyzer), a proposal archive repo, or a static list. The closest things to git-into-gsoc's issue/repo features are generic (EddieHub finder, goodfirstissue.dev, up-for-grabs, CodeTriage's daily-issue email, OpenIssueMonitor's Telegram label watcher). Adjacent programs offer better structure to borrow from: Outreachy's `ProjectSkill` (experience level 1-5 × required/preferred/optional) and `Contribution` ledger; CNCF/LFX's issue-form proposals with prerequisites and coding challenges; OWASP Nest's AI issue "hint"/"summary", `IssueUserInterest`, and a CI check that closes PRs that don't reference an issue the author is assigned to.

Top proposals (details in the final section): (P1) switch org/project intelligence to the official archive API with mentor names and per-project tags, S/M; (P2) tiered ideas-page parser producing `ProjectIdea{title,size,difficulty,skills,mentors,links}` with a confidence flag, M; (P3) contribution ledger + "proposal evidence pack" modelled on Outreachy's Contribution model and Blender's PR-link section, M; (P4) org AI/LLM-policy extractor and proposal pre-flight lint against the org's own rules and Google's spam signals, S+M; (P5) daily/weekly digest of new beginner issues in tracked repos (CodeTriage pattern), S.

---

## 0. Method

- Primary sources fetched: official JSON endpoints (probed 30+ URL shapes), the SPA bundle (`main.de5b78a7d3173b60.js`, 1.77 MB decompressed) for route constants, `api.gsocorganizations.dev/organizations.json` + year files, shallow clones of `nishantwrp/gsoc-organizations`, `SammanSarkar/GSoC_archive_2025`, `satwiksps/GSoC_archive_2026`, `apsinghdev/opensox`, `cncf/mentoring`, `EddieHubCommunity/good-first-issue-finder`; `gh api` reads of READMEs, trees, issues and workflow files for ~30 more repos; Google's gsocguides and developers.google.com pages; org admin posts (OSM, Rust, LLVM, AiiDA, CRIU, INCF, Jenkins, Wikimedia).
- Scripts (in the research scratchpad): `schema.py` (archive schema census), `fetch_ideas.py` (14 deep samples), `fetch_all_ideas.py` (all 183 ideas links), `parse_ideas.py` (heuristic parser feasibility), `proposals.py` (pdftotext + heading census).
- Items I could not verify are marked **unverified**.

---

## 1. Data sources

### 1.1 summerofcode.withgoogle.com public JSON API (verified 2026-10-20)

Base: `https://summerofcode.withgoogle.com/api` (`apiUrl:"/api"` in the bundle's environment config). Unauthenticated, no CORS issue for server-side use, no documented rate limit (**unverified**). Trailing slash required.

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/` | 200 `{"status":"OK"}` | health |
| `GET /api/program/` | 200, list | 5 programs: 2022-2026, each with full `milestones[]`, `phase`, `stats` |
| `GET /api/program/{year}/` | 200 for 2022-2026; 404 `{"type":"object_not_found"}` otherwise | `name, slug, is_active, phase, terms_contributor/member/organization/rules, date_created, date_updated, milestones[{name,datetime,label}], stats{orgs_accepted, allocated_projects}, project_sizes["small","medium","large"]`. 2026: `phase:"project_work"`, `stats:{orgs_accepted:184, allocated_projects:1156}`. Milestone names: `prog_announce, org_application_start, org_application_deadline, org_notification, org_announce_public, contributor_proposals_open, proposal_deadline, proposal_ranking_deadline, project_announce_oa, project_announce_public, project_work_start, program_end`, then per-size `midterm_evaluation_start/deadline, final_submission_start/deadline, final_evaluation_start/deadline, project_completion` labelled "(small/medium/large project)". |
| `GET /api/program/current/` | 404 | not a thing |
| `GET /api/program/{year}/organizations/` | 200 (2025: 185; 2026: 183, note `stats.orgs_accepted` says 184) | per org: `name, slug, logo_url, website_url, tagline, license, categories[], contributor_guidance_url (174/183 non-null), description, tech_tags[], topic_tags[], contact_links[{name,value}], source_code, ideas_link, direct_comm_methods[{name,value}], social_comm_methods[]`. `contact_links.name` values seen: `email, chat, mailingList, blog, twitter, ...`. |
| `GET /api/program/{year}/organizations/{slug}/` | 404 | no per-org detail for active programs |
| `GET /api/program/{year}/projects/` | 2026: 400 `"Program is not open to receive applications"`; 2025: 403 `"Request not allowed for completed/archived programs"` | the messages hint this lists something during the application window (**unverified**) |
| `GET /api/archive/programs/` | 200 | 2016-2025: `slug, name, date_created, year, project_count, contributor_count, organization_count, mentor_count, date_archived`. E.g. 2025: 185 orgs, 1,261 projects, 2,775 mentors, `contributor_count` 15,218 (this matches the *applicant* number Google published for 2026-style stats, so treat it as applicants, **unverified**). |
| `GET /api/archive/programs/{year}/` | 200 | same object for one year |
| `GET /api/archive/programs/{year}/organizations/` | 200 for 2016-2025 (2016: 374 KB) | `slug, name, logo_url, website_url, tagline, contact_links[], date_created, tech_tags[], topic_tags[], categories[], program_slug, logo_bg_color, description_html, ideas_list_url` |
| `GET /api/archive/programs/{year}/organizations/{slug}/` | 200 | same + `projects[]` (OWASP 2025: 12) |
| `GET /api/archive/programs/{year}/projects/` | 200 (2025: 1,191 items, 1.96 MB) | `title, project_code_url, date_created, tech_tags[], topic_tags[], status, program_slug, contributor_display_name, mentor_names[], abstract_short, abstract_html, date_archived, id (8-char, e.g. "ENS6gMck"), organization_name, organization_slug`. Query params (`?organization=`, `?page=`) are ignored, full list always returned. |
| `GET /api/archive/projects/{id}/` | 200 | single project (the SPA's `getProjectDetails`) |
| `GET /api/archive/program/...`, `/api/archive/{year}/...`, `/api/programs/` | 404 | wrong shapes |

Observations from the 2025 archive projects list:
- **All 1,191 entries have `status:"passed"`**; the archive program summary says `project_count:1261` and the program `stats.allocated_projects` says 1,293. So the public archive only exposes completed/passed projects, the pass rate cannot be derived from it alone, but "orgs whose contributors finish" can.
- `mentor_names` per project: 1 mentor 342, 2 mentors 516, 3: 220, 4: 67, 5: 27, 6: 14, 7: 5. This is the only public source of **who mentors at an org**, across years.
- `project_code_url` hosts: github.com 429, gist.github.com 268, medium.com 92, docs.google.com 45, gitlab.com 13; 60 point straight at a PR. Useful to find which *repos* an org's past projects touched.
- `tech_tags` are free text per project, un-normalised (e.g. `"C, Kernel"` as one tag).
- Orgs with most 2025 projects: Google DeepMind 38, NumFOCUS 31, ML4SCI 31, CERN-HSF 25, INCF 25, ASF 25, Linux Foundation 21, R 21, i.e. umbrella orgs dominate; per-sub-project resolution needs the ideas page or `project_code_url`.
- 2026 (active) organisations and `api.gsocorganizations.dev` 2026 names intersect on 180/183; the 3 differences are name filters ("Ceph" vs "Ceph Foundation", "GNU Mailman" vs "GNU Mailman Project", "Apache Software Foundation" vs "The Apache Software Foundation").

What git-into-gsoc uses today (`src/git_into_gsoc/gsoc/official.py`): only `program/{year}/` and `program/{year}/organizations/`. It does consume `ideas_link`, `contributor_guidance_url`, `source_code`, `tech_tags`, `topic_tags`, `direct_comm_methods` (`gsoc/client.py`). It does **not** use `/api/program/` (all programs at once), `stats`, `project_sizes`, or any `/api/archive/...` endpoint, the multi-year history comes from gsocorganizations.dev instead.

### 1.2 api.gsocorganizations.dev: nishantwrp/gsoc-organizations

- URL: https://github.com/nishantwrp/gsoc-organizations ; site https://www.gsocorganizations.dev ; API docs https://api.gsocorganizations.dev/ (Redoc from `api/openapi.yml`). License **GPL-3.0**. 749★, JavaScript (Gatsby + Redux), last push 2026-05-14 ("feat: projects announced for 2026"). Deployed on Netlify (two sites: main + api).
- **Endpoints**: `/organizations.json` (14,663,695 bytes, 519 orgs, 2016-2026) and `/{year}.json` (2025: 1,903,423 B; 2026: 1,867,132 B). Headers: `cache-control: public,max-age=0,must-revalidate`, strong `ETag`, conditional GETs work.
- **Schema (census of the live file, 519 orgs, 2,131 org-years, 12,095 projects):**
  - org: `name, url, image_url, image_background_color, description, category, topics[], technologies[], years{}, irc_channel, contact_email, mailing_list, ideas_url, guide_url` (always present) + `twitter_url` (385 orgs), `blog_url` (347). Empty-string counts: `ideas_url` 295/519, `guide_url` 308/519, `irc_channel` 99, `contact_email` 99, `mailing_list` 139. `category` is a single string from 13 values (Science and medicine 120, Programming languages 90, End user applications 73, Data 48, Other 37, Operating systems 36, Web 29, Media 28, Infrastructure and cloud 21, Security 19, Social and communication 10, Development tools 6, Artificial Intelligence 2).
  - `years[YYYY]`: `projects_url, num_projects, projects[]`. Years present: 2016:178, 2017:201, 2018:212, 2019:206, 2020:199, 2021:202, 2022:202, 2023:168, 2024:195, 2025:185, 2026:183.
  - project: `title, short_description, description (HTML), student_name, code_url (10,923/12,095 non-null), project_url`, plus `proposal_id` on 3,239 recent projects. No mentor names, no tags, no status, no stable id for older years.
  - Per-year raw file (`api/data/{year}.json`): `{year, archive_url, organizations[{name,image_url,image_background_color,description,url,category,projects_url,ideas_url,guide_url,topics,technologies,irc_channel,contact_email,mailing_list,twitter_url,blog_url,facebook_url,num_projects,projects[]}]}`, i.e. a renamed projection of the official archive org + projects.
  - Vocabulary after filtering: 924 distinct topics, 566 technologies (top: python 278, javascript 223, c++ 160, c 132, java 102, "frontend" 75, "machine learning" 74, database 74, go 55, react 47, rust 44).
- **Pipeline (from source):** there is **no scraper in the repo**. `Makefile` target `api` runs `scripts/generate-data.js` → `api/compile-data.js`:
  1. For each year file, apply `nameFilters` (hard-coded alias table), `categoryFilters`, and recursive `topicFilters`/`technologyFilters` (merge maps with a 15-iteration cycle guard; comment says "AI curated filters can sometimes have un-ordered mergings").
  2. Union orgs across years with a `DisjointSet`; `isMergePossible` = case-insensitive name equality OR same host (with `www.` stripped) **and** same URL path.
  3. `getCombinedOrgJson`: sort by year; basic properties take the latest non-empty value (`orgJson[prop] || combinedJson[prop]`); topics/technologies are only accumulated from the **last 3 participation years** (`isFreshData`, commit "discard more than 3 year old topics, technologies", 2026-03-01).
  - Filter curation is now partly automated: `.github/workflows/propose-merge-filters.yml` runs `actions/ai-inference@v1` with GitHub MCP following `.agent/skills/propose-merge-filters/SKILL.md`, which merges low-count tags into popular ones using view analytics from a private `gsoc-organizations-store` repo.
- **Update cadence (commit log, path `api/data`):** "add 2026 orgs" 2026-02-20 (Google announced 2026-02-19); "projects announced for 2026" 2026-05-14 (announced 2026-04-30); 2025: orgs 2025-03-01 (announced 2025-02-27), projects 2025-05-10, fix 2025-06-16, "update info for gsoc 2025 as the program has concluded" 2026-01-25; 2024: orgs 02-21, projects 07-07; 2023: orgs 02-25, projects 11-11. So: **days-to-weeks lag, single maintainer, and the "concluded" pass (which drops failed projects to match the archive) only lands the following January.**
- **Site features** (`src/components`): search, sidebar filters (year, category, topics, technologies), org cards, org info with `imp_links.json` (hand-curated "important links" per org, e.g. Oppia contributing wiki, Joplin PR guidelines), a per-org projects graph (projects per year) and project cards. No sort by activity, no issues, no ideas parsing.
- **Community feedback (issues, 213 total):** sort by project count (#173), sort by "how active" (#150, maintainer pushed back: issue/PR counts vary with timing), exclude filters (#149), tech stack per project (#155), AI skill matching (#160), **a contributor built a RAG over 2,426 scraped ideas from all 185 2025 orgs** (#174 → `sreehariX/gsoc-projectRecommendation`, servers now down), automate scraping with Actions (#130, unanswered), duplicate tags by case (#209), "Design required to accept Past GSoC Proposals" (#125). These are the unmet needs of its user base.
- **Assessment:** reliable enough as a cache of history, but derivative, lagging, lossy (no mentors/tags/ids), GPL-3 code (irrelevant since we only consume JSON), and the maintainer explicitly declines "activity" metrics. git-into-gsoc should treat the official archive as primary and this as fallback/cross-check, and keep its own alias table (do not copy the GPL filter files; the *idea* of alias merging is not copyrightable, but write our own mapping).

### 1.3 Other structured datasets worth knowing

- `OWASP/Nest` ships `backend/data/project-custom-tags/gsoc-2012.json … gsoc-2026.json`, per-year lists of OWASP projects that took part in GSoC (MIT). Evidence that umbrella orgs maintain sub-project participation lists.
- `cncf/mentoring/programs/summerofcode/{2017..2026}.md`, CNCF's GSoC ideas in one fixed markdown template per idea (`Description / Expected Outcome / Recommended Skills / Expected project size / Mentor(s) with GitHub handles / Upstream Issue (URL)`), Apache-2.0 code + `LICENSE-CONTENT`.
- `cncf/mentoring/programs/lfx-mentorship/{year}/{term}/` plus `automation/` (projects.yml, quotas.yml, term-issues.yml, board.json), LFX proposals are GitHub issue forms with validation bots.
- Outreachy: no public API; data model readable in `outreachy/website/home/models.py` (GPL-3).

---

## 2. Ideas pages: structure survey of all 183 GSoC-2026 orgs

### 2.1 Where ideas live (`ideas_link` from the official 2026 org list)

By URL kind: plain HTML sites 63, non-GitHub wikis (MediaWiki/Trac/Confluence/Atlassian) 29, GitHub wiki 29, GitHub blob (markdown in a repo) 27, Google Docs 12 (5 are published `/d/e/…/pub` pages, the rest `/edit` links), GitHub Pages 10, other GitHub URLs (repo root, discussions) 7, GitHub issue searches 5, bare `.md` 1. Hosts: github.com 68, docs.google.com 12, everything else 1 each (community.kde.org, wiki.openstreetmap.org, wiki.postgresql.org, trac.ffmpeg.org, wiki.qemu.org, openmrs.atlassian.net, forum.dbpedia.org, gitlab.com, …).

Fetch result (curl, 40 s timeout, UA set): **168/183 OK**. Failures: 404 on renamed GitHub wiki/blob pages (AOSSIE, Metaflow, R `rstats-gsoc/gsoc2026`, libreswan, aboutcode, CGAL), bot walls (GNU Radio 403; FreeBSD wiki returns Anubis "Access Denied" to non-browser clients), TLS failure (`wiki.NetBSD.org`), SageMath 502, VideoLAN timeout, Eclipse GitLab issue list, two orgs whose page is a stub (preCICE 321 B, GNU 61 B, gnu.org redirects). **Any parser must fall back to `contributor_guidance_url`, the org's official page, or cached text, and report "could not fetch" rather than guess.**

### 2.2 Deep samples (14 pages; field labels extracted by script)

| Org (format) | Idea container | Per-idea labels found | Notes |
|---|---|---|---|
| Dart (GitHub blob .md) | `## **Idea:** Title` ×6 | `Possible Mentor(s)`, `Difficulty`, `Project size`, `Skills`, `Description`, optional `Expected outcome`, `Further reading`, `Good Sample Project` | fully regular; bold-label lines |
| NixOS (GitHub blob .md) | `## Title` ×16 under `# Ideas` / `# Draft Ideas` | difficulty 14, size 36 mentions, skills 14, mentor 16 | labels inline in prose/bullets, still regular |
| MDAnalysis (GitHub wiki) | `## Project N: Title` ×7 | `### Summary / Detailed Description / Expected Outcomes / Relevant Skills / Related issues/PRs/etc. / Possible Mentors / Expected Size of Project / Difficulty Rating` | gold standard: fields are H3 headings |
| KubeVirt (GitHub wiki) | `### N. Title` ×5 | bold `GitHub issue`, `Description`, `Goal`, `Impact`, `Project requirements` | plus sections "Our stance on using AI for submissions", "What the proposal should contain" |
| Metasploit (GitHub blob .md) | `### Title` ×2 | mentor/skill/size in prose | has "AI Usage Policy" section |
| KDE (MediaWiki HTML) | `h2` = sub-project (Okular, Plasma…), `h3` = idea ×18 | bold `Brief explanation`, `Expected results`, `Knowledge Prerequisite`, `Mentor`, `Duration`, `Difficulty` | two-level umbrella; labels as `<b>` |
| OpenStreetMap (MediaWiki HTML) | `h2` = area, `h4` = idea ×16 | skills (mandatory/useful) 39 mentions, difficulty 16, length 90/175/350 | template per OSM wiki; "Note on using AI tools" section |
| Learning Equality (published Google Doc) | `h2` idea ×6 | `h3` `Background / Needs / Outcomes / Mentors / Skills / Size / Difficulty level` | published docs keep headings in HTML; `export?format=txt` would lose them |
| webpack (Google Doc, edit link → export txt) | 973 bytes | 2 ideas, difficulty/size inline | tiny doc; export works for `/document/d/{id}` only |
| CNCF (GitHub blob .md) | `#### Project` / `##### Title` ×15 | `- Description: / - Expected Outcome: / - Recommended Skills: / - Expected project size: / - Mentor(s): (@handle, email) / - Upstream Issue (URL):` | explicit template at top of page |
| Jenkins (HTML site) | one table: Project / Category / Skills to study | per-idea pages elsewhere (`.adoc` with YAML front matter `title, goal, category, year, status, mentors, skills, links`, sections Description / Quickstart / Links / Newbie-friendly issues) | ideas are first-class content objects with review gate |
| Python Software Foundation (HTML) | `h2` per sub-org ×8 | none, each h2 links out to the sub-org's own page | umbrella index; must follow links |
| NumFOCUS (GitHub blob .md) | index of links | none | same |
| Open Healthcare Network (GitHub issues `label:GSoC`) | issues API | 0 open issues with that label today | issue-tracker-as-ideas-page (Google's guide says this is "almost always grounds for rejection", yet 5 orgs do it) |

From web search (not fetched in full): GCC's 2026 call asks for title, 2-5 sentence description, expected outcomes, size, difficulty, mentors, required skills, "study pointers" (https://gcc.gnu.org/pipermail/gcc/2026-January/247396.html); Django's wiki template has Difficulty (Medium/Hard), Size (175/350), Mentors, Key skills (https://code.djangoproject.com/wiki/SummerOfCode2026); OSM's template splits skills into mandatory/useful and adds "Suggested By".

### 2.3 Aggregate over all 168 fetched pages

Mentions (≥2 occurrences of the label word on the page): `mentor` 129, size/hours 118, skills/prerequisites 113, difficulty 97, "expected outcome/result/deliverable" 74; all four of difficulty+size+mentor+skills: **76 pages**; ≥5 headings 125; GitHub links 86; any AI/LLM mention 122 (includes AI as a project topic).

Heuristic parser test (`parse_ideas.py`: pick the heading level that occurs ≥3 times most often, split into blocks, match `label: value` lines against a 30-label vocabulary, plus a `90|175|350 h` size regex): 172 files processed; 121 pages gave ≥3 blocks; **64 pages gave ≥3 "good" blocks (≥2 labelled fields and ≥3 lines)**; 735 good blocks out of 3,042; 96 pages yielded 0 good blocks. Best-structured: ASF (167 blocks/78 good, Apache's single ideas page is huge), STE||AR 44/44, BRL-CAD 25/21, Catrobat 21/21, Rocket.Chat 23/21, GRAME 22/19, Haiku 21/18, MetaCall 21/17, JBoss 17/16, KDE 18/16, ns-3 26/16, CNCF 15/15, MariaDB 15/15, NixOS 16/15, Qubes 18/15, FOSSi 14/14, Neovim 19/14, Open Robotics 18/14, Checkstyle 13/13, Ruby 17/13, Blender 12/12.

**Label vocabulary observed (case-insensitive):**
- difficulty: `Difficulty`, `Difficulty level`, `Difficulty Rating`, `Complexity`; values `easy|beginner|medium|intermediate|hard|advanced|difficult`.
- size: `Project size`, `Expected Size of Project`, `Expected project size`, `Size`, `Duration`, `Length`, `Project length`, `Time commitment`, `Hours`; values `90|175|350` optionally with `h|hr|hours`, or `small|medium|large`.
- mentors: `Mentor`, `Mentor(s)`, `Mentors`, `Possible Mentors`, `Potential Mentor(s)`, `Mentors name`; values often `Name (@github, email)`.
- skills: `Skills`, `Relevant Skills`, `Recommended Skills`, `Required Skills`, `Required/Desirable Skills`, `Skills required`, `Prerequisites`, `Knowledge Prerequisite(s)`, `Required knowledge`, `Project requirements`.
- outcome: `Expected Outcome(s)`, `Expected results`, `Outcome(s)`, `Deliverables`, `Goal`, `Impact`.
- links: `Related issues/PRs`, `Related bug reports`, `Upstream Issue (URL)`, `GitHub issue`, `Links`, `Resources`, `References`, `Further reading`.

Google's own recommendations for ideas pages (mentor guide): description (3-5 sentences), size (~90/175/350 h), prerequisites/skills, difficulty (easy/intermediate/hard), potential mentors; "defining a project" adds expected outcomes and says "must NOT be a link to your bug tracker" (https://google.github.io/gsocguides/mentor/making-your-ideas-page.html, https://google.github.io/gsocguides/mentor/defining-a-project-ideas-list.html).

**Verdict:** a dependency-free parser can extract title + size + difficulty + mentors + skills + links for roughly a third of orgs with high confidence, partial fields for another third, and must honestly return "unstructured" for the rest. Four engineering details matter: (a) use Google Docs `export?format=html` (or the `/pub` HTML) instead of `format=txt` so headings survive, the current `ideas.py` txt export flattens structure; (b) for GitHub wikis prefer `raw.githubusercontent.com/wiki/...` (works) and for MediaWiki use `?action=raw` (wikitext with `==` headings, **unverified** per site); (c) umbrella orgs (PSF, NumFOCUS, ASF, CNCF, INCF, ML4SCI, OSGeo…) need a second hop: collect outbound links under each H2 and parse those; (d) treat `label:GSoC` issue searches as a distinct "ideas are issues" mode and list the issues.

### 2.4 AI/LLM policy on ideas pages

75 of the fetched pages contain a policy-like sentence about AI/LLM use in proposals or contributions (regex: AI/LLM mention near propos|submission|polic|allow|prohibit|reject|disclos|generated). Examples (verbatim fragments): FOSSology "The proposal writing is a core part of the GSoC program and it should never be offloaded to the AI completely"; GRAME "It is fine to use LLMs/AI for spellcheck, language correction or translation, but do not rely on AI to write the proposal for you"; DeepChem "We allow students to use AI for research and for initial prototyping but we expect students to be fully responsible"; GA4GH "Code generation using AI is not forbidden, but generated code must be fully understood and reviewed thoroughly"; JBoss "The code submitted for this project should not be AI generated"; erofs provides a disclosure template sentence "This proposal was written with the assistance of [ChatGPT/Gemini/etc] to [check spelling / check accuracy / format text]"; dora-rs "You are allowed to use the AI coding tool of your choice"; Jitsi "We value your struggle, your questions, and your unique coding style more than a 'perfect' AI-generated fix"; KubeVirt has a section "Our stance on using AI for submissions"; Metasploit "AI Usage Policy"; API Dash "AI Usage Policy"; Catrobat "AI tools policy"; Blender/Graphite/Gambit link to an "AI contribution(s) policy". Policies therefore range from outright bans to permissive-with-disclosure and must be surfaced **per org**, not as one global rule.

---

## 3. Accepted-proposal archives and what they reveal

### 3.1 The archives

| Repo | Stars / license / last push | Content | Mechanics |
|---|---|---|---|
| SammanSarkar/GSoC_archive_2025, https://github.com/SammanSarkar/GSoC_archive_2025 | 1,046★ / MIT / 2026-10-19; site https://gsocguide.vercel.app | 43 PDFs in 30 org folders (`<Org>/<file>.pdf`) | README (count, org checklist, contributors) regenerated by a GitHub Action (`readme-maintainer.yml`, PyGithub, cron daily + on merged PR). Inspired by Aritra8438/GSoC_archive. |
| satwiksps/GSoC_archive_2026, https://github.com/satwiksps/GSoC_archive_2026 | 407★ / MIT / 2026-07-21 | 48 PDFs in 36 org folders | same pattern; clone-forks exist (nirmaltodwal7/GSoC_archive_2026 264★) |
| pavanjoshi914/GSoC_archive | 283★ / no license / 2026-10-09 | multi-year | |
| Aritra8438/GSoC_archive | 180★ / MIT / 2025-05-10 | accepted and rejected proposals, ≤2024 | |
| Google-Summer-of-Code-Archive/gsoc-proposals-archive | 504★ / MIT / 2024-03-20 | links + PDFs | |
| saketkc/fos-proposals | 534★ / MIT / 2024-05-15 | older archive with Python tooling | |
| COPS-IITBHU/GSoC-Accepted-Proposals | 526★ / none / 2025-05-28 | one institute's proposals | |
| ketankauntia/gsoc-orgs (gsocorganizationsguide.com) | 42★ / "other" / 2026-10-09 | **claim-verified** proposal library | contributor signs in with Google, claims the archived project/person, admin verifies against Google's archive, PDF is validated (`%PDF-`, ≤10 MiB, parsed), text-extracted and scanned for emails/phones, author confirms redaction, publishes under CC BY 4.0; eligibility rules (≤2 contributor claims, no contributor+mentor same year) enforced in DB functions. Site APIs (`/api/v1`, `/api/v2`) returned **402 DEPLOYMENT_DISABLED** on 2026-10-20. |
| satwiksps/openorganizations, https://openorganizations.site | 12★ / GPL-3.0 / 2026-10-19 | multi-program directory (GSoC, LFX, Summer of Bitcoin, ESoC, Outreachy, C4GT, Season of KDE) + proposals + "look inside umbrella organizations" | by the GSoC_archive_2026 author; "Inspired by gsocorganizations.dev" |
| airvitap/gsoc | 6★ / GPL-3 | GSoC + LFX + Season of KDE proposals | |

### 3.2 Structure of 43 accepted 2025 proposals (pdftotext + heading census)

Section-like headings by number of proposals containing them: **timeline 19, about me 17, deliverables 13, abstract 10, references 10, synopsis 9, personal information 8, benefits to the community 8, goals 8, table of contents 7, approach 7, implementation 7, motivation 6, overview 5, background 5, introduction 5, project timeline 4, related work 4, personal details 4, availability 4, milestones 4, community bonding period 4, deployment plan 4, testing plan 4.** Word counts: quartiles 2,186 / 3,473 / 4,511 (min 764, max 7,875). 31/43 contain a "Week N" schedule. Only 7/43 contain a `github.com/.../pull/N` link (several files are explicitly "Without contacts" versions, and many proposals describe contributions in prose). 12/43 mention ChatGPT/LLM/AI tooling.

### 3.3 Templates orgs actually ask for (verified)

- Google student guide elements: Name and Contact Information, Title, Synopsis, Benefits to Community, Deliverables (work breakdown with milestones, mark optional vs required, include investigation/coding/documentation), Related Work, Biographical Information, Follow the Rules; advice: submit a draft early, state time commitments, "under-scoped project that completes" beats ambitious (https://google.github.io/gsocguides/student/writing-a-proposal.html).
- LLVM 2025: descriptive title; your info; prior compiler experience; prior LLVM contributions with links; project info "fairly detailed" with Synopsis, Benefits to Community, Deliverables, Timeline, Related Work; four questions (why our org, why this project, why you, what you expect to get); known commitments. "proposals generated using Large Language Models (LLMs) will not be accepted" (https://discourse.llvm.org/t/gsoc-2025-projects-proposals-and-other-information/85035).
- Blender: Project Title, Name, Contact (email + chat.blender.org nick), **Pull Request** ("link to at least one pull request submitted to the Blender project"), Synopsis, Benefits, Deliverables (end-user docs are a deliverable), Project Details (diagrams/mockups welcome), Project Schedule (≥1 week buffer; note exams), Bio (https://developer.blender.org/docs/programs/gsoc/application_template/).
- openSUSE: Introduction (problem before solution), Project goals (what you will and won't do), Implementation, Timeline (modest and detailed beats ambitious), About me; warns copying the mentoring issue text "won't work" (https://github.com/openSUSE/mentoring/blob/gh-pages/templates/gsoc.md).
- RTEMS 2026 Google-Doc template (https://docs.google.com/document/d/1F5XCodvX8AYNqWX5ssu7dfjkmFT__83uf8ABKbB_Pkg/): header fields Project Title / Name / Discord Handle / Discourse Username / Email / University; "you need to disclose ALL resources you use, including other proposals, other individuals, web pages, AI assistants, etc. For AI assistance in particular, you should retain the prompts you use and the versions of your work as it develops"; must include: what/why paragraph, a sentence on how it will be maintained, documenting hand-over as a deliverable, increments that can be upstreamed if time runs out, a tutorial as deliverable, "Share a draft for feedback … (THIS IS A CRITICAL REQUIREMENT!!!)", and a list of questions mentors will ask ("What's the maintenance plan? How will we test it? We did this already... How is this an improvement? This is too much for you to complete in a summer"). Body: Project Abstract (50-60 words), Project Scope (Small/Medium/Large), Project Description, Project Deliverables keyed to GSoC dates.
- CNCF (GSoC ideas template) requires 2 mentors with a primary; LFX proposal issue form has `Technologies`, `Required/Desirable Skills`, `Mentors`, `Upstream Issue URL`, `Application Prerequisites` (Resume, Cover Letter, School Enrollment Verification, Participation Permission, **Coding Challenge** + URL, custom prerequisites with optional file upload).
- BeagleBoard template asks for a 10-milestone, one-per-week timeline (search result, page not fetched, **unverified**).

### 3.4 Licensing / privacy notes for proposals

PDFs contain names, emails, phone numbers, universities. Most archive repos license *the repo* MIT but say nothing about the PDFs' copyright; only ketankauntia's library obtains CC BY 4.0 consent and redacts PII. git-into-gsoc should **link** to archive folders (by org name) and never bundle, mirror, or quote proposals beyond section headings.

---

## 4. What organisations are told to look for (official) and what they say they do

### 4.1 Google's guidance (verified)

- Mentor guide, "Selecting a Contributor" (https://google.github.io/gsocguides/mentor/selecting-a-student.html): "The best GSoC contributors interact with your organization's community"; "Don't even think about selecting a GSoC contributor with whom you've had no contact"; "Anyone can write a good proposal"; red flags: "extremely short" or hard-to-read proposals, slow replies ("Failure to respond well or in a timely fashion almost guarantees problems"), copy-pasted multi-org proposals, overcommitment; "err on the side of rejecting"; "Past performance is usually an indicator of future GSoC success".
- Org Admin tips (https://developers.google.com/open-source/gsoc/help/oa-tips): initial filter removes spam and proposals that skipped a required task "such as a PR"; AI-generated low-quality submissions: "We suggest you ignore them"; "ALWAYS talk to every GSoC contributor you are considering selecting before the Org Admins begin ranking proposals"; "your org should NEVER select a GSoC contributor based solely on what they wrote in their proposal"; one committed mentor per excellent proposal ("two is better!"); rankings are binding for slots.
- Spam proposals resource, last updated 2026-02-26 (https://developers.google.com/open-source/gsoc/resources/spam_proposals): require community interaction and track it in a spreadsheet ("one of the strongest signals of a good proposal"); prerequisites: links to past contributions, small fixes/code challenges, early draft, required template; check draft creation/edit dates for copying; AI screening: enforce template with auto-disqualification for missing answers, search for leftover placeholders/buzzwords, typos as a human signal, short intro video, proposals that mirror the org's idea text, "Super pretty proposals are more likely to be AI-generated"; ask 3-5 org-specific questions; admin triage into Valid / Invalid-Spam / Out of Scope; standardized titles.
- AI guidance (https://developers.google.com/open-source/gsoc/resources/ai_guidance): "It is vital that you read through the GSoC organization's documentation"; "Some organizations do not allow any use of AI tooling, including in the writing of proposals"; "The human contributor retains 100% responsibility for the work"; prefer AI for research over code generation; verify licensing policy with the org.
- Warning signs during the program (https://google.github.io/gsocguides/mentor/warning-signs.html): time commitments, missed meetings, excuses/dishonesty, disappearing, scraps of code until mid-term, unscheduled time off.
- Student guide: choose orgs you use/are enthusiastic about long-term; "don't wait until the application period to initiate contact"; lurk first, "come up with at least a few legitimate questions before offering your opinion"; shortlist ideas, resolve questions, re-evaluate; "Do not copy the organization's idea text as your own project description"; "The earlier you apply, the better" (choosing-an-organization, making-first-contact, finding-the-right-project pages).

### 4.2 Org admins and mentors, 2025-2026 (verified unless noted)

- **OpenStreetMap, April 2025** (https://lists.openstreetmap.org/pipermail/gsoc-orga/2025-April/000260.html): 136 proposals vs 34 the prior year, "mainly due to an influx in AI-generated spam proposals"; pre-filter ignored proposals that were for an idea with no mentor, résumés only, had unfilled placeholders, or "no more technical content than the GSoC project idea page"; 17 remained after removing those without a mentor; mentors rate 0-9 in a shared spreadsheet; "do NOT consider any student that you have not been in personal contact with"; many auto-generated proposals followed Google's guide but lacked the required OSM account and contribution links.
- **Rust 2026** (https://blog.rust-lang.org/2026/04/30/gsoc-2026-selected-projects/): 96 proposals (+50%), 13 accepted; criteria: "prior interactions with the given applicant", "their contributions so far", proposal quality, project importance, mentor bandwidth; "somewhat struggled with some AI-generated proposals and low-quality contributions generated using AI agents, but it stayed manageable".
- **Jenkins** (https://community.jenkins.io/t/next-steps-for-mentors-proposal-grading-starts-april-4th/6497): grade 1-5; a 5 needs "A clear and well defined proposal", skills to "quickly hit the ground running", "completed contribution(s) to the project prior to submission, and attended office hours", demonstrated communication "on forums or gitter, on PR conversations". Jenkins also states it does **not** require contributions before applying (ideas standard page).
- **Wikimedia** (https://www.mediawiki.org/wiki/Google_Summer_of_Code/Mentors): "We strongly discourage giving priority to someone with prior contributions and fewer during the application phase"; prior contributions are only a tiebreaker; point applicants to microtasks; interviews recommended; WMF rubric for the final 2-3 (rubric not public).
- **INCF 2026** (https://incf.org/blog/gsoc-2026-proposal-submission-deadline-what-mentors-and-org-admins-need-know): evaluate on "Conversations and discussions with contributors", "Prior contributions and activity", "Demonstrated interest and engagement with your community"; "not to accept proposals from contributors who have had no prior interaction".
- **AiiDA 2026** (https://aiida.discourse.group/t/google-summer-of-code-gsoc-2026/706?page=2): "fully AI-generated content submitted without real engagement from the contributor actively hurts an application"; "The sheer volume of AI-generated PRs and architectural proposals we receive around the GSoC deadline"; single slot, many qualified applicants.
- **CRIU** (https://criu.org/Special:MobileDiff/5614): "Using LLM as a tool for brainstorming, drafting, or editing is acceptable" but "proposals generated predominantly by LLMs will be rejected".
- **Haiku** (search result): number and difficulty of resolved issues considered (**unverified**). **Drupal**: must disclose prior relationship with mentor and AI use (**unverified**). **FreeBSD** keeps a private 1-5 scoring spreadsheet (wiki page behind Anubis; **unverified**).
- Program scale (https://opensource.googleblog.com/2026/04/the-journey-begins-meet-the-2026-gsoc-contributors.html): 15,245 applicants from 131 countries, 23,371 proposals, 1,141 contributors, 184 orgs, >2,000 mentors/org admins → about 1 in 20 proposals and 1 in 13 applicants succeed.

### 4.3 Synthesised "what gets scored" (for a git-into-gsoc checklist)

1. Pre-application presence in the org's channels, with real questions (Google, OSM, INCF, Jenkins, Rust).
2. Contributions **during the application phase**, preferably merged, to the repos the idea touches (Wikimedia weights these above older ones; Blender requires a PR link in the proposal; Jenkins office hours).
3. Proposal content that goes beyond the idea text: scoping decisions, design, testing plan, maintenance plan, increments that can land independently (OSM pre-filter, RTEMS, openSUSE).
4. Exact template adherence and org-specific questions answered (Google spam page, LLVM, Drupal).
5. Honest time commitments and availability, week-level timeline with buffer (Google student guide, Blender).
6. Compliance with the org's AI policy, with disclosure where required (RTEMS, erofs, Drupal, CRIU, LLVM).
7. Responsiveness and tone in public threads (Google mentor guide, AiiDA's "professional standard" remark).

---

## 5. Project profiles (strongest first)

### 5.1 nishantwrp/gsoc-organizations: covered in §1.2. Critical assessment: best-known explorer; data model is the de-facto community schema; weaknesses are lag, lossy projection, manual updates, GPL code, and an explicit stance against activity metrics.

### 5.2 S3DFX-CYBER/FindMyGSoC: https://github.com/S3DFX-CYBER/FindMyGSoC (https://findmygsoc.vercel.app)
- 178★, **574 forks**, Apache-2.0, pure HTML/CSS/JS, last push 2026-10-21. Claims filters by tech stack, domain, "competition level", side-by-side org comparison, "Discover beginner-friendly Good First Issues", "Track live GitHub activity".
- How it works: static site; `.env.example` suggests a GitHub token for client-side calls; the repo is primarily a GSSoC'26/NSoC'26 contribution farm, `.github/scripts` contain `detect-low-effort-review.js`, mentor leaderboards, priority-label management, GSSoC/NSoC-specific issue and PR templates. I could not find a published data file (`/data/orgs.json` 404) so the "competition level" basis is **unverified**.
- Assessment: popular because of program-driven contributions, not because of data quality. Useful as a signal of what beginners ask for (competition level, comparison, GFI counts). Avoid: unverifiable "competition" scores.

### 5.3 ketankauntia/gsoc-orgs → gsocorganizationsguide.com
- 42★/36 forks, TypeScript (Next.js, Neon Postgres + Neon Auth, Cloudflare R2 behind a signed Worker), last push 2026-10-09. Catalog 2016-2025 imported from checked-in JSON (`new-api-details/`), views by project/contributor-slot/mentor/org/year/technology, editorial guides with RSS, `/api/v1` and `/api/v2` catalog APIs (currently 402 on Vercel), and the proposal library described in §3.1.
- Worth copying (as ideas): mentor and slot views; the strict privacy boundary for proposals; "public views never include email, evidence, notes"; importer with dry-run + reconcile commands.

### 5.4 SammanSarkar/GSoC_archive_2025 and satwiksps/GSoC_archive_2026: covered in §3. Pattern worth copying: README auto-maintained by Action; org-folder convention `<Org name>/<file>.pdf` makes org→proposal lookup trivial via the GitHub trees API.

### 5.5 sreehariX/gsoc-projectRecommendation (https://github.com/sreehariX/gsoc-projectRecommendation)
- 2★, MIT, TypeScript, 2025. "scrape 185 orgs ideas list and make each idea into a vector in total 2426 ideas"; prompt → top ideas with source links; fallback to DB listing when the Gemini key is exhausted; "Took the servers down, i will try to make this work for year 2026". Evidence that whole-program ideas extraction is feasible (≈13 ideas/org) and that users want semantic matching over filters; also evidence of the sustainability problem of hosted LLM features.

### 5.6 OWASP/Nest: https://github.com/OWASP/Nest (https://nest.owasp.org)
- 460★/736 forks, MIT, Python/Django + DRF, Algolia, slack-bolt, PyGitHub, OpenAI; 362 open issues; last push 2026-10-21. GSoC-umbrella org's own contributor platform.
- Mechanics verified in source: `Issue.summary` and `Issue.hint` are AI-generated on save (`generate_hint`, `generate_summary`) from prompts stored in a DB `Prompt` table (`github-issue-hint`, `github-issue-project-summary`, `github-issue-documentation-project-summary`, plus RAG and Slack question-detector prompts); a `mentorship` app with `Program → Module → Task(issue, assignee, status TODO/IN_PROGRESS/IN_REVIEW/COMPLETED, deadline)`, `IssueUserInterest(issue, module, user)` (people registering interest in an issue), `TaskLevel`, `ExperienceLevel`, `MatchingAttributes`; CI `check-contribution.yaml` uses `arkid15r/check-contribution-action` with `check_for: commit_sign_off, commit_signature, issue_assignee, issue_reference` and `close_on: issue_assignee, issue_reference`, PRs that don't reference an issue assigned to the author are auto-closed.
- Assessment: the most complete "org-side" model of newcomer workflow (interest → assignment → task → review). For git-into-gsoc this is the clearest statement that **assignment before PR** is enforced by some orgs, which the `issue` availability check already approximates.

### 5.7 cncf/mentoring: https://github.com/cncf/mentoring (https://mentoring.cncf.io)
- 3,123★, Apache-2.0 (+ LICENSE-CONTENT), last push 2026-10-19, 160 open issues. LFX proposals are GitHub issue forms (`lfx-program-proposal.yml`: project dropdown synced from the CNCF landscape, term, name, description, technologies, skills, mentors, upstream issue URL, application prerequisites incl. coding challenge); `programs/lfx-mentorship/{year}/{term}` + `automation/` (projects.yml, quotas.yml, term-issues.yml, board.json) track approvals; GSoC ideas per year in one markdown template. Mentee selection: Statement of Purpose, optional interviews, ≤3 applications per term (per README/LF docs; LFX platform itself has no public API I could find, **unverified**).

### 5.8 outreachy/website: https://github.com/outreachy/website
- 309★, GPL-3.0, Django. Data model (verified in `home/models.py`): `ProjectSkill(skill, experience_level ∈ {No knowledge required, Concepts, Experimented, Comfortable, Challenge} shown as 1-5, required ∈ {Optional, Preferred, Required})` with help text "Many Outreachy applicants choose not to apply for an internship project unless they meet 100% of the project skill criteria"; `Project(repository, issue_tracker, newcomer_issue_tag, longevity, community_size, …)`; `Contribution(applicant, project, date_started, date_merged, url, description, "If you used advanced tools to create this contribution, mention them here")`; `FinalApplication(experience, foss_experience, relevant_projects, applying_to_gsoc, time_correct, time_updates, community_specific_questions, timeline)`. Applicant docs: must record ≥1 contribution before a final application; generative-AI use must be documented with tool, version and prompts (https://www.outreachy.org/docs/applicant/).
- Assessment: the best-designed *applicant-side* data model in this space; directly adaptable to git-into-gsoc's progress store.

### 5.9 Generic good-first-issue tooling
- EddieHubCommunity/good-first-issue-finder (631★, MIT, Svelte, last push 2024-08-11): GitHub OAuth, then a GraphQL `search(type: ISSUE)` with the user's query string, 10 per page, returning labels, repo language, **code of conduct and license** per issue (`src/routes/api/get-issues/+server.ts`). UX detail worth copying: show CoC/license presence next to each issue.
- deepsourcelabs/good-first-issue (3,544★, MIT; goodfirstissue.dev): curated repo list + Python data script generating `generated.json` and `tags.json`; quality bar enforced by curation rather than search.
- up-for-grabs/up-for-grabs.net (6,034★): YAML project registry with a per-project label.
- codetriage/codetriage (1,471★, MIT): subscribe to repos, "once a day you'll be emailed with an open issue from that repository, and instructions on how to triage", a 13-year-old proof that a **one-issue-a-day digest** retains newcomers.
- 0xVikasRushi/OpenIssueMonitor (22★, MIT): single-repo label watcher polling GitHub every 10 s and alerting on Telegram; `/addLabel` command.
- firstcontributions/first-contributions (56k★): the canonical first-PR tutorial; relevant only as the on-ramp orgs expect beginners to have done.

### 5.10 Smaller / historical GSoC explorers (all verified metadata)
- Sparsh1212/gsocanalyzer (76★, MIT, 2022): search by tech/org/category/topic, per-year charts, **bookmarks**, `scrape.py` + manual `merge.py` for duplicate org names.
- RajGM/GSoC_OrganizationsTracker (18★, 2022), tusharinqueue/Globoc (3★, 3D globe of 520 orgs), sdivyanshu90/GSoC-Explorer (1★, Next.js), RajeevDash007/gsoc-github-finder (2★, MIT, 2024, "Track GSoC organizations, explore their repositories, and find beginner-friendly issues": the closest conceptual match to `repos`/`issues`, but a Next.js boilerplate README), sombek/gsoc-scraper (2★, scraped 2025 ideas into a site), Marvin9/gsoc-timeline (2★, npm `gsoc-timelines`, prints the timeline, the only GSoC CLI I found, 2019), hkirat/gsoc-good-first-issues (689★, a static 2023 list of issue URLs grouped by language), erdengk/gsoc-analyse (583★, Chinese experience-sharing docs site), gsoc-cn/gsoc-cn (964★, Chinese alumni community + proposal samples), google/gsocguides (541★, the guides themselves), numfocus/gsoc (653★, NumFOCUS ideas-list repo), neutralinojs/gsoc2026 (123★, an org's ideas repo), AOSSIE-Org/OrgExplorer (45★, browser-only GitHub-org dashboards: bus factor, contributor networks, IndexedDB cache, relevant to `repos ORG`).
- apsinghdev/opensox (395★, AGPL-3.0, 93 open issues): general OSS-project discovery platform (Next.js + tRPC + Postgres), not GSoC-specific; not studied further.

### 5.11 Bots, extensions, other programs
- No GSoC-specific Discord/Telegram bot found; generic GitHub→chat relays exist (GitTrack.me, "GitHub issue bot" on top.gg, n8n template, AOSSIE Gitcord). No established "good first issue" browser extension (Kororin, Open Source Pal: tiny user counts, third-party listings only, **unverified**).
- LFX: `linuxfoundation/lfx-mentorship` (2★, MIT, Go + Nuxt) is a rewrite "in implementation"; no public data API found. MLH Fellowship, Season of Docs, Summer of Bitcoin, GSSoC: only curated lists (deepanshu1422/List-Of-Open-Source-Internships-Programs 5,204★; yashisrani/List-of-OpenSource-Programs 484★), no tooling or datasets found.

---

## 6. Synthesis

### 6.1 Brilliant ideas worth adapting
1. **Mentor continuity from the official archive.** `mentor_names` per project per year lets us show "who has mentored at this org, for how many years, on which topics", the single most actionable "who to talk to" fact, from a primary source (§1.1).
2. **Contribution ledger with dates and merge status** (Outreachy `Contribution`): the proposal section mentors actually want ("link to at least one pull request", Blender; "contribution links", OSM) can be generated from a ledger instead of remembered at the deadline.
3. **Skill requirements as (level 1-5 × required/preferred/optional)** (Outreachy `ProjectSkill`): a parsed idea's "Skills" line can be mapped onto the user's inferred languages to rank ideas, instead of orgs.
4. **Org-side spam filters as a self-check** (Google spam page, OSM pre-filter): a proposal pre-flight that flags placeholders, idea-text mirroring, missing required sections, missing contribution links, missing time commitments.
5. **One-issue-a-day digest** (CodeTriage) and **label watchers** (OpenIssueMonitor) for tracked repos, proven retention mechanics with trivial implementation on top of the existing cache.
6. **Issue "hint"** (OWASP Nest), but without an LLM: grep the repo for identifiers quoted in the issue and list candidate files (this stream only notes the demand; the mechanism belongs to the codebase stream).
7. **Claim-verified, PII-scanned proposal sharing** (ketankauntia), if git-into-gsoc ever surfaces proposals, link to libraries that have consent, not raw PDFs.
8. **Jenkins' idea standard** (Quickstart + Newbie-friendly issues per idea, review gate): when an idea block links issues/PRs, surface them as "starter issues named by the org itself", higher-trust than label search.

### 6.2 Proven patterns
- Org folder = org name in proposal archives; README regenerated by Actions.
- Year-file + merged-file split in the archive API; ETag revalidation.
- Alias tables for org names and tags; recursion with cycle guard.
- Keep only recent years' tags for matching (gsocorganizations' 3-year rule), matches git-into-gsoc's intent of "current" relevance.
- Explicit per-org AI policy sections (KubeVirt, Metasploit, API Dash, Catrobat), orgs expect applicants to find and follow them.

### 6.3 Pitfalls to avoid
- "Competition level" and "activity" scores with no stated evidence (FindMyGSoC; the gsocorganizations maintainer's objection in #150 is sound: activity depends on timing).
- Hosted LLM features that die when a key runs out (gsoc-projectRecommendation; gsocorganizationsguide's APIs are 402 today).
- Treating `export?format=txt` of Google Docs as structure-preserving; treating 404/403/bot-wall pages as "no ideas".
- Implying that proposal archives are licensed for reuse; copying GPL filter tables.
- Counting the public archive as "all projects" (only `status: passed` is exposed) or using `contributor_count` as accepted contributors (it looks like applicants).
- Generic "contribute to anything" advice, every 2025-2026 org voice says volume of AI-assisted PRs *hurts*.

### 6.4 Licensing / attribution notes
- Official JSON: Google's site terms; we consume public JSON exactly as the SPA does; cite summerofcode.withgoogle.com in output (already done).
- api.gsocorganizations.dev: GPL-3.0 code; JSON consumption fine; attribute the site when its data is shown (already done). Do not port `api/filters/*.js` tables.
- google/gsocguides: GitHub says license "other" (the site states a CC license, **unverified**); quote short passages with citation only.
- Outreachy website GPL-3.0, OWASP Nest MIT, cncf/mentoring Apache-2.0 + content license, EddieHub finder MIT, goodfirstissue MIT, CodeTriage MIT, FindMyGSoC Apache-2.0, openorganizations GPL-3.0, opensox AGPL-3.0: we adapt data-model ideas only; no code is copied.
- Proposal PDFs: personal data; link only (SammanSarkar/satwiksps/pavanjoshi914/Aritra8438 repos are MIT for the repo, silent on PDFs; ketankauntia publishes under CC BY 4.0 with consent).

---

## Feature proposals for git-into-gsoc

Effort: S ≤ 1 day, M ≈ 2-4 days, L ≈ 1-2 weeks. Each proposal names the evidence that motivates it.

**P1. Official archive client (`gsoc/official.py`): orgs, projects, mentors, per-project tags, S/M.**
Add `archive_programs()`, `archive_organizations(year)`, `archive_organization(year, slug)`, `archive_projects(year)` (cache the 2 MB list per year with the existing ETag layer), `archive_project(id)`. Use them to (a) build multi-year history from the primary source and keep gsocorganizations.dev as fallback/cross-check (the two agree: 1,191 passed projects in 2025); (b) add `mentor_names`, `project_code_url`, per-project `tech_tags/topic_tags`, `id`, `organization_slug` to `org`/`projects` output; (c) show "mentors seen N years" and "past project code lives in repo X" (429 github.com + 268 gist + 60 PR links in 2025). Also read `/api/program/` once for all years' milestones and `stats.allocated_projects` / `orgs_accepted`, and surface `phase` ("project_work", "program_archived") in `program`. Evidence: §1.1 probes; SPA constants `ARCHIVE_PATH="/archive/"`, `PROGRAMS_PATH="/archive/programs/"`.

**P2. Tiered ideas-page parser → `ProjectIdea` objects, M.**
Fetch via format-aware URL mapping (GitHub blob/wiki raw, Google Docs `export?format=html` or `/pub` HTML, MediaWiki `?action=raw` where available, issue-label searches via the GitHub API). Tier 1: heading-split + label regex over the vocabulary in §2.3 (`difficulty`, `size` incl. `90|175|350` and small/medium/large, `mentors` incl. `@handles`, `skills`, `expected outcome`, `links`), with a per-page confidence score (fraction of blocks with ≥2 fields). Tier 2: umbrella pages, follow outbound links under each H2 and parse children (PSF, NumFOCUS, ASF, CNCF, INCF). Tier 3: return `unstructured` with the raw text excerpt and the fetch error, never a guess. Expose `ideas ORG [--size --difficulty --skill]` and `gsoc_ideas` MCP tool; feed `recommend` with idea-level skill matching. Expected coverage from the survey: high-confidence structure on ~35-40% of orgs, partial on ~30%, honest "unstructured" on the rest. Evidence: §2 (64/172 pages parse cleanly; label vocabulary; 15 fetch failures).

**P3. Contribution ledger + proposal evidence pack, M.**
Extend the progress store with `contributions[{url, repo, type: issue|pr|review|comment, date_started, date_merged, status, idea_ref, note}]`, auto-refreshed from the GitHub API (merged? closed? review state?), plus `git-into-gsoc evidence --org X --format md` that renders a "Prior contributions" section (links, dates, merge status) and a "Community interaction" section (threads the user has recorded). Mirrors Outreachy's `Contribution` model and the Blender/OSM/LLVM requirement to link PRs. Evidence: §3.3, §4.3; only 7/43 archived proposals embed PR links today, which is exactly the gap mentors complain about.

**P4a. Org AI/LLM-policy extractor, S.** When fetching an org's ideas/guidance pages, extract sentences matching the AI-policy regex (§2.4) and classify as `prohibited | restricted_with_disclosure | permitted | unknown`; show it in `org` and in the proposal checklist with the quote and source URL. 75/168 pages carry such a sentence; policies range from bans (LLVM, JBoss) to disclosure templates (erofs, RTEMS).

**P4b. Proposal pre-flight lint, M.** Given a draft (markdown/txt/PDF via pdftotext if present), check: required sections (Synopsis, Benefits, Deliverables, Timeline with week granularity and buffer, About me, Availability/commitments, Related work), org-template adherence (fetch the org's template URL from `contributor_guidance_url` when it is a doc/wiki), presence of contribution links, "mirrors the idea text" similarity against the parsed idea description, leftover placeholders (`[Your name]`, `TODO`, `Lorem`), generic buzzword density, missing maintenance/testing plan, and AI-disclosure line when the org requires it. Output is advice with citations, not a score. Evidence: Google spam page (2026-02-26), OSM pre-filter, RTEMS template, §3.2 heading census.

**P5. Tracked-repo digest, S.** `git-into-gsoc digest [--since 7d]`: for tracked repos (progress store), list new/unassigned beginner-label issues, newly answered threads on tracked issues, and ideas-page changes (hash of fetched text). Optional `--one` to emit a single best issue (CodeTriage). MCP tool `gsoc_digest`. Evidence: §5.9 (CodeTriage, OpenIssueMonitor), gsocorganizations issue #130.

**P6. Past-proposal pointers, S.** Build a small index (refreshed via the GitHub trees API, cached) of org folders in the known archive repos (SammanSarkar/GSoC_archive_2025, satwiksps/GSoC_archive_2026, pavanjoshi914/GSoC_archive, Aritra8438/GSoC_archive, Google-Summer-of-Code-Archive/gsoc-proposals-archive, saketkc/fos-proposals, COPS-IITBHU) and link `org` output to "N accepted proposals for this org (external, personal data, read, don't copy)". Never download PDFs by default. Evidence: §3.1.

**P7. Evidence-based "slot competition" panel, S.** Replace any temptation to score "competition" with facts: projects per year (archive), mentors per project distribution, number of parsed ideas, number of beginner issues open, and Google's 2026 ratio (23,371 proposals → 1,141 projects). Evidence: §5.2 (FindMyGSoC's unverifiable score), §4.2 numbers.

**P8. Umbrella-org expansion, M.** For orgs whose ideas page is an index (PSF, NumFOCUS, ASF, CNCF, INCF, ML4SCI, OSGeo, Linux Foundation workgroups), resolve sub-projects from (a) ideas-page links, (b) `project_code_url` hosts/repos of past projects, (c) OWASP-style custom-tag lists when present, and let `repos`/`issues` operate at sub-project granularity. Evidence: §1.1 (umbrellas dominate project counts), §2.2 (PSF/NumFOCUS index pages).

**P9. Tag normalisation table of our own, S.** Per-project `tech_tags` in the official archive are free text ("C, Kernel"); write an MIT alias map (split on commas/slashes, lowercase, map `nodejs|node.js|NodeJS`, `cpp|c++`, `js|javascript`, …) for matching; cite gsocorganizations' approach as prior art without copying its GPL tables. Evidence: §1.2, issue #209.

**P10. MCP resources for ideas and policies, S (ties to another stream).** Expose parsed ideas (`gsoc://org/{slug}/ideas`) and the org AI policy as MCP resources so agent clients can ground proposal help in the org's own words.

Out of scope but noted: multi-program support (LFX/Outreachy/Season of KDE as in openorganizations.site) is L and would need per-program data models; Outreachy and LFX have no public APIs.
