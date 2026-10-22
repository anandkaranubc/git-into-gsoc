# Ranking benchmarks

These datasets measure how well `orgs` and `recommend` rank GSoC organizations for real kinds of contributors. They run offline against the organization data shipped in the package, so anyone gets the same numbers.

```bash
python scripts/eval_matching.py                 # both rankers, dev, test, and all
python scripts/eval_matching.py --split dev --ranker current --detail
python scripts/eval_matching.py --json
```

`baseline` is the keyword ranker used up to release 0.11; `current` is the ranker in `src/git_into_gsoc/matching/`.

## `personas.json`

34 contributor personas across ecosystems (Python data science, web, Android, C and kernels, Rust, Go and cloud, robotics, bioinformatics, astronomy, healthcare, compilers, graphics, music, GIS, climate, and more), experience levels (`new`, `some`, `experienced`), and weekly hours (5 to 30). Two are deliberately hard: one types `pyhton` and the vague interest `ai`, and one knows only HTML and CSS.

Each persona has graded judgments for the official GSoC 2026 organizations: 3 (strong fit: the work matches the interests, the main stack uses the person's skills, and it is realistic for their level), 2 (good), and 1 (partial). Anything not listed is 0. Each also lists up to eight `wrong_top5` organizations: ones a keyword matcher would likely surface (they share a language tag, for example) that should not be in the person's top five.

The judgments were made by a reviewer who never saw the ranking code, working from the official listings (tags, categories, tagline, description, ideas page link, 2026 project count) and, for uncertain cases, the organizations' 2026 ideas pages. `judge_notes` says how each persona was judged.

Metrics: **nDCG@10** (agreement between the top ten and the graded judgments, 1 is perfect; Järvelin and Kekäläinen, 2002), **P@5** (share of the top five graded 2 or 3), **strong@10** (share of grade-3 organizations found in the top ten), **wrong@5** (`wrong_top5` organizations in the top five, summed), and **empty** (personas with no results).

## `accepted_2026.json`

240 real GSoC 2026 accepted projects, sampled with at most two per organization (a fixed seed) from the [community archive](https://api.gsocorganizations.dev/organizations.json). For each, a writer who could not see the organization read the project's title and description and wrote the profile the contributor might have typed months earlier: one to four technologies and one to three interests in plain words, never the name of the organization, its product, or a library specific to it. The case keeps only the organization, project title, project link, and that profile; no contributor names.

The organization that accepted the project is the answer. Metrics: **hit@k** (it is in the top k) and **MRR** (mean reciprocal rank). Two cases name organizations missing from the 2026 list under the same name and are skipped.

This is a fair but strict test: other organizations may suit the same profile just as well, so absolute numbers understate quality, and differences between rankers are what matter.

## Dev and test halves

Each dataset has a `split`. Weights in `matching/rank.py` and `matching/orgs.py` were tuned only on the dev half; the test half was looked at only after each round of tuning (three times so far). To keep it honest, tune on `--split dev` and look at `--split test` only to confirm. `holdout2.json` is a newer set of personas from a second blind reviewer, never used for tuning but no longer blind. `holdout3.json` is a third set, sealed for the next round (see below).

| Test half | Keyword ranker | Now |
|---|---|---|
| Personas: nDCG@10 | 0.643 | **0.811** |
| Personas: P@5 | 0.537 | **0.637** |
| Personas: strong@10 | 0.763 | **0.885** |
| Personas: wrong@5 | 14 | **6** |
| Accepted projects: hit@5 | 0.521 | **0.655** |
| Accepted projects: hit@10 | 0.622 | **0.765** |
| Accepted projects: MRR | 0.363 | **0.463** |

`holdout2.json` (12 personas in ecosystems the first set does not cover: Swift, Elixir, Scala and Spark, Lua, MATLAB, C#, embedded Rust, NLP, D3 with no language named, Java and Spring, documentation only, several with misspellings) was written and graded by a second reviewer who never saw the code or the first set. At its first and only blind look, the keyword ranker scored nDCG@10 0.451 (P@5 0.317, wrong@5 21) and the current ranker 0.566 (P@5 0.483, wrong@5 11). Its typed words then showed four vocabulary gaps (Phoenix, NLTK, Leaflet, "realtime chat"), now fixed, which moved it to 0.573; treat it as no longer blind. It is harder by design: four of its personas have no strong fit among the 2026 organizations.

## `dev2.json` (a second development set)

15 personas from a fourth reviewer who, like the others, saw only the official 2026 list and the organizations' own pages. They are the kinds of people `holdout3` showed the ranker handles worst, but different ones: bioinformatics pipelines, game scripting, screen readers, digital humanities, climate models in Fortran, database internals, real-time operating systems, R dashboards, computer vision in C++, speech models, hospital software in Java, music notation, software supply chain security, a React developer who typed "open source AI tools", and a Java student who typed only "backend". Three have no strong fit among the 2026 organizations.

It is for tuning, so its per-persona rows can be read. Like `holdout3` it is left out of `all`. Its first look, and the changes it led to:

| `dev2` | Keyword ranker | First look | After round 5 |
|---|---|---|---|
| nDCG@10 | 0.347 | 0.550 | **0.623** |
| P@5 | 0.173 | 0.307 | **0.347** |
| strong@10 | 0.672 | 0.889 | **0.911** |
| wrong@5 | 14 | 9 | **8** |

Round 5 made general fixes it pointed to:

- **Tags with hyphens.** These are read both with and without the hyphen. "r-project" and "objective-c" are spellings only with it, so the R project did not count as using R.
- **Software supply chain security** is now its own subject under security. Before, an SBOM or signing interest matched any security organization as strongly as one that works on supply chains.
- **Phrases that name a common and a rare subject.** In "audio machine learning", the rare subject counts most. A match on machine learning alone now counts for less.
- **A small penalty when most of an organization's active code is in a language the person did not list.** It was already a caveat; now it is a small score penalty too.
- **New spellings:** "camera pipelines" and "archiving".

## `holdout3.json` (sealed)

15 personas written and graded by a third reviewer who saw only the official 2026 list and the organizations' own pages: never the code, the earlier sets, or the tool's output. They cover kinds of people the other sets miss: quantum computing, browser engines, networking, cheminformatics, brain imaging, FPGA and open hardware, video codecs, Qt desktop apps, Vue or Angular with six hours a week, React Native, symbolic math, privacy and cryptography, translation and localization, someone who types almost nothing, and a career changer who knows SQL and Excel. Two have a typo on purpose, and two have no strong fit among the 2026 organizations.

It is **sealed** so that a later round of changes still has a blind test:

- Only its totals are ever shown. `--detail` and `--json` leave out its per-persona rows, and `all` leaves it out, so the numbers above keep their meaning.
- Never tune on it, and never read the ranker's output for its personas. Judge a change on `dev` first, then look at these totals once.
- When it has been used to choose between changes, say so here and write a new sealed set.

At its first look, before any change was made for it:

| `holdout3` | Keyword ranker | Current |
|---|---|---|
| nDCG@10 | 0.332 | **0.488** |
| P@5 | 0.227 | **0.320** |
| strong@10 | 0.589 | **0.667** |
| wrong@5 | **5** | 6 |

The current ranker finds more of the right organizations, but it puts one more wrong one in a top five than the keyword ranker. That is a real weakness on unseen kinds of people, and the test keeps it visible instead of hiding it.

Second look, once, after round 5 was tuned on `dev` and `dev2` and before anything else changed: nDCG@10 0.493 (from 0.488), P@5 0.320 (unchanged), strong@10 0.700 (from 0.667), wrong@5 6 (unchanged). The round carried over only a little to these people, and the wrong-pick gap remains. It was not used to choose between changes, so it stays sealed for one more round.

Measured on 2026-10-21 with the data shipped then, after the fifth round of changes. Round 5 added one wrong pick on the test half (5 to 6) and improved every other number there. A later change, after a blind beginner test, costs an organization a little (x0.95) when most of its ideas need a skill the person did not list: on `dev` nDCG@10 0.804 to 0.815, on `dev2` 0.623 to 0.635, accepted-project MRR 0.510 to 0.518 over all cases, but `holdout2` one more wrong pick (10 to 11) and P@5 0.500 to 0.483. Before that, the third round made matching stricter so evidence never overstates (a skill no longer counts through a neighbouring skill or a subject), which cost a little on the test half (nDCG@10 0.804 to 0.790) in exchange for evidence a live reviewer could trust. `tests/unit/test_match_benchmark.py` keeps the current ranker above floors a little under these numbers and above the baseline, so the monthly evidence refresh or a code change cannot quietly make recommendations worse.

## Adding to the benchmark

- A new persona needs the same rubric and a reviewer who has not seen the code; put it in the `test` split unless you also re-tune.
- When the official list for a new year is published, the judgments need redoing for that year's organizations.
- Never add personal details. Profiles describe skills and interests, not people.
