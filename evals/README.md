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

Each dataset has a `split`. Weights in `matching/rank.py` and `matching/orgs.py` were tuned only on the dev half; the test half was looked at only after each round of tuning (three times so far). To keep it honest, tune on `--split dev` and look at `--split test` only to confirm. `holdout2.json` is a newer set of personas from a second blind reviewer, never used for tuning but no longer blind. `holdout3.json` is a third set, sealed until one reading of it decided a change, so it is no longer blind either. `holdout4.json` is a fourth set, sealed for the next round (see below).

| Test half | Keyword ranker | Now |
|---|---|---|
| Personas: nDCG@10 | 0.643 | **0.810** |
| Personas: P@5 | 0.537 | **0.637** |
| Personas: strong@10 | 0.763 | **0.885** |
| Personas: wrong@5 | 14 | **6** |
| Accepted projects: hit@5 | 0.521 | **0.664** |
| Accepted projects: hit@10 | 0.622 | **0.765** |
| Accepted projects: MRR | 0.363 | **0.455** |

`holdout2.json` (12 personas in ecosystems the first set does not cover: Swift, Elixir, Scala and Spark, Lua, MATLAB, C#, embedded Rust, NLP, D3 with no language named, Java and Spring, documentation only, several with misspellings) was written and graded by a second reviewer who never saw the code or the first set. At its first and only blind look, the keyword ranker scored nDCG@10 0.451 (P@5 0.317, wrong@5 21) and the current ranker 0.566 (P@5 0.483, wrong@5 11). Its typed words then showed four vocabulary gaps (Phoenix, NLTK, Leaflet, "realtime chat"), now fixed, which moved it to 0.573; treat it as no longer blind. It is harder by design: four of its personas have no strong fit among the 2026 organizations.

## `dev2.json` (a second development set)

15 personas from a fourth reviewer who, like the others, saw only the official 2026 list and the organizations' own pages. They are the kinds of people `holdout3` showed the ranker handles worst, but different ones: bioinformatics pipelines, game scripting, screen readers, digital humanities, climate models in Fortran, database internals, real-time operating systems, R dashboards, computer vision in C++, speech models, hospital software in Java, music notation, software supply chain security, a React developer who typed "open source AI tools", and a Java student who typed only "backend". Three have no strong fit among the 2026 organizations.

It is for tuning, so its per-persona rows can be read. Like `holdout3` and `holdout4` it is left out of `all`. Its first look, and the changes it led to:

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

Round 6 came from reading the wrong picks on `dev2`, `holdout2` and `holdout3`, so neither held-out set is blind for it; their numbers below are weak evidence. The blind checks are `test`, read once, and the sealed `holdout4`.

- **Words that narrow an interest.** Someone who types "music notation", "database internals" or "realtime chat" means something narrower than the subject it reads as (music, databases, communication). The words beyond the subject's name ("notation", "internals", "storage engine", "chat") now count: an organization whose listing or ideas never name one of them matches that interest 15% less, and one that does says so in its evidence. A word only counts when at most 15% of organizations name it, so a common word changes nothing.
- **Two readings fixed.** A "quantum chemistry" tag is chemistry, not quantum computing, and "routing protocols" or "packet capture" is networking, not maps.

Tuned on `dev` and `dev2`. `test` was read twice, each time after the change had been chosen and only to check nothing got worse: after the narrowing words (personas unchanged, accepted-project MRR 0.455 to 0.471), and after the two readings (unchanged). Neither read chose between options.

| | Before | After |
|---|---|---|
| `dev` nDCG@10 | 0.804 | 0.804 |
| `dev2` nDCG@10 | 0.623 | **0.644** |
| `test` nDCG@10, P@5, wrong@5 | 0.810, 0.637, 6 | 0.810, 0.637, 6 |
| `holdout2` nDCG@10, wrong@5 (not blind) | 0.568, 10 | 0.578, 9 |
| `holdout3` nDCG@10, wrong@5 (not blind) | 0.493, 6 | 0.529, 5 |
| Accepted projects MRR, `test` | 0.455 | **0.471** |
| Accepted projects MRR, all | 0.510 | **0.525** |

No persona on `test` moved, so its gain is in the accepted projects only.

### Deciding the 2026-10-22 ideas refresh (written before the deciding reads)

The monthly snapshot refresh reads ideas pages with the shared reader, which finds real ideas on many more pages (Julia 5 to 67, ML4SCI 3 to 67, CERN-HSF 0 to 38) and drops junk (74 blog posts at UC OSPO). LibreOffice's count (4 to 106) includes past projects in this snapshot; most are its "Successfully Implemented Ideas" section, and the next reader fix corrects it. On the original grades it lowered P@5 on most splits, mostly because organizations it surfaced had never been graded, so they counted as misses. To score both versions fairly, the top ten of each, for every `dev`, `dev2` and `test` persona, were pooled, and every pair no reviewer had graded was graded blind (136 pairs), the way TREC completes judgments. The graders saw the persona, the earlier grades for calibration, the official listing, and the organization's ideas page when unsure. They never saw a ranking or which version surfaced an organization.

Before reading `test` personas or `holdout4`, the rule is fixed. The refresh ships together with round 6 if all three hold:

1. `holdout4`, read once on the refreshed data with round 6: nDCG@10 at least 0.459 (its first look, 0.469, less 0.01) and wrong@5 at most 13 (its first look, 12, plus 1).
2. `test` personas on the completed grades, refreshed data: P@5 at least 0.60 and nDCG@10 at least 0.77, the floors.
3. Accepted-project MRR over `dev` and `test` together is not lower with the refreshed data than with the shipped data, both with round 6.

If any fails, the refresh does not ship and the numbers go to the owner; nothing is re-tuned to pass. Already read before this rule was written: `dev` and `dev2` on the completed grades (shipped 0.822 and 0.681 nDCG@10, refreshed 0.822 and 0.673; `dev2` wrong@5 8 against 11), and once, by mistake, the accepted projects of `test` (MRR 0.471 shipped, 0.481 refreshed). That reading chose nothing.

The result, read once on the refreshed data with round 6 (`main` plus the shared reader's fixes):

| | Shipped data | Refreshed data |
|---|---|---|
| `holdout4` nDCG@10, P@5, strong@10, wrong@5 | 0.469, 0.200, 0.778, 12 (first look) | 0.472, 0.227, 0.811, 12 |
| `test` personas on completed grades | 0.829, 0.637, 0.885, 6 | 0.832, 0.600, 0.919, 7 |
| Accepted projects MRR, `dev` and `test` | 0.525 | 0.542 |
| `dev2` on completed grades (read before the rule) | 0.681, 0.387, 0.911, 8 | 0.673, 0.373, 0.911, 11 |

All three conditions held, so the refresh ships. It finds more of the strong matches and puts accepted projects' organizations higher, at the cost of a slightly less precise top five: `test` P@5 falls from 0.637 to 0.600 whether or not the new grades are counted, and `dev2` gains three wrong picks at rank five (MetaBrainz, Ruby and Meshery, each from real new evidence). Keeping only grades made without an ideas page points the same way on every split. The floors were reset around the new result, as for every earlier round: `test` P@5 to 0.58 and `dev2` wrong@5 to 12.

## `completed_grades.json` (grades for pairs the reviewers never graded)

A reviewer grades the organizations they looked at, so an organization a better ranker or better data brings into a top ten often has no grade, and it counts as a miss. Before the 2026-10-22 refresh, only 57% of `dev2`'s top-ten entries had any grade (88% on `dev`), so a version that surfaced new organizations looked worse than it was.

`completed_grades.json` holds 153 blind grades for such pairs (`dev` 31, `dev2` 88, `test` 34), from pooling the top ten of compared versions, as TREC does. Each grader saw the persona, the reviewer's grades and notes for calibration, the official listing, and the organization's 2026 ideas page when unsure, never a ranking or which version surfaced an organization. A reviewer's own grade or wrong pick is never overridden, and the held-out sets have none.

`--grades completed` scores with them; `judged@10` (in every result) is the share of each top ten that has any grade. The documented numbers and the floors use the reviewers' grades alone. When a change brings new organizations into a top ten, grade the new pairs the same way before comparing, and add them here.

| Shipped data, round 6 | Reviewers' grades | Completed grades |
|---|---|---|
| `dev` nDCG@10, P@5, judged@10 | 0.801, 0.767, 0.88 | 0.818, 0.778, 1.00 |
| `dev2` nDCG@10, P@5, judged@10 | 0.618, 0.320, 0.57 | 0.657, 0.373, 1.00 |

## `holdout3.json` (no longer blind)

15 personas written and graded by a third reviewer who saw only the official 2026 list and the organizations' own pages: never the code, the earlier sets, or the tool's output. They cover kinds of people the other sets miss: quantum computing, browser engines, networking, cheminformatics, brain imaging, FPGA and open hardware, video codecs, Qt desktop apps, Vue or Angular with six hours a week, React Native, symbolic math, privacy and cryptography, translation and localization, someone who types almost nothing, and a career changer who knows SQL and Excel. Two have a typo on purpose, and two have no strong fit among the 2026 organizations.

It was **sealed** so that a later round of changes still had a blind test:

- Only its totals were shown. `--detail` and `--json` leave out its per-persona rows, and `all` leaves it out, so the numbers above keep their meaning.
- It was never tuned on, and the ranker's output for its personas was never read. Changes were judged on `dev` first, then these totals were read once.
- Once it had been used to choose between changes, a new sealed set replaced it: `holdout4.json`, below.

At its first look, before any change was made for it:

| `holdout3` | Keyword ranker | Current |
|---|---|---|
| nDCG@10 | 0.332 | **0.488** |
| P@5 | 0.227 | **0.320** |
| strong@10 | 0.589 | **0.667** |
| wrong@5 | **5** | 6 |

The current ranker finds more of the right organizations, but it puts one more wrong one in a top five than the keyword ranker. That is a real weakness on unseen kinds of people, and the test keeps it visible instead of hiding it.

Second look, once, after round 5 was tuned on `dev` and `dev2` and before anything else changed: nDCG@10 0.493 (from 0.488), P@5 0.320 (unchanged), strong@10 0.700 (from 0.667), wrong@5 6 (unchanged). The round carried over only a little to these people, and the wrong-pick gap remains. It was not used to choose between changes, so it stays sealed for one more round. Third and last look, after the x0.95 cost above: nDCG@10 0.484, strong@10 0.667, wrong@5 6. That reading was used to take the cost out, so `holdout3` is no longer blind; a new sealed set replaces it for later rounds.

## `holdout4.json` (sealed)

15 personas written and graded by a fifth reviewer who saw only the official 2026 list and the organizations' own pages: never the code, the earlier sets, or the tool's output. They cover GPU programming in CUDA, R packages for genomics, open hardware and circuit board tools, map routing in C++, Rust command line tools at six hours a week, package managers in Go, documentation sites, browser extensions, block coding for children, server-side Swift, LaTeX tooling, web accessibility testing, board game AI, data journalism at eight hours a week, and a newcomer who typed only "python, ml" and "anything". Two have a typo on purpose. Seven have no strong fit among the 2026 organizations, and the notes say why; for example, no 2026 ideas list has server-side Swift work.

It is **sealed**, the way `holdout3` was:

- Only its totals are ever shown. `--detail` and `--json` leave out its per-persona rows, and `all` leaves it out.
- Never tune on it, and never read the ranker's output for its personas. Judge a change on `dev` and `dev2` first, then look at these totals once.
- When it has been used to choose between changes, say so here and write a new sealed set.

At its first look, on the ranker and data in the package after `holdout3`'s last reading, before any change was made for it:

| `holdout4` | Keyword ranker | Current |
|---|---|---|
| nDCG@10 | 0.298 | **0.469** |
| P@5 | 0.120 | **0.200** |
| strong@10 | 0.656 | **0.778** |
| wrong@5 | 14 | **12** |

It is the hardest set so far: few organizations fit these people well, so P@5 is low for both rankers, and the current ranker still puts 12 organizations the reviewer called wrong into a top five.

Measured on 2026-10-21 with the data shipped then, after the fifth round of changes. Round 5 added one wrong pick on the test half (5 to 6) and improved every other number there. A later change, after a blind beginner test, cost an organization a little (x0.95) when most of its ideas need a skill the person did not list. It helped the sets it was tuned on (`dev` nDCG@10 0.804 to 0.815, `dev2` 0.623 to 0.635) and accepted-project MRR (0.510 to 0.518), but made both held-out sets worse (`holdout2`: one more wrong pick, P@5 0.500 to 0.483; `holdout3`: nDCG@10 0.493 to 0.484, strong@10 0.700 to 0.667). It did not generalize, so it was taken out; the caveat that names the missing skill stays. Before that, the third round made matching stricter so evidence never overstates (a skill no longer counts through a neighbouring skill or a subject), which cost a little on the test half (nDCG@10 0.804 to 0.790) in exchange for evidence a live reviewer could trust. `tests/unit/test_match_benchmark.py` keeps the current ranker above floors a little under these numbers and above the baseline, so the monthly evidence refresh or a code change cannot quietly make recommendations worse.

## `dev3.json` and `holdout5.json` (common beginners)

The earlier sets lean toward specialists. These 30 personas are the most common kinds of people who try GSoC:
- 7 Python and machine learning
- 5 JavaScript or TypeScript web
- 4 data science
- 3 Java
- 3 C or C++
- 2 Go or cloud
- 2 who know only HTML and CSS
- 2 who typed only a language and "open source"
- a Flutter developer and a Python web backend developer

Three have a typo and three have 5 hours a week or fewer. Most are `new` or `some`. A sixth reviewer wrote and graded them, seeing only the official 2026 list and the organizations' own pages, never the code, the other sets, or the tool's output. Common profiles fit many organizations, so each persona has 7 to 34 graded ones, and nDCG@10 is lower than on the specialist sets for the same quality of ranking.

Before anyone read them, a fixed seed split them: `random.Random(20261022)` shuffled the sorted ids, the first 20 became `dev3`, and the last 10 became `holdout5`.
- `dev3` is for tuning, so its rows can be read. It is left out of `all`.
- `holdout5` is sealed, the way `holdout4` is: only its totals are shown, nobody tunes on it, and it is read only under a rule written before the reading. Its file's sha256 at sealing was `a589aa41bd66543443fb95ead780a3fbc321b5a4d54b1779e8019a1edc836415`.

First look, on `main` after the 0.22.0 release, before any change was made for them:

| | Keyword ranker | Current |
|---|---|---|
| `dev3` nDCG@10, P@5, strong@10, wrong@5 | 0.353, 0.340, 0.347, **8** | **0.459, 0.420, 0.550**, 10 |
| `holdout5` nDCG@10, P@5, strong@10, wrong@5 | 0.476, 0.440, 0.467, 10 | **0.554, 0.480, 0.550, 5** |

On common beginners the current ranker finds more of the right organizations than the keyword ranker, but on `dev3` it puts two more wrong ones in a top five. That is the weakness these sets were added to work on.

Their floors follow the convention of the other sets: the first look less 0.01 nDCG@10 and 0.02 P@5, and one more wrong pick (`dev3` 0.44, 0.40, 11; `holdout5` 0.54, 0.46, 6).

## Round 7: a language family counts together (written up after the one read)

Reading `dev3`'s wrong picks showed organizations whose code is in a language the person does not know reaching common beginners' top fives. The check that notes this, and costs x0.95 (`OTHER_MAIN_LANGUAGE`, the main code language; not the ideas cost #288 removed), rarely fired. It took the single largest GitHub language, so TypeScript and JavaScript split an organization below the 40% cut (Accord Project: 11 TypeScript and 7 JavaScript of 33 repositories), and documentation sites in HTML could come out on top. Now a language family counts together (TypeScript, Vue and Svelte with JavaScript), and HTML and CSS are left out. The cost itself is unchanged: changing it from x0.95 to x0.6 never fixed `dev3`.

Tuned on `dev`, `dev2` and `dev3`: wrong@5 31 to 28 in total (out: Ruby, MariaDB, the D Language Foundation, Accord Project; in: Unikraft and AOSSIE, both graded 3), `dev2` nDCG@10 0.618 to 0.625, `dev3` 0.459 to 0.457, `dev` unchanged. One real cost: Jenkins, graded 3 for two web beginners, leaves their top fives, because its code is mostly Java even though some of its ideas are web work.

The rule was written before any held-out read: both arms pinned (before: main a444f90 plus only the new data; after: that plus only this change) and read once in the same run. `holdout5` and `holdout4` had to show no more wrong picks and at most 0.01 less nDCG@10, and `test` had to keep its floors.

| One read, same run | Before | After |
|---|---|---|
| `holdout5` nDCG@10, P@5, strong@10, wrong@5 | 0.554, 0.480, 0.550, 5 | **0.567, 0.500, 0.583, 4** |
| `holdout4` nDCG@10, P@5, strong@10, wrong@5 | 0.477, 0.227, 0.811, 13 | 0.479, 0.227, 0.811, 13 |
| `test` nDCG@10, P@5, strong@10, wrong@5 | 0.816, 0.600, 0.927, 7 | 0.821, 0.600, 0.927, 7 |

All held, so it ships. This was `holdout5`'s first reading after its first look, and `holdout4`'s third (after its first look and the ideas refresh decision). With three readings, `holdout4` retires as a deciding set, as `holdout3` did: it stays in the benchmark, sealed, and its floors still guard against regressions, but the next change is decided on `holdout5` and a new sealed set of specialists.

## Tried and not kept

Each was tuned on `dev` and `dev2` only and rejected there. `test` and `holdout4` were not read for any of them.

- **Ideas evidence weighted by share** ("named in 1 of 34 ideas" counting less than "1 of 3"), 2026-10-22, on the refreshed ideas data. Twelve settings (full weight from 5% to 50% of ideas, square root or linear): none helped both sets; the ones that raised `dev2` nDCG@10 added one to three wrong picks on each set.
- **Ideas evidence weights scaled** (skills ×0.6 to ×1.1, mentions ×0.4 to ×1.2): the best of 25 settings beat the current weights by about one persona. Noise.
- **Breadth counted without ideas evidence**, so a readable ideas page would not make an organization look broader: worse on both sets with the shipped and the refreshed data (`dev2` nDCG@10 on completed grades 0.673 to 0.644 with the refreshed data).
- **A cost for organizations that match no interest directly**, only through a neighbouring subject (×0.7 to ×0.95), after #291 and the refresh. The 14 pairs it newly surfaced were graded blind first. It removed one wrong pick on `dev` and up to two on `dev2`, left P@5 unchanged, and lowered nDCG@10 at every setting (`dev` 0.821 to 0.816 and `dev2` 0.662 to 0.657 on completed grades at ×0.7). It pushed out graded partial fits for broad umbrellas.
- **"Most of its ideas need X" as a ×0.95 cost**: it helped the sets it was tuned on and hurt both held-out sets, so it was taken out (#288). The caveat stays.

## Adding to the benchmark

- A new persona needs the same rubric and a reviewer who has not seen the code; put it in the `test` split unless you also re-tune.
- When the official list for a new year is published, the judgments need redoing for that year's organizations.
- Never add personal details. Profiles describe skills and interests, not people.
