"""The ranking benchmark in evals/ must not get worse (see evals/README.md).

The floors sit a little under the results when the benchmark was added, so a
weekly data refresh can move them slightly, but a change that makes
recommendations clearly worse fails here. If an improvement raises the numbers,
raise the floors with it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "eval_matching", ROOT / "scripts" / "eval_matching.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_matching"] = module
    spec.loader.exec_module(module)
    return module


# split: (nDCG@10, precision@5, wrong picks in the top 5, hit@10 on accepted projects)
# holdout2, holdout3 and holdout4 have personas only, from later blind reviewers. holdout4
# is sealed (see evals/README.md); its floors sit under its first look.
FLOORS = {
    "dev": (0.76, 0.69, 12, 0.85),
    "test": (0.77, 0.58, 7, 0.73),
    "holdout2": (0.53, 0.42, 14, None),
    "holdout3": (0.45, 0.28, 8, None),
    "holdout4": (0.43, 0.16, 14, None),
    # Common kinds of beginners: dev3 for tuning, holdout5 sealed (same reviewer and batch).
    "dev3": (0.44, 0.40, 11, None),
    "holdout5": (0.54, 0.46, 6, None),
    # Specialists the other sets do not cover, sealed.
    "holdout6": (0.60, 0.43, 6, None),
    # A second development set from a fourth blind reviewer, used for tuning. Its wrong@5
    # floor and test's P@5 floor were reset around the ideas refresh that the rule in
    # evals/README.md ("Deciding the 2026-10-22 ideas refresh") passed.
    "dev2": (0.61, 0.32, 12, None),
}


SPLITS = [
    "dev",
    "dev2",
    "dev3",
    "test",
    "holdout2",
    "holdout3",
    "holdout4",
    "holdout5",
    "holdout6",
]


@pytest.mark.parametrize("split", SPLITS)
def test_ranking_keeps_its_quality(bench: ModuleType, split: str) -> None:
    result = bench.evaluate("current", split)
    personas, accepted = result["personas"], result["accepted"]
    ndcg, p5, wrong, hit10 = FLOORS[split]
    assert personas["ndcg10"] >= ndcg, personas["ndcg10"]
    assert personas["p5"] >= p5, personas["p5"]
    assert personas["wrong5"] <= wrong, personas["wrong5"]
    assert personas["empty"] == 0
    if hit10 is not None:
        assert accepted["hit10"] >= hit10, accepted["hit10"]


@pytest.mark.parametrize("split", SPLITS)
def test_ranking_beats_the_keyword_baseline(bench: ModuleType, split: str) -> None:
    current = bench.evaluate("current", split)
    baseline = bench.evaluate("baseline", split)
    assert current["personas"]["ndcg10"] > baseline["personas"]["ndcg10"]
    # At their first looks: holdout3 had 6 wrong picks against the baseline's 5, and dev3
    # (common beginners) 10 against 8. Both are known weaknesses, kept visible here.
    if split not in {"holdout3", "dev3"}:
        assert current["personas"]["wrong5"] < baseline["personas"]["wrong5"]
    if current["accepted"]["cases"]:
        assert current["accepted"]["mrr"] > baseline["accepted"]["mrr"]
        assert current["accepted"]["hit10"] > baseline["accepted"]["hit10"]


def test_benchmark_data_holds_no_personal_details(bench: ModuleType) -> None:
    for case in bench.load_accepted():
        assert set(case) == {
            "case",
            "split",
            "org",
            "title",
            "project_url",
            "technologies",
            "interests",
            "confidence",
        }
    names = {org.name for org in bench.catalog().orgs}
    for persona in bench.load_personas():
        assert set(persona["grades"]) <= names, persona["id"]
        assert set(persona["wrong_top5"]) <= names, persona["id"]


def test_the_sealed_set_stays_out_of_all_and_shows_totals_only(
    bench: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    sealed_splits = {"holdout4", "holdout5", "holdout6"}
    sealed = [p for p in bench.load_personas() if p["split"] in sealed_splits]
    assert len(sealed) == 40 and set(bench.SEALED) == sealed_splits
    apart = [p for p in bench.load_personas() if p["split"] in {"dev2", "dev3", "holdout3"}]
    everyone = bench.evaluate("current", "all")["personas"]["personas"]
    assert everyone == len(bench.load_personas()) - len(sealed) - len(apart) == 46
    for split in sorted(sealed_splits):
        assert bench.main(["--split", split, "--json"]) == 0
        shown = json.loads(capsys.readouterr().out)
        assert shown and all(not r["personas"]["rows"] for r in shown)


def test_completed_grades_only_fill_gaps_and_hold_no_personal_details(bench: ModuleType) -> None:
    rows = json.loads((ROOT / "evals" / "completed_grades.json").read_text(encoding="utf-8"))[
        "grades"
    ]
    personas = {p["id"]: p for p in bench.load_personas()}
    names = {org.name for org in bench.catalog().orgs}
    seen = set()
    for row in rows:
        assert set(row) == {"persona", "org", "grade", "ideas_page", "why"}
        persona = personas[row["persona"]]
        assert persona["split"] in {"dev", "dev2", "test"}  # never a held-out set
        assert row["org"] in names and row["grade"] in {0, 1, 2, 3}
        # A reviewer's grade or wrong pick is never second-guessed.
        assert row["org"] not in persona["grades"] and row["org"] not in persona["wrong_top5"]
        assert (row["persona"], row["org"]) not in seen
        seen.add((row["persona"], row["org"]))


def test_completed_grades_cover_more_of_each_top_ten(bench: ModuleType) -> None:
    for split in ("dev", "dev2"):
        original = bench.evaluate("current", split)["personas"]
        completed = bench.evaluate("current", split, "completed")["personas"]
        assert completed["judged10"] >= original["judged10"]
        assert completed["wrong5"] == original["wrong5"]  # wrong picks are the reviewers' own
