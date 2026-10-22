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
    "test": (0.77, 0.60, 7, 0.73),
    "holdout2": (0.53, 0.42, 14, None),
    "holdout3": (0.45, 0.28, 8, None),
    "holdout4": (0.43, 0.16, 14, None),
    # A second development set from a fourth blind reviewer, used for tuning.
    "dev2": (0.59, 0.32, 10, None),
}


@pytest.mark.parametrize("split", ["dev", "dev2", "test", "holdout2", "holdout3", "holdout4"])
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


@pytest.mark.parametrize("split", ["dev", "dev2", "test", "holdout2", "holdout3", "holdout4"])
def test_ranking_beats_the_keyword_baseline(bench: ModuleType, split: str) -> None:
    current = bench.evaluate("current", split)
    baseline = bench.evaluate("baseline", split)
    assert current["personas"]["ndcg10"] > baseline["personas"]["ndcg10"]
    if split != "holdout3":  # at its first look, 6 wrong picks against the baseline's 5
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
    sealed = [p for p in bench.load_personas() if p["split"] == "holdout4"]
    assert len(sealed) == 15 and set(bench.SEALED) == {"holdout4"}
    apart = [p for p in bench.load_personas() if p["split"] in {"dev2", "holdout3"}]
    everyone = bench.evaluate("current", "all")["personas"]["personas"]
    assert everyone == len(bench.load_personas()) - len(sealed) - len(apart) == 46
    assert bench.main(["--split", "holdout4", "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown and all(not r["personas"]["rows"] for r in shown)
