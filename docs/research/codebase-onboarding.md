<!-- Research working notes. Written 2026-10-20/21 during the ecosystem research pass; kept as the evidence base for ../research.md. Claims marked unverified were not confirmed against a primary source. Plain-language rules apply loosely here; these are notes, not a guide. -->

> Working notes from the research pass of October 2026. Codebase understanding and onboarding tools, and the GitHub API toolbox behind orient and pointers. The checked conclusions are in [the research summary](../research.md); these notes keep the evidence, numbers, and URLs behind them. Items marked unverified were not confirmed against a primary source.

# Stream D: Codebase understanding and contributor onboarding ("I picked a repo, now what?")

> Verification status. Re-checked first hand on 2026-10-21: aider's `repomap.py` weights, the Agentless file-level prompt, the CodeTour schema, the repomix README, the DeepWiki complaint threads, Cody's archived retrievers, and the closing-pull-request rule on matplotlib. Also opened: codeglance's detectors, learn-codebase's skill, aoci-code, repo-map and repomind. Links: 39 of 42 resolved with HTTP 200 on 2026-10-21; the rest are URL templates with placeholders, endpoints that need a token, or sites that block scripts. Everything else here is the research stream's working record as written.

Research date: 2026-10-21. All GitHub numbers (stars, pushed_at, licence) were read live via `gh api` on that date; all claims about a project's internals come from its source or official docs fetched during this session (URLs inline). Anything I could not confirm is marked **unverified**.

---

## TL;DR

1. **No existing tool solves the GSoC newcomer's problem.** Repo packers (repomix, gitingest, code2prompt) dump the *whole* codebase into an LLM prompt; wiki generators (DeepWiki, deepwiki-open) produce confident prose that maintainers publicly call wrong; retrieval servers (GitMCP, Context7) answer "how do I *use* this library", not "how do I *change* it". None produce the two things a first-time contributor actually needs: a cheap **orientation sheet** (where things are, how tests run, who merges, what the rules are) and **issue→code pointers** backed by what previous fixes touched.
2. **The best algorithmic ideas are small and portable.** aider's repo map ranks symbols with PageRank over tree-sitter definition/reference edges inside a token budget (exact weights in §1.1). Agentless found that giving an LLM *full file paths* instead of a nested tree was the single most important trick to stop hallucinated paths. deepwiki-open forces every generated claim to carry `Sources: [path:lines]()`. CodeTour's `.tour` JSON is a 3-field schema (file, line, description) that turns "reading plan" into something a newcomer can click through. All four are adaptable to an API-only design.
3. **GitHub's REST API is enough, and cheap.** One `git/trees?recursive=1` call gives the entire file tree (limit 100,000 entries / 7 MB); one `issues/{n}/timeline` call reveals the PR that closed an issue; one `pulls/{n}/files` call shows what that fix touched; `commits?since=` gives active maintainers; `.github/workflows/*.yml` `run:` lines give the real test command; check-run names give CLA/DCO. I prototyped the full chain on matplotlib in **16 API calls**: 4/6 closed good-first-issues had a same-repo PR whose `merged_at` was within **1 second** of the issue's `closed_at` (the "Fixes #n" signature), the fix PRs touched a median of **2 files**, and **5/5 touched `lib/matplotlib/tests/`**, exactly the kind of evidence that tells a beginner "you will be expected to add a test".
4. **Two traps found empirically**: timeline cross-references include PRs from *other* repositories (matplotlib #9970 was "referenced" by merged PRs in `sherpa/sherpa` and `open-atmos/PySDM`), filter on `source.issue.repository.full_name`; and matplotlib's label is literally `🌱 Good first issue`, so hard-coded label strings miss repos (the tool already has `pick_beginner_label`; reuse it in queries).
5. **The research on good-first-issues is unambiguous about what to show beginners.** GFIs that newcomers actually finish touch fewer, simpler files (Huang et al. ESEM'21); 40.9% of labelled GFIs are *not* solved by newcomers and 31.2% of newcomers fail after several attempts (cited in RecGFI, ICSE'22); the newcomer-GFI merge rate fell from 61.9% to 42.2% while GFI supply shrank from Jan 2024 (Hoshikawa et al. 2026); and retention correlates with *interaction* (project members participating) more than with the issue's intrinsic attributes (Hao et al. 2026). Translation: show the newcomer the fix-size norm, the test expectation, who reviews, and the project's explicit AI/assignment policy (matplotlib's bot says "we do not assign issues … do not try to automate a solution using AI").
6. **Local clone / tree-sitter mode is not worth it yet.** `tree-sitter-language-pack` is only ~2.2-2.5 MB per wheel (MIT, 372 grammars), so it is *feasible*, but the API-only pointers already resolve stack traces, paths and identifiers, and GitHub code search (10 req/min, default branch only) covers "where is this symbol". Ship API-first; keep a `[local]` extra as a later option.
7. **Top proposals (details in §8):** `orient OWNER/REPO` (S/M), `pointers OWNER/REPO#N` (M), `fix-patterns` evidence from closed-GFI fix PRs (M), `reading-plan` with optional CodeTour export (S), MCP resources + prompts for the orientation sheet (S), and a strict "facts and paths only, no architecture prose" output contract (S, policy).

---

## 0. What was examined, and how

- Source read directly (via `gh api … contents`): aider `aider/repomap.py` (867 lines) and `aider/special.py`; GitMCP `src/api/tools/commonTools.ts`, `src/api/utils/github.ts`, `githubClient.ts`; gitingest `src/gitingest/clone.py`; repomix `src/core/git/gitHubArchiveApi.ts`, docs `code-compress.md`, `agent-skills-generation.md`, `mcp-server.md`, tree-sitter `queries/README.md`; deepwiki-open `api/services/wiki/structure.py`, `prompts.py`, `codemap.py`; Agentless `agentless/fl/FL.py`, `util/preprocess_data.py`, `fl/retrieve.py`; CodeTour `.tours/intro.tour`; matplotlib `.github/workflows/good-first-issue.yml`, `pr_welcome.yml`, `PULL_REQUEST_TEMPLATE.md`; airflow `.github/CODEOWNERS`; rust-analyzer `docs/book/src/contributing/architecture.md`.
- Papers read (PDF): Huang et al., "Characterizing and Predicting Good First Issues", ESEM 2021; Xiao et al., "Recommending Good First Issues in GitHub OSS Projects" (RecGFI), ICSE 2022. Abstracts: Hoshikawa et al. arXiv:2604.27532; Hao et al. arXiv:2603.27136.
- Docs fetched: GitHub REST (trees, contents, timeline, pulls/files, search code, community profile, CODEOWNERS, linking PRs to issues), legacy code-search syntax, DeepWiki MCP + DeepWiki docs, Context7 README + adding-libraries, Greptile graph doc, Sourcegraph Cody context doc, opensource.guide, matklad's ARCHITECTURE.md post.
- Prototypes run (≈35 API calls total, all outputs in the scratchpad `research/D-proto/`): matplotlib closed-GFI → fix-PR → files pipeline; CI test-command extraction; 90-day committer histogram; recursive tree histogram; issue-body path/identifier extraction on IBM/import-tracker #55 followed by one code-search call. Script: `research/D-proto-scripts/pointers.py` (stdlib only).

---

## 1. Project studies

### 1.1 aider repo map: `Aider-AI/aider`, `aider/repomap.py`

- **Facts**: 49,672★, Apache-2.0, Python, pushed 2026-05-22. https://github.com/Aider-AI/aider
- **What it does**: builds a token-budgeted "map" of the most important definitions in a repo for an LLM pair-programmer, refreshed as the chat context changes.
- **How it works (verified from source)**:
  - *Tags*: for each file, `grep_ast.filename_to_lang` picks a tree-sitter grammar; a per-language `tags.scm` query yields captures named `name.definition.*` (kind `def`) and `name.reference.*` (kind `ref`). If a grammar yields only defs (C++ is given as the example), Pygments lexer `Token.Name` tokens are back-filled as refs with `line=-1`.
  - *Cache*: tags are cached in `diskcache` (SQLite) under `.aider.tags.cache.v4`, keyed by absolute path, invalidated by `mtime`. The code carries workarounds for real issues: SQLite corruption → recreate or fall back to a dict (issue #1308), Windows cross-drive relpath `ValueError` (issue #1288), PageRank `ZeroDivisionError` on degenerate graphs (issue #1536).
  - *Graph*: `networkx.MultiDiGraph`; for each identifier defined somewhere and referenced somewhere, add edge `referencer_file → definer_file` with weight `mul * sqrt(num_refs)`, where `mul` starts at 1.0 and is multiplied by **10** if the identifier was mentioned in the chat, **10** if it is snake/kebab/camel case *and* ≥ 8 chars, **0.1** if it starts with `_`, **0.1** if it is defined in > 5 files, and **50** if the referencing file is already in the chat. Unreferenced definitions get a 0.1 self-edge so they are not dropped.
  - *Ranking*: personalised PageRank (`personalization` = `100/len(files)` for chat files, mentioned files, and files whose path components intersect mentioned identifiers; `dangling` = same). Each node's rank is then redistributed along its out-edges proportionally to weight, and summed per `(definer_file, identifier)`; chat files themselves are excluded from output.
  - *Budget*: default `map_tokens=1024`; with no chat files the budget becomes `min(1024 * map_mul_no_files(8), context_window - 4096)`. It binary-searches the number of ranked tags to render so that the rendered tree is within **15 %** of the budget (`ok_err = 0.15`), starting from `max_map_tokens // 25` tags. Rendering uses `grep_ast.TreeContext` to show just the definition lines with structural context; every line is truncated to 100 chars (minified-JS guard). Token counting samples 1 % of lines for texts > 200 chars.
  - *Always-included files*: `special.py` lists ~170 root files (README*, CONTRIBUTING*, LICENSE*, CHANGELOG*, SECURITY*, CODEOWNERS, package manifests, lint/CI/docker/cloud configs, `.pre-commit-config.yaml`, `tox.ini`, `mkdocs.yml`, `.readthedocs.yaml`, …) plus any `.github/workflows/*.yml`; these are prepended to the ranked list.
- **UX worth copying**: budgeted output, "mentioned identifiers boost rank", "special files first", graceful cache failure.
- **Avoid**: the dependency stack (tree-sitter + language pack + grep_ast + pygments + networkx + diskcache + tqdm) and the need for a local checkout; both contradict git-into-gsoc's API-only/cheap design. The rendering is for an LLM that will *edit* code; a GSoC beginner needs *where to look*, not every signature.
- **Community feedback**: issues referenced in the code (#1288, #1308, #1536) show the fragile parts are the disk cache and the graph edge cases, a warning for any port.
- **Assessment**: high-quality, battle-tested; the *weights* and the "paths that match mentioned identifiers" trick are directly reusable as heuristics on API data.

### 1.2 repomix: `yamadashy/repomix`

- **Facts**: 28,941★, MIT, TypeScript, pushed 2026-10-18. https://github.com/yamadashy/repomix
- **What it does**: packs a repository into one XML/Markdown/JSON/plain file for LLMs, with a directory tree, per-file token counts, optional git logs/diffs, and Secretlint-based secret filtering.
- **How it works (verified)**:
  - Remote repos are fetched as a **tarball from `codeload.github.com/{owner}/{repo}/tar.gz/{ref}`** ("skips the 302 redirect … saving ~100-300ms"), not `git clone`; 403 with `X-RateLimit-Remaining: 0` is surfaced as a rate-limit error (`src/core/git/gitHubArchiveApi.ts`).
  - `--compress` uses tree-sitter to keep signatures/interfaces/classes and drop bodies, rendering `⋮----` separators; documented as **experimental** (`website/.../code-compress.md`). Its tree-sitter queries are "modified versions of tree-sitter queries from Aider and Cline" (both Apache-2.0) per `src/core/treeSitter/queries/README.md`.
  - `--include-logs` (default 50 commits, "commit dates, messages, and file paths"), `--include-diffs`, `--token-budget N` (non-zero exit when exceeded), `--token-count-tree`, `--remote-trust-config` (remote config is untrusted by default).
  - `--skill-generate` emits a Claude Agent Skill directory: `SKILL.md` + `references/{summary.md, project-structure.md (tree with line counts), files.md (all contents, grep-friendly), tech-stacks.md}` (experimental).
  - MCP server tools: `pack_codebase`, `pack_remote_repository`, `read_repomix_output`, `grep_repomix_output`, `file_system_read_file`, `file_system_read_directory`; `--sandbox` confines file tools to a workspace root and disables remote/network tools.
- **Worth copying**: tarball-instead-of-clone when a full snapshot is really needed; `--token-budget` as a hard output cap; the *shape* of the generated skill (`project-structure.md` with line counts, `tech-stacks.md`); treating remote repo config as untrusted.
- **Avoid**: the core product (full-content packing) is the opposite of what a beginner needs; it is also where token bloat comes from.
- **Assessment**: mature, well-documented, security-conscious. Relevant only as a reference for output structure and the tarball trick.

### 1.3 gitingest: `cyclotruc/gitingest` (now `coderamp-labs/gitingest`)

- **Facts**: 15,970★, MIT, Python, pushed 2026-10-21. https://github.com/coderamp-labs/gitingest
- **What it does**: "Replace `hub` with `ingest` in any GitHub URL" → summary + tree + concatenated contents; CLI and Python API `ingest(url) -> (summary, tree, content)`.
- **How it works (verified)**: `clone.py` requires git, checks the repo exists, resolves the commit, then clones with `single_branch=True, no_checkout=True, depth=1`; for a sub-path it uses `--filter=blob:none --sparse`; respects `.gitignore` by default; token count in the summary.
- **Worth copying**: the URL-shaped UX (`owner/repo/tree/main/subdir`); the `--filter=blob:none --sparse` recipe if a local mode is ever added.
- **Avoid**: cloning by default; whole-content output.
- **Assessment**: simple and popular; nothing algorithmic to adapt beyond the clone recipe.

### 1.4 GitMCP: `idosal/git-mcp`

- **Facts**: 8,471★, Apache-2.0, TypeScript (Cloudflare Workers), pushed 2026-05-08. https://github.com/idosal/git-mcp
- **What it does**: remote MCP server `gitmcp.io/{owner}/{repo}` exposing `fetch_<repo>_documentation`, `search_<repo>_documentation`, `search_<repo>_code`, `fetch_url_content`.
- **How it works without cloning (verified in `commonTools.ts`, `github.ts`, `githubClient.ts`)**:
  - Documentation fetch order: `llms.txt` (with robots.txt check for GitHub Pages sites) → landing page → `README.md`; for repos: static paths `docs/docs/llms.txt`, `llms.txt`, `docs/llms.txt` via `raw.githubusercontent.com` → GitHub code search `filename:llms.txt repo:o/r` → pre-generated `llms.txt` in R2 → README via code search `README path:/`. Default branch from `GET /repos/{o}/{r}` with `main`/`master` HEAD fallback.
  - Result cache TTL 30 min; Cloudflare tiered cache: 200 → 3600 s, 404 → 60 s; a rate-limit tracker reads `x-ratelimit-*` headers and sleeps when remaining < 5.
  - Code search = `GET /search/code?q={query}+repo:{o}/{r}`, 30 results/page, returns path/url/score only.
  - `searchRepositoryDocumentationNaive` **returns the entire documentation as a "fallback"** when no vector index exists, a token-bloat anti-pattern.
- **Worth copying**: the "no clone" stance; `llms.txt` → README fallback chain; caching 404s briefly; header-driven rate-limit back-off (git-into-gsoc already has retries/throttling; add the "remaining < N → defer optional calls" idea).
- **Avoid**: dumping whole docs as a fallback; the README-only model of a repository.
- **Assessment**: pragmatic, small; its GitHub plumbing is a good sanity check for an API-only design.

### 1.5 DeepWiki (Cognition) and deepwiki-open

- **DeepWiki facts**: proprietary; MCP at `https://mcp.deepwiki.com/mcp` (SSE legacy at `/sse`), "free, remote, no-authentication-required", public repos only; tools `read_wiki_structure`, `read_wiki_contents`, `ask_question` (parameters undocumented on the page). https://docs.devin.ai/work-with-devin/deepwiki-mcp
  Generation effort tiers: low (free, default), medium "5-10 ACUs", high "20-40 ACUs"; `.devin/wiki.json` can pin pages (≤30, 80 enterprise; ≤100 notes; ≤10,000 chars/note) and "When a config file is present, we bypass the default cluster-based planning". https://docs.devin.ai/work-with-devin/deepwiki
- **Community feedback (negative, primary sources)**: an OpenWrt package maintainer reports users filing bug reports based on wrong DeepWiki pages and that pages are not regenerated when the repo changes (https://forum.openwrt.org/t/important-consideration-deepwiki-ai-generated-docs-may-contain-inaccuracies/249471); a Scala contributors thread titled "AI slop claiming to be documentation" says the Scala 3 wiki is largely wrong and there is no simple removal path (https://contributors.scala-lang.org/t/ai-slop-claiming-to-be-documentation/7382); a hands-on test found it fine on a simple blog engine and "full of factual errors" on an assembler (https://zeli.app/en/story/48930871).
- **deepwiki-open facts**: `AsyncFuncAI/deepwiki-open`, 18,234★, MIT, Python/Next.js, pushed 2026-09-03. https://github.com/AsyncFuncAI/deepwiki-open
- **How deepwiki-open works (verified)**:
  - `build_structure_prompt(owner, repo, file_tree, readme, comprehensive, language)` sends the **complete file tree + README** and asks for XML `<wiki_structure>` with 4-6 (concise) or 8-12 (comprehensive) pages, each listing `relevant_files` that "should be actual files from the repository".
  - `build_page_prompt` requires a `<details>` block listing ≥ 5 source files, Mermaid diagrams, and "For EVERY piece of significant information … you MUST cite … `Sources: [src/full/path/file.ext:start_line-end_line]()`", "NEVER a bare filename", and "All information must be derived SOLELY from the [RELEVANT_SOURCE_FILES]".
  - It clones the repo and builds a RAG index (`api/rag/`), and `codemap.py` runs a two-call "skeleton → enrich" flow and then `_ground_citations` to verify quoted snippets actually exist in the files.
- **Worth copying**: *citation discipline* (full repo-relative paths, line ranges, "never a bare filename") and *post-hoc grounding* (verify that cited paths exist in the tree). git-into-gsoc should apply exactly this to any narrative its skill asks an LLM to write.
- **Avoid**: generating architecture prose at all inside the tool; staleness without regeneration; per-page LLM cost.
- **Assessment**: DeepWiki is the clearest cautionary tale in this stream, confident, unsourced prose about undocumented code is actively harmful to maintainers. deepwiki-open's prompt discipline is the best available mitigation and is cheap to adopt as *policy*.

### 1.6 Context7: `upstash/context7`

- **Facts**: 63,390★, MIT (MCP server only; "The API backend, parsing engine, and crawling engine are private"), TypeScript, pushed 2026-10-20. https://github.com/upstash/context7
- **How it works (verified from README and docs/adding-libraries.mdx)**: MCP tools `resolve-library-id(query, libraryName)` and `query-docs(libraryId, query, language?)`; CLI `ctx7 library …`, `ctx7 docs …`; indexes **documentation files only** (`.md .mdx .markdown .rst .txt .ipynb`) and extracts code examples; "Raw source code files … are not indexed when documentation is present"; falls back to generating examples from source only when docs are scarce; libraries are community-submitted, refreshed "based on popularity", with a GitHub Action for push-triggered refresh; a "Report" button exists because "Context7 does not guarantee their accuracy, completeness, or security".
- **Relevance**: solves *usage* questions, not *contribution* questions. The useful lesson is scope discipline: index what is authoritative (docs), say so, and provide a report path.

### 1.7 CodeTour: `microsoft/codetour`

- **Facts**: 4,593★, MIT, TypeScript (VS Code extension), pushed 2026-05-05. https://github.com/microsoft/codetour
- **How it works (verified)**: tours are JSON files in `.tours/` (also `.vscode/tours`, `.github/tours`, `.tour`, `main.tour`). Schema seen in the project's own `intro.tour`: `{"$schema": "https://aka.ms/codetour-schema", "title", "description", "steps": [{"description"} | {"file", "line", "description"} | {"directory", …}]}`. Steps support Markdown, `[#2]` step links, `>> npm test` shell links, `command:` links; a tour can be pinned to `None`/branch/commit/tag ("ref") so it does not go stale; a title beginning `#1 - ` or `1 - ` is the **primary** tour shown to newcomers on first open; `nextTour` chains tours; `when` hides tours conditionally.
- **Worth copying**: the schema is tiny and the semantics ("primary tour for new developers", "pin to a commit so it never goes out of sync", "directory steps") map exactly onto a generated **reading plan** for a GSoC beginner. Emitting a `.tours/gsoc-orientation.tour` pinned to the current HEAD sha costs nothing extra.
- **Assessment**: low-risk, additive, VS Code-only consumer but the JSON is useful even as plain data.

### 1.8 Agentless: `OpenAutoCoder/Agentless`

- **Facts**: 2,130★, MIT, Python, pushed 2024-12-22. https://github.com/OpenAutoCoder/Agentless
- **How it works (verified)**: hierarchical localisation, files → classes/functions → edit lines. The file-level prompt is: "look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem … Please only provide the full path and return at most 5 files … ordered by most to least important". A second prompt asks for *irrelevant folders* to prune. `show_project_structure` prints only `.py` entries with 4-space indentation and `filter_out_test_files` drops `test*`. An alternative retriever (`fl/retrieve.py`) uses an embedding index with 512-token chunks.
- **Evidence from the field**: a 2025 survey reports Agentless at 40.67 % (SWE-bench Lite) / 50.8 % (Verified) and notes that for the Agentless-Mini scaffold "writing out full file paths, rather than a nested tree, was extremely important in ensuring the models do not hallucinate false file paths" (https://arxiv.org/pdf/2512.22256). BM25 lexical retrieval remains a strong, cheap baseline for issue→file ranking in that literature (https://arxiv.org/html/2512.07022v1).
- **Worth copying**: "full paths, at most N, ordered by importance"; the "irrelevant folders" pruning idea (for git-into-gsoc: exclude `docs/`, `examples/`, `vendor/`, `third_party/`, `node_modules/` from pointer candidates unless the issue is a docs issue); BM25-style keyword matching between issue text and file paths/names as a zero-API-cost ranker.

### 1.9 Shorter studies

- **Greptile** (proprietary). Official doc: builds a graph of "directories, files, functions, classes, variables" with edges for "function calls, imports, dependencies, variable usage", stored and queried during reviews; no mention of tree-sitter/embeddings/caching in the official page (https://www.greptile.com/docs/how-greptile-works/graph-based-codebase-context.md). Founder statements about tree-sitter + generated docstrings + embeddings are second-hand (https://www.aiwiki.ai/wiki/greptile), **unverified**. Lesson: callers/callees of a symbol are the context reviewers want; for a beginner, "who calls this function" is a one-line code-search query.
- **Sourcegraph Cody**. Official context doc lists keyword search (queries "automatically rewritten"), Sourcegraph Search (remote), and a code graph; context selection by `@`-mentions; token-limit tuning (https://sourcegraph.com/docs/cody/core-concepts/context). Cody Free/Pro were retired in 2025 with Amp named as the successor (https://sourcegraph.com/blog/changes-to-cody-free-pro-and-enterprise-starter-plans; dates from third parties, **unverified**); `github.com/sourcegraph/cody` returned 404 on 2026-10-21. Lesson: hybrid keyword-first retrieval is the pragmatic default; embeddings were de-emphasised even by a well-funded vendor.
- **Swimm** (proprietary): "auto-sync" keeps code snippets/paths in docs current and comments on PRs when docs drift (https://swimm.io/blog/how-swimms-github-app-works; https://docs.swimm.io/ide-integrations/vs-code/ide-plugins-vscode-keep-docs-up-to-date). Vendor claims only. Lesson: pin generated pointers to a commit sha and say so (CodeTour's `ref`).
- **GitHub Copilot on github.com**: Copilot Spaces (public preview) "searches the repository and retrieves only the most relevant content for your question" when a whole repo is attached (https://docs.github.com/en/copilot/how-tos/provide-context/use-copilot-spaces/create-copilot-spaces); the May-2024 Copilot Enterprise changelog suggested "Tell me about this repo" answered from owner/description/stars/timestamps (https://github.blog/changelog/2024-05-31-github-copilot-enterprise-copilot-knows-about-repositories-releases-commits-more-may-2024-updates/). A dedicated "explain this repository" feature: **unverified**.
- **Mutable.ai Auto Wiki**: YC lists the company as "Acquired" (https://ycombinator.com/companies/mutable-ai); `wiki.mutable.ai` did not resolve (DNS ENOTFOUND) on 2026-10-21. Treat as defunct.
- **Potpie** (`potpie-ai/potpie`, 5,746★, Apache-2.0, pushed 2026-10-19): "context graph" over code + PRs + issues + Linear/Jira/Confluence; CLI-first with `potpie resolve "<task>"` to "pull the context an agent should read before doing a task" (https://github.com/potpie-ai/potpie). Heavy (indexing service) but the *verb*, "resolve a task into the context to read", is the right framing for `pointers`.
- **code2prompt** (`mufeedvh/code2prompt`, 7,727★, MIT, Rust, pushed 2026-10-16): glob filtering, `.gitignore`, Handlebars templates, per-file token estimates, git diff/log; ships an agent skill with an optional "entity-map" feature (https://github.com/mufeedvh/code2prompt). Same genre as repomix.
- **first-contributions** (`firstcontributions/first-contributions`, 56,447★, MIT): the canonical fork→branch→PR tutorial; no code-reading guidance.
- **Onboarding bots in the wild**: `actions/first-interaction` (899★, MIT, pushed 2026-01-21) greets first-time issue/PR authors. matplotlib's `good-first-issue.yml` auto-comments on the `🌱 Good first issue` label: "**We do not assign issues** … please do not try to automate a solution using AI … If there is an open PR, please collaborate on the work by reviewing it rather than duplicating it"; `pr_welcome.yml` (plbstl/first-contribution) tells first-time PR authors to wait "a week or so" and to finish one PR before opening another; the PR template has an **"AI Disclosure"** section and "(no AI please)" on the summary. These are machine-readable policy signals the tool should surface verbatim.
- **GFI-Bot / RecGFI** (`osslab-pku/gfi-bot`, 57★, GPL-3.0): research bot (see §3).

---

## 2. How experienced maintainers say a codebase should be read

- **matklad, "ARCHITECTURE.md"** (https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html): for projects of ~10k-200k LOC add an `ARCHITECTURE.md` next to README/CONTRIBUTING containing a bird's-eye view (the problem solved), a **codemap** of coarse modules ("where's the thing that does X?" and "what does the thing I'm looking at do?"), **invariants** (especially absences: "model does not depend on views"), **boundaries**, and cross-cutting concerns. Keep it short; "Don't sync it with code"; **name important files/modules/types instead of linking lines** so symbol search finds them. rust-analyzer's `architecture.md` is the model, its headings are `Bird's Eye View`, `Entry Points`, `Code Map` (one subsection per crate), `Cross-Cutting Concerns` (verified from the file).
  → For git-into-gsoc: detect and surface `ARCHITECTURE.md`, `docs/dev/architecture*`, `docs/book/src/contributing/architecture.md`, `HACKING.md`, `DEVELOPING.md`, `docs/contributing/`; and structure the generated orientation sheet exactly like matklad's sections, but only with facts the API can prove (entry points, code map by directory, test command).
- **opensource.guide, "How to Contribute"** (https://opensource.guide/how-to-contribute/): read LICENSE ("If the project does not have a license, it is not open source"), README, CONTRIBUTING, CODE_OF_CONDUCT, then "the archives" (issues, PR threads, chat); health signals = latest commit date, number of contributors, issue response speed, PRs reviewed/merged recently; "If you want to make a substantial contribution, open an issue to ask before working on it"; claim issues by commenting; verify old issues; open small PRs early as drafts; "Review AI-assisted output carefully, since you remain responsible for what you submit".
- **The GSoC-specific reading order that follows from both**: README → CONTRIBUTING → ARCHITECTURE/dev docs → the *entry point* file → the *test file* for the area you will touch → one *recently merged small outsider PR* as a worked example → the files the issue points at. (§8 proposes generating exactly this list.)

---

## 3. What the research says about good-first-issues (and what to show a beginner)

- **Huang et al., ESEM 2021** (https://www.eecs.yorku.ca/~wangsong/papers/esem21b.pdf): 74,780 issues from 10 projects; 79 features; Random Forest median AUC 0.88. GFIs have **fewer modified files** and **less complex most-modified files** (Cliff's delta small), **more code snippets** in the body, shorter/clearer text with better readability; `is_enhancement` distinguishes GFIs; reporter role has *negligible* effect; semantics features (indicative words) contribute most.
- **Xiao et al., RecGFI, ICSE 2022** (https://hehao98.github.io/files/2022-recgfi.pdf): ground truth = issue resolved by a developer with ≤ k prior commits; 53,510 resolved issues / 100 projects; XGBoost; AUC up to 0.853. Features: content (title/body length, #urls, #code_snips, #imgs, readability, TF-IDF, label categories: task type / difficulty / status), background (reporter experience in project and GitHub-wide, project stars/contributors/commits, open issues, median close time, ratio of issues resolved by newcomers), dynamics (#comments, event counts, participant expertise, newcomer share among labelers). Interpretation: an issue is more likely a real GFI when the reporter has "just enough" experience, experienced developers participate, and the project has an active owner and recently onboarded newcomers. Cited statistics: "40.9 % of GFIs are not solved by newcomers and 31.2 % of newcomers fail to solve a GFI even after several attempts".
- **Hoshikawa et al., 2026** (https://arxiv.org/abs/2604.27532): 406,826 issues and 1,117 newcomer GFI PRs across 37 repos (2021-07 → 2025-06); GFI-label share "underwent a statistically significant decline beginning in January 2024"; newcomer engagement with GFIs steady (~27 %); **newcomer GFI PR merge rate fell from 61.9 % to 42.2 %**; description length and code size of the PR were *not* associated with merge outcome.
- **Hao et al., 2026** (https://arxiv.org/abs/2603.27136): first-issue *interaction* characteristics (moderately experienced reporter, moderate discussion, project-member participation) relate more strongly to long-term retention than intrinsic issue attributes.
- **Implications for the tool**: (a) show the empirical *fix-size norm* for the repo ("GFI fixes here touch a median of 2 files and always include a test") rather than generic advice; (b) prefer issues with project-member participation (already partly captured by availability checks) and flag issues with zero maintainer comments; (c) surface the project's explicit AI/assignment policy because the merge-rate collapse coincides with the AI era and maintainers are reacting with bots and PR-template disclosures; (d) do not present the beginner with a "fix it" prompt, present *reading* and *evidence*.

---

## 4. GitHub REST toolbox for cheap orientation (verified limits)

| Need | Endpoint | Cost | Verified limits / notes |
|---|---|---|---|
| Whole file tree | `GET /repos/{o}/{r}/git/trees/{ref}?recursive=1` | 1 | `tree[]` with `path, mode, type, sha, size`; limit **100,000 entries / 7 MB**, `truncated: true` beyond → fetch subtrees non-recursively (https://docs.github.com/en/rest/git/trees). matplotlib: 4,818 entries, not truncated. Cache keyed by the resolved HEAD sha. |
| Root/dir listing | `GET /repos/{o}/{r}/contents/{path}` | 1 | ≤ **1,000 files per directory**; files ≤ 1 MB full, 1-100 MB raw/object media type only, > 100 MB unsupported; `Accept: application/vnd.github.raw+json` (https://docs.github.com/en/rest/repos/contents). |
| README | `GET /repos/{o}/{r}/readme[/{dir}]` | 1 | Returns the *preferred* README; per-directory variant exists. |
| Languages | `GET /repos/{o}/{r}/languages` | 1 | Bytes per language (aider: Python 1.33 MB, "Tree-sitter Query" 64 KB …). |
| Community files | `GET /repos/{o}/{r}/community/profile` | 1 | `health_percentage`, `files.{code_of_conduct, contributing, issue_template, pull_request_template, license, readme}`; not for forks (https://docs.github.com/en/rest/metrics/community). Already used by the tool. |
| Real test command | `GET …/contents/.github/workflows` + raw of 1-2 workflow files | 2-3 | matplotlib `tests.yml` line 340: `pytest -rfEsXR -n auto \`, parse `run:` blocks for known runners. |
| Active maintainers | `GET /repos/{o}/{r}/commits?since=<90d>&per_page=100` | 1 | matplotlib 90 d: timhoffm 38, tacaswell 15, QuLogic 10, ayshih 8 …; drop bots (`[bot]`, known list). `stats/contributors` returned 200 for aider; docs note it can return 202 while computing (**not re-verified here**). |
| Who owns a path | `CODEOWNERS` in `.github/`, root or `docs/` (first found wins) | ≤ 3 | gitignore-style patterns, **last matching pattern wins**, < 3 MB (https://docs.github.com/…/about-code-owners). airflow example: `/airflow-core/src/airflow/cli/ @bugraoz93 @potiuk @dheerajturaga @henry3260`. |
| CLA / DCO | `GET /repos/{o}/{r}/commits/{sha}/check-runs` and `/status` on a recent merged PR head | 2 | Observed names: check-run `cla/google` + `license-check` (tensorflow), status context `EasyCLA` (kubernetes), check-run `DCO` (runc), `validate-dco / run` (moby); containerd's sampled commit showed only `Check Signed Tag`, airflow none. Also grep CONTRIBUTING for `sign-off|Signed-off-by|Developer Certificate|DCO` (moby 2 hits, runc 4). |
| Which PR fixed an issue | `GET /repos/{o}/{r}/issues/{n}/timeline?per_page=100` | 1 | Event types seen on matplotlib #9970: closed 2, commented 17, cross-referenced 12, labeled 6, mentioned 1, milestoned 1, referenced 7, renamed 1, reopened 1, subscribed 1, unlabeled 3. `cross-referenced.source.issue.{number, repository.full_name, pull_request.merged_at}`; `closed.{commit_id, state_reason, actor}`. **Filter on `repository.full_name`**, #9970 was cross-referenced by merged PRs in `sherpa/sherpa` and `open-atmos/PySDM`. |
| What the fix touched | `GET /repos/{o}/{r}/pulls/{n}/files?per_page=100` | 1 | ≤ 3,000 files; `filename, status, additions, deletions, changes, patch?, previous_filename?` (https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files). |
| Merged PRs linked to issues | `search/issues?q=repo:o/r is:pr is:merged linked:issue` | 1 (search) | matplotlib: 2,514 results. Useful when issues are unlabeled. |
| Where is this symbol | `GET /search/code?q="ident"+repo:o/r` (+ `Accept: application/vnd.github.text-match+json`) | 1 (code-search bucket) | **Auth required, 10 req/min**, default branch only, files < 384 KB, repos < 500,000 files, repo must have had activity in the last year, archived excluded, at least one term (except `filename:`), ≤ 2 fragments/file, qualifiers `in:file,path user: org: repo: path: language: size: filename: extension: fork:` (https://docs.github.com/en/search-github/searching-on-github/searching-code). `symbol:` is UI-only code search; **no REST symbol endpoint found**. |
| Past commits by keyword | `GET /search/commits?q=repo:o/r+keyword` | 1 (search) | Works (found aider's "Removed all the G nodes except the top 10 based on their PageRank" commit). Partial substitute for `git log -S`; no true pickaxe via API. |
| Closing semantics | docs | none | "When you merge a linked pull request into the default branch of a repository, its linked issue is automatically closed"; keywords `close/closes/closed/fix/fixes/fixed/resolve/resolves/resolved`, cross-repo `owner/repo#n` (https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue). This is why `|merged_at − closed_at| ≤ 1-5 s` identifies the closing PR. |
| Search budget | none | none | 30 req/min authenticated; 256-char query, ≤ 5 `AND/OR/NOT`; semantic/hybrid `search_type` needs auth and is 10/min (https://docs.github.com/en/rest/search/search). |

Gotcha for anyone scripting with `gh`: `gh api search/issues -f q=…` sends a **POST** and GitHub answers 404; use `-X GET`. (git-into-gsoc uses httpx GET so it is unaffected.)

---

## 5. Prototype results

### 5.1 "What do good-first-issue fixes touch here?": matplotlib/matplotlib (16 calls)

1. `search/issues?q=repo:matplotlib/matplotlib is:issue is:closed label:"Good first issue"` (sorted by updated, 8 results; `state_reason` completed/not_planned).
2. 6 timelines → 23 cross-referenced PRs; after filtering `repository.full_name == matplotlib/matplotlib` and `merged_at != null`, and comparing to the issue's `closed_at`:

| Issue | closed_at | Same-repo merged PR | merged_at | Δ |
|---|---|---|---|---|
| #9970 | 2026-07-22T03:44:12Z | #32069 | 2026-07-22T03:44:11Z | 1 s |
| #2488 | 2026-02-04T22:28:42Z | #30746 | 2026-02-04T22:28:41Z | 1 s |
| #18985 | 2025-12-08T17:10:44Z | #30052 | 2025-12-08T17:10:43Z | 1 s |
| #13919 | 2025-06-24T06:24:34Z | #29481 | 2025-06-24T06:24:33Z | 1 s |
| #4822 | 2026-04-11T07:03:49Z | #31183 | 2026-03-27T18:27:38Z | 15 d (manual close) |
| #13044 | 2026-04-10T19:37:50Z | #29199 | 2025-06-10T20:53:00Z | 10 mo (weak) |

   Heuristic: Δ ≤ 5 s ⇒ "closing PR" (high confidence); otherwise the most recent same-repo merged PR before `closed_at` ⇒ "likely fix" (low confidence); `closed.commit_id != null` ⇒ fixed by a direct commit.
3. 5 × `pulls/{n}/files`:

| PR | files | +/− | paths |
|---|---|---|---|
| 32069 | 2 | +25/−1 | `lib/matplotlib/axes/_base.py`, `lib/matplotlib/tests/test_axes.py` |
| 30746 | 2 | +257/−0 | `lib/matplotlib/backends/backend_pdf.py`, `lib/matplotlib/tests/test_backend_pdf.py` |
| 30052 | 2 | +19/−2 | `lib/matplotlib/axes/_base.py`, `lib/matplotlib/tests/test_axes.py` |
| 29481 | 7 | +127/−7 | `doc/users/next_whats_new/*.rst`, `lib/matplotlib/{__init__,axis,rcsetup}.py`, `rcsetup.pyi`, `mpl-data/matplotlibrc`, `tests/test_axis.py` |
| 31183 | 4 | +247/−10 | `doc/release/next_whats_new/*.rst`, `font_manager.py`, `font_manager.pyi`, `tests/test_font_manager.py` |

   Aggregate a beginner can act on: **median 2 files; 5/5 PRs modify `lib/matplotlib/tests/`; 2/5 add a `next_whats_new` release note; 2/5 update a `.pyi` stub alongside the `.py`.** That is the project's unwritten checklist, derived from evidence, in 11 calls (cacheable for a week).
4. Orientation facts from 4 more calls: tree 4,818 entries → `lib` 3,038 files, `galleries` 665, `doc` 559, `extern` 191, `.github` 34, `src` 31 (C extensions), `tools` 17, `ci` 16, `.devcontainer` present; `tests.yml` → `pytest -rfEsXR -n auto`; 90-day committers: timhoffm 38, tacaswell 15, QuLogic 10, ayshih 8, maaz7409 8, iccir 6; policy bots as in §1.9.

### 5.2 Issue → code pointers: IBM/import-tracker #55 (3 calls)

`pointers.py` (stdlib regexes; weights: blob-URL path ×5, stack-trace frame ×3, path-like token ×1, back-ticked identifier ×2, snake/camel identifier ≥ 8 chars ×1; path resolution exact → suffix → basename against the recursive tree) produced:

- `…/site-packages/import_tracker/__main__.py` (weight 12) → **`import_tracker/__main__.py`** via suffix match, the right file; stack-trace lines 755/661/429/468 give the functions (`main`, `get_all_new_modules`, `_set_ending_modules`).
- Noise: `runpy.py`, `distributed_c10d.py` (not in tree → dropped automatically); single-letter CLI flags (`m`, `n`, `i`, `s`) leaked through the back-tick rule → add a min-length of 3 and strip `-x` flags.
- One code-search call for `"import_tracker" repo:IBM/import-tracker` → 22 hits, top files `import_tracker/import_tracker.py`, `__init__.py`, `__main__.py`, `constants.py`, `setup_tools.py`.

Conclusion: path/stack-trace extraction plus tree matching is high-precision at zero API cost; identifiers need a stop-list and the "≥ 8 chars snake/camel" rule from aider; code search should be capped at 2-3 calls per run because of the 10/min bucket.

---

## 6. Answers to the four key questions

**(1) Best cheap "repo orientation" output for a beginner.** A one-screen sheet with these sections, each line carrying the path or URL that proves it (matklad's structure, DeepWiki's citation rule, aider's special-files list):

- *What it is*: description, language bytes (top 3), licence, stars/forks, default branch, HEAD sha (so the sheet can say "as of commit …").
- *Code map*: top-level directories with file counts and a purpose guess from a small name dictionary (`src|lib|pkg|internal|core` → source; `tests|test|spec|__tests__|e2e` → tests; `docs|doc|site|website` → docs; `examples|samples|galleries|demo` → examples; `scripts|tools|bin|ci|.github` → tooling; `extern|vendor|third_party|node_modules` → vendored; `benchmarks|perf` → perf) and dominant extension per directory, purpose *guesses* are labelled as such.
- *Entry points*: `pyproject [project.scripts]`, `setup.py entry_points`, `package.json bin/main`, `src/main.rs`/`src/bin/*`, `cmd/*/main.go`, `__main__.py`, `cli.py`, `Main.java`; plus `ARCHITECTURE.md`-type docs if present.
- *How to run tests*: the `run:` line(s) from CI workflows that match a runner (`pytest|tox|nox|npm test|pnpm test|yarn test|cargo test|go test|make test|mvn test|gradle test|ctest|meson test|bundle exec rspec`), then `Makefile`/`justfile`/`noxfile.py`/`tox.ini`/`package.json scripts.test` as secondary evidence; dev container presence.
- *Who merges*: top committers (90 days, bots removed), CODEOWNERS for the most-touched directories, and recent issue-closers' `author_association`.
- *Rules*: DCO/CLA signature (check-run names + CONTRIBUTING grep), conventional-commit ratio over the last 30 commit messages (`^(feat|fix|docs|chore|refactor|test|ci|build|perf|style)(\(.+\))?!?:`) and presence of `commitlint`/`release-please`/`.cz.toml`, `.pre-commit-config.yaml`, PR-template checklist items, and any explicit **AI-use/assignment policy** text found in CONTRIBUTING, PR template, or label-triggered bot workflows.
- *Where to talk*: channels (already extracted from CONTRIBUTING).
- *Fix norms*: from §5.1, median files, test-touch rate, docs/changelog-touch rate for recent GFI fixes.

Cost ≈ 12-16 calls, ~24 h cache keyed by HEAD sha; output ≤ ~80 rich lines / ≤ 4 k tokens JSON.

**(2) Code pointers for an issue.** Pipeline (≈ 4-8 calls): issue + tree (cached) → extract paths/stack frames/blob URLs/identifiers → resolve against tree → ≤ 3 code-search calls for the top identifiers (skip when a path already resolved) → "similar past issues": `search/issues` with the same beginner label (or the issue's other labels) `is:closed`, top 5 → timelines → closing PRs by the Δ-seconds rule → `pulls/{n}/files` → files/directories histogram → output "files likely involved (with confidence and reason)", "3 similar closed issues and the PRs that fixed them (title, files, size, days-to-merge)", "this repo's fix norm". Never output narrative about *how* to fix.

**(3) Local clone / tree-sitter mode.** Feasible but not now. Costs: `tree-sitter-language-pack` 1.22.1 wheels are 2.16-2.47 MB (MIT, `tree-sitter>=0.23`, Python ≥ 3.10), plus per-language `tags.scm` queries (aider's are Apache-2.0; repomix reuses them with credit); a shallow sparse clone (gitingest recipe) is seconds for most repos but minutes for monorepos. Benefits for a *beginner* are marginal: the API-only pointers already locate files; GitHub code search locates symbols; and the one thing local parsing adds, a ranked symbol map like aider's, serves an editing LLM more than a reading human. Recommendation: ship API-first; add an optional `git-into-gsoc[local]` extra later that (a) uses `universal-ctags` if on `PATH`, else tree-sitter-language-pack, (b) only to produce a *skeleton* (defs with line numbers) for the ≤ 10 files the pointers already selected. For Python repos, a zero-dependency skeleton via `ast` on raw files fetched with the contents API covers most GSoC Python orgs today.

**(4) What not to copy.** Whole-repo packing (repomix/gitingest/code2prompt) → token bloat; LLM-written wikis (DeepWiki) → confident errors and maintainer backlash; nested-tree rendering → hallucinated paths (Agentless); heavy dependency stacks and fragile disk caches (aider's SQLite workarounds); returning the entire doc as a search fallback (GitMCP); hard-coded label strings (`🌱 Good first issue`); unfiltered cross-repo references; unbounded code-search use (10/min); embeddings infrastructure (Cody de-emphasised it; deepwiki-open requires it), keyword + path heuristics are enough at this scale.

---

## 7. Synthesis

### Brilliant ideas worth adapting
- aider: identifier weighting (snake/camel ≥ 8 chars ×10, `_`-prefixed ×0.1, defined-everywhere ×0.1) and "path components ∩ mentioned identifiers" boosts; always-included special files; a hard token/line budget with ±15 % tolerance.
- Agentless: "full paths, at most 5, ordered by importance"; pruning irrelevant folders first.
- deepwiki-open: `Sources: [path:lines]()` on every claim; post-hoc grounding of citations against the tree.
- CodeTour: primary tour pinned to a commit; directory steps; `>> command` steps for "run the tests".
- matklad: Bird's-eye → Entry points → Code map → Cross-cutting; name files, don't link lines.
- RecGFI/Huang: the measurable GFI traits (few files, simple files, code snippets, member participation) → surface them as evidence, not as a score alone.
- GitMCP: cache 404s briefly; defer optional calls when `x-ratelimit-remaining` is low; `llms.txt` → README chain.
- repomix: `--token-budget` exit code; generated-skill layout (`project-structure.md` with line counts, `tech-stacks.md`); treat remote config as untrusted.

### Proven patterns
- API-only repo introspection works (GitMCP in production; our 16-call prototype).
- Timeline cross-references + `merged_at ≈ closed_at` recover closing PRs without GraphQL.
- `pulls/{n}/files` histograms give an evidence-based "what a fix looks like here".
- CI `run:` lines are the most reliable test-command source (aider's special-files list includes workflows for the same reason).

### Pitfalls to avoid
- Prose generation inside the tool; stale generated artefacts without a sha; dumping file contents; hard-coded labels; cross-repo references; exceeding the 10/min code-search bucket; treating `author_association` or commit counts as "maintainer" without bot filtering; trusting `README` alone (GitMCP's weakest spot); assuming `stats/*` endpoints are synchronous (202 behaviour, **unverified here**).

---

## 8. Feature proposals for git-into-gsoc

Effort: S ≤ 1 day, M 2-4 days, L > 1 week. All proposals respect: REST-only, disk cache (ETag, stale-if-error), no cloning by default, no fabricated content, no "write the fix for me".

1. **`orient OWNER/REPO` + MCP `gsoc_orient_repo`**, M. The orientation sheet of §6(1). New module `github/orient.py` (pure helpers: directory purpose dictionary, entry-point detection, CI `run:` parser, conventional-commit ratio, DCO/CLA detectors, policy-text extractor) + 12-16 calls in `GitHubClient.orient()` (tree, languages, readme, contributing, workflows dir + ≤ 2 files, commits since 90 d, CODEOWNERS probe in 3 locations, PR template, check-runs on one recent merged PR head). Cache tree/CODEOWNERS/workflows by HEAD sha (24 h+). Evidence: §1.1 special files, §2 matklad, §4 limits, §5.1 numbers.
2. **`pointers OWNER/REPO#N` + MCP `gsoc_issue_pointers`**, M. Pipeline of §6(2), 4-8 calls; regex extraction as in `pointers.py` with the fixes noted (min length 3, flag stripping, aider's identifier rule, stop-list of language/vendor names); confidence labels (`exact path`, `stack trace`, `suffix match`, `code search`, `similar fix`); hard cap of 3 code-search calls and a visible "code-search budget: 10/min" note. Output must contain only paths, line numbers, titles and numbers, never a fix suggestion. Evidence: §1.8 Agentless, §5.2.
3. **`fix-patterns OWNER/REPO [--label …]` (also folded into `repo` output as a one-line "fix norm")**, M. §5.1 pipeline: 1 search + ≤ 6 timelines + ≤ 6 `pulls/files`; Δ-seconds closing-PR rule; filter same-repo; report median files, test-touch rate, docs/changelog-touch rate, median days from PR open to merge, author associations of fixers (how many were first-timers). Cache 7 days per repo+label. Reuse `pick_beginner_label` so `🌱 Good first issue` works; fall back to `is:pr is:merged linked:issue` sampling when the label has no closed issues. Evidence: §3 research, §5.1 table.
4. **`reading-plan OWNER/REPO [#N] [--codetour]`**, S. Deterministic ordered list: README → CONTRIBUTING → architecture/dev docs (if found) → entry point(s) → test file(s) for the directory the issue points at → one recently merged ≤ 3-file outsider PR as a worked example (from the 60 closed PRs `repo` already fetches, +1 `pulls/files` call) → issue pointers. With `--codetour`, write `.tours/gsoc-orientation.tour` (`$schema`, title `#1 - GSoC orientation`, `ref` = HEAD sha, directory steps + file steps with `line` where known, a `>> <test command>` step). Evidence: §1.7, §2.
5. **Output contract: "facts and paths only"**, S (policy + tests). The skill and the MCP tool descriptions state that orientation/pointer output contains no architectural narrative; any narrative the LLM writes must cite repo-relative paths that exist in the fetched tree (ship a `validate_citations(text, tree)` helper the skill can call via MCP). Evidence: §1.5 DeepWiki backlash, deepwiki-open prompt rules.
6. **MCP resources + prompts**, S. Expose `repo://{owner}/{repo}/orientation`, `repo://{owner}/{repo}/fix-patterns`, `issue://{owner}/{repo}/{n}/pointers` as MCP *resources* (cached JSON) and add prompts `gsoc_first_pr_plan(repo, issue)` and `gsoc_before_you_comment(repo, issue)` that assemble orientation + availability + pointers + policy text. Addresses the brief's "MCP exposes only tools" weakness; cheap because the data already exists.
7. **Policy surfacing in `issue` and `repo`**, S. Grep CONTRIBUTING, PR template, and label-triggered workflow bodies for assignment policy ("we do not assign"), AI policy ("no AI", "AI Disclosure", "generative AI"), DCO/CLA, and "one PR at a time" rules; print verbatim quotes with file paths. Evidence: matplotlib workflows/template (§1.9), Hoshikawa 2026 merge-rate collapse (§3).
8. **Rate-limit-aware degradation**, S. Read `x-ratelimit-remaining` from responses (already available in `CachedHttpClient`) and skip *optional* calls (code search, check-runs, extra workflow files) when remaining < 50 or the code-search bucket < 3, with a one-line note in output. Evidence: GitMCP `respectRateLimits` (§1.4).
9. **Optional `[local]` extra (later)**, L. `tree-sitter-language-pack` or `ctags` skeletons for the ≤ 10 pointed files; shallow sparse clone recipe from gitingest; only if users ask after 1-4 ship. Evidence: §6(3) cost analysis.
10. **Digest hook (ties to another stream)**, S. The `fix-patterns` cache makes "new GFI opened in a tracked repo that touches directories where previous GFI fixes landed" a cheap, evidence-based alert line for any future digest feature.

---

## 9. Licensing and attribution notes

- aider (Apache-2.0): we adapt *heuristic weights* and the *special-files idea*, not code; the per-language `tags.scm` files are Apache-2.0 modifications of MIT/Apache tree-sitter grammar queries, if a `[local]` mode ever vendors them, keep the NOTICE/credits exactly as repomix does (`src/core/treeSitter/queries/README.md`).
- repomix (MIT), gitingest (MIT), code2prompt (MIT), CodeTour (MIT), deepwiki-open (MIT), Context7 MCP (MIT), Agentless (MIT), first-contributions (MIT), actions/first-interaction (MIT): ideas only; the CodeTour JSON schema is a public format (`https://aka.ms/codetour-schema`), writing files in that format needs no licence.
- GitMCP (Apache-2.0), Potpie (Apache-2.0): ideas only.
- GFI-Bot (GPL-3.0): do **not** copy code; the RecGFI/Huang feature definitions are from the papers (academic use of ideas is fine; cite the papers in docs).
- DeepWiki, Greptile, Swimm, Copilot, Context7 backend: proprietary; nothing to copy beyond publicly documented behaviour.
- Papers: cite Huang et al. (ESEM 2021, DOI 10.1145/3475716.3475789), Xiao et al. (ICSE 2022, DOI 10.1145/3510003.3510196), Hoshikawa et al. (arXiv:2604.27532), Hao et al. (arXiv:2603.27136) in the beginner guide when the tool shows "fix norms".
