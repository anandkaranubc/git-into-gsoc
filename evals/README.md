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

Each dataset has a `split`. Weights in `matching/rank.py` and `matching/orgs.py` were tuned only on the dev half; the test half was looked at only after each round of tuning (twice so far). To keep it honest, tune on `--split dev` and look at `--split test` only to confirm. `holdout2.json` is a newer set of personas from a second blind reviewer, never used for tuning but no longer blind. `holdout3.json` is a third set, sealed for the next round (see below).

| Test half | Keyword ranker | Now |
|---|---|---|
| Personas: nDCG@10 | 0.643 | **0.790** |
| Personas: P@5 | 0.537 | **0.625** |
| Personas: strong@10 | 0.763 | **0.857** |
| Personas: wrong@5 | 14 | **5** |
| Accepted projects: hit@5 | 0.521 | **0.647** |
| Accepted projects: hit@10 | 0.622 | **0.756** |
| Accepted projects: MRR | 0.363 | **0.450** |

`holdout2.json` (12 personas in ecosystems the first set does not cover: Swift, Elixir, Scala and Spark, Lua, MATLAB, C#, embedded Rust, NLP, D3 with no language named, Java and Spring, documentation only, several with misspellings) was written and graded by a second reviewer who never saw the code or the first set. At its first and only blind look, the keyword ranker scored nDCG@10 0.451 (P@5 0.317, wrong@5 21) and the current ranker 0.566 (P@5 0.483, wrong@5 11). Its typed words then showed four vocabulary gaps (Phoenix, NLTK, Leaflet, "realtime chat"), now fixed, which moved it to 0.573; treat it as no longer blind. It is harder by design: four of its personas have no strong fit among the 2026 organizations.

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

Measured on 2026-10-21 with the data shipped then, after the third round of changes. That round made matching stricter so evidence never overstates (a skill no longer counts through a neighbouring skill or a subject), which cost a little on the test half (nDCG@10 0.804 to 0.790) in exchange for evidence a live reviewer could trust. `tests/unit/test_match_benchmark.py` keeps the current ranker above floors a little under these numbers and above the baseline, so the monthly evidence refresh or a code change cannot quietly make recommendations worse.

## Adding to the benchmark

- A new persona needs the same rubric and a reviewer who has not seen the code; put it in the `test` split unless you also re-tune.
- When the official list for a new year is published, the judgments need redoing for that year's organizations.
- Never add personal details. Profiles describe skills and interests, not people.
