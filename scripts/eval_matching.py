"""Measure how well organization ranking serves real contributor profiles.

Two datasets live in ``evals/`` (see evals/README.md):

* ``personas.json``: contributor personas across ecosystems and experience
  levels, each with graded judgments (3 strong, 2 good, 1 partial) made by a
  reviewer who never saw the ranking code, and a list of organizations that
  should not reach the top five.
* ``accepted_2026.json``: profiles written from real GSoC 2026 accepted
  projects without seeing the organization. The organization that accepted
  the project is the answer.

Everything runs offline against the embedded snapshot, so results are
repeatable. Each set has a dev half (used while tuning) and a test half (only
checked at the end).

``holdout2.json``, ``holdout3.json`` and ``holdout4.json`` are later persona sets
from other blind reviewers. ``holdout4`` is sealed: its per-persona rows are never
printed, and it must never be used for tuning. ``holdout3`` was sealed until a
reading of it decided a change, so it is no longer blind. ``dev2.json`` and
``dev3.json`` are more development sets for tuning; ``dev3`` holds common kinds of
beginners. ``holdout5.json`` is sealed too: common beginners from the same batch as
``dev3``, split off by a fixed seed before anyone read them. ``holdout6.json`` is sealed
as well: specialists the other sets do not cover. All of these are left
out of ``all`` so the numbers documented for the first 46 personas keep their meaning.

``completed_grades.json`` holds blind grades for pairs the reviewers never graded,
from pooling the top ten of compared versions (see evals/README.md). They count only
with ``--grades completed``; the documented numbers and the floors use the reviewers'
grades alone. ``judged@10`` says what share of each top ten has any grade at all.

Usage: python scripts/eval_matching.py [--split dev|dev2|dev3|test|holdout2|holdout3|holdout4|holdout5|holdout6|all] [--ranker both|current|baseline] [--grades original|completed] [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
sys.path.insert(0, str(ROOT / "src"))

from git_into_gsoc.gsoc.client import GSoCClient  # noqa: E402
from git_into_gsoc.gsoc.snapshot import load_official  # noqa: E402
from git_into_gsoc.matching.profile import build_profile  # noqa: E402
from git_into_gsoc.matching.rank import OrgIndex  # noqa: E402
from git_into_gsoc.matching.signals import load_signals  # noqa: E402
from git_into_gsoc.models import OrgSummary  # noqa: E402
from git_into_gsoc.scoring.org_match import score_org_match  # noqa: E402

Ranker = Callable[[dict[str, Any]], list[str]]


@dataclass
class Catalog:
    year: int
    orgs: list[OrgSummary]
    descriptions: dict[str, str]
    index: OrgIndex


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    client = GSoCClient()
    snapshot = load_official()
    year = int(snapshot["year"])
    orgs = [client._from_official(raw, year) for raw in snapshot["organizations"]]
    descriptions = dict(client._search_text)
    index = OrgIndex.build(
        orgs, descriptions=descriptions, signals=load_signals(), reference_year=year
    )
    return Catalog(year=year, orgs=orgs, descriptions=descriptions, index=index)


def current_ranker(profile: dict[str, Any]) -> list[str]:
    """The matching package's ranker, as `orgs` and `recommend` run it."""
    person = build_profile(
        technologies=profile.get("technologies"),
        interests=profile.get("interests"),
        experience=profile.get("experience"),
        hours_per_week=profile.get("hours_per_week"),
    )
    return [m.org.name for m in catalog().index.rank(person)]


def baseline_ranker(profile: dict[str, Any]) -> list[str]:
    """The keyword ranker used before the matching package (release 0.11)."""
    cat = catalog()
    scored = []
    for org in cat.orgs:
        result = score_org_match(
            org,
            technologies=profile.get("technologies"),
            topics=profile.get("interests"),
            reference_year=cat.year,
            search_text=cat.descriptions.get(org.name, ""),
        )
        if result.relevant:
            scored.append(
                (-result.score, -org.num_projects_latest, -len(org.years_active), org.name)
            )
    return [name for *_, name in sorted(scored)]


RANKERS: dict[str, Ranker] = {"current": current_ranker, "baseline": baseline_ranker}


def _dcg(gains: list[int]) -> float:
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


# Splits kept blind for later rounds: only their totals are ever shown.
SEALED = frozenset({"holdout4", "holdout5", "holdout6"})
# Splits shown on their own and left out of `all`.
OUTSIDE_ALL = SEALED | {"dev2", "dev3", "holdout3"}


def load_personas() -> list[dict[str, Any]]:
    """Personas from personas.json (dev and test) and the later blind sets."""
    out: list[dict[str, Any]] = []
    for name in (
        "personas.json",
        "dev2.json",
        "dev3.json",
        "holdout2.json",
        "holdout3.json",
        "holdout4.json",
        "holdout5.json",
        "holdout6.json",
    ):
        path = EVALS / name
        if path.is_file():
            out.extend(json.loads(path.read_text(encoding="utf-8"))["personas"])
    return out


@lru_cache(maxsize=1)
def load_completed() -> dict[tuple[str, str], int]:
    """Blind grades for pairs the persona reviewers never graded (completed_grades.json)."""
    path = EVALS / "completed_grades.json"
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))["grades"]
    return {(r["persona"], r["org"]): int(r["grade"]) for r in rows}


def load_accepted() -> list[dict[str, Any]]:
    return list(json.loads((EVALS / "accepted_2026.json").read_text(encoding="utf-8"))["cases"])


def persona_metrics(ranker: Ranker, split: str = "all", grades: str = "original") -> dict[str, Any]:
    """nDCG@10, precision@5 (grade 2+), strong recall@10, and wrong picks in the top 5."""
    rows = []
    for persona in load_personas():
        if split != "all" and persona["split"] != split:
            continue
        if split == "all" and persona["split"] in OUTSIDE_ALL:
            continue
        given: dict[str, int] = persona["grades"]
        if grades == "completed":
            # The reviewer's grades and wrong picks always win over a completed one.
            extra = {
                org: g
                for (pid, org), g in load_completed().items()
                if pid == persona["id"] and org not in persona["wrong_top5"]
            }
            given = {**extra, **given}
        order = ranker(persona["profile"])[:10]
        ideal = _dcg(sorted(given.values(), reverse=True)[:10]) or 1.0
        strong = {name for name, grade in given.items() if grade == 3}
        rows.append(
            {
                "id": persona["id"],
                "ndcg10": _dcg([given.get(name, 0) for name in order]) / ideal,
                "p5": sum(1 for name in order[:5] if given.get(name, 0) >= 2) / 5,
                "strong_recall10": len(strong & set(order)) / len(strong) if strong else 1.0,
                "wrong5": sum(1 for name in order[:5] if name in persona["wrong_top5"]),
                "judged10": (
                    sum(1 for name in order if name in given or name in persona["wrong_top5"])
                    / len(order)
                    if order
                    else 1.0
                ),
                "empty": not order,
                "top3": order[:3],
            }
        )
    n = len(rows) or 1
    return {
        "personas": len(rows),
        "ndcg10": sum(r["ndcg10"] for r in rows) / n,
        "p5": sum(r["p5"] for r in rows) / n,
        "strong_recall10": sum(r["strong_recall10"] for r in rows) / n,
        "wrong5": sum(r["wrong5"] for r in rows),
        "judged10": sum(r["judged10"] for r in rows) / n,
        "empty": sum(1 for r in rows if r["empty"]),
        "rows": rows,
    }


def accepted_metrics(ranker: Ranker, split: str = "all") -> dict[str, Any]:
    """Where the organization that accepted each project lands: hit@k and MRR."""
    names = {org.name for org in catalog().orgs}
    ranks: list[int | None] = []
    for case in load_accepted():
        if split != "all" and case["split"] != split:
            continue
        if case["org"] not in names:
            continue
        order = ranker({"technologies": case["technologies"], "interests": case["interests"]})
        ranks.append(order.index(case["org"]) + 1 if case["org"] in order else None)
    n = len(ranks) or 1

    def hit(k: int) -> float:
        return sum(1 for r in ranks if r is not None and r <= k) / n

    return {
        "cases": len(ranks),
        "hit1": hit(1),
        "hit5": hit(5),
        "hit10": hit(10),
        "mrr": sum(1 / r for r in ranks if r) / n,
        "not_ranked": sum(1 for r in ranks if r is None),
    }


def evaluate(
    ranker_name: str = "current", split: str = "all", grades: str = "original"
) -> dict[str, Any]:
    ranker = RANKERS[ranker_name]
    return {
        "ranker": ranker_name,
        "split": split,
        "grades": grades,
        "personas": persona_metrics(ranker, split, grades),
        "accepted": accepted_metrics(ranker, split),
    }


def _print(result: dict[str, Any], *, detail: bool) -> None:
    p, a = result["personas"], result["accepted"]
    print(
        f"{result['ranker']:9s} {result['split']:4s}"
        f"{' (completed grades)' if result.get('grades') == 'completed' else ''} | "
        f"personas={p['personas']:2d} "
        f"nDCG@10={p['ndcg10']:.3f} P@5={p['p5']:.3f} strong@10={p['strong_recall10']:.3f} "
        f"wrong@5={p['wrong5']:2d} judged@10={p['judged10']:.2f} empty={p['empty']} | "
        f"projects={a['cases']} "
        f"hit@1={a['hit1']:.3f} hit@5={a['hit5']:.3f} hit@10={a['hit10']:.3f} MRR={a['mrr']:.3f}"
    )
    if detail and result["split"] in SEALED:
        print("    (sealed: per-persona rows are not shown)")
    elif detail:
        for row in p["rows"]:
            print(
                f"    {row['id']:20s} nDCG={row['ndcg10']:.2f} P@5={row['p5']:.1f} "
                f"wrong={row['wrong5']} top3={row['top3']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--split",
        choices=(
            "dev",
            "dev2",
            "dev3",
            "test",
            "holdout2",
            "holdout3",
            "holdout4",
            "holdout5",
            "holdout6",
            "all",
        ),
        default="all",
        help="Which personas and cases to score; holdout4, holdout5 and holdout6 are sealed, so only their totals are shown",
    )
    parser.add_argument("--ranker", choices=("both", "current", "baseline"), default="both")
    parser.add_argument(
        "--grades",
        choices=("original", "completed"),
        default="original",
        help="original: the reviewers' grades only (the documented numbers and the floors); "
        "completed: also the blind grades for pairs they never graded",
    )
    parser.add_argument("--detail", action="store_true", help="Show every persona")
    parser.add_argument("--json", action="store_true", help="Print the results as JSON")
    args = parser.parse_args(argv)
    names = ["baseline", "current"] if args.ranker == "both" else [args.ranker]
    present = {p["split"] for p in load_personas()}
    order = [
        x
        for x in (
            "dev",
            "dev2",
            "dev3",
            "test",
            "holdout2",
            "holdout3",
            "holdout4",
            "holdout5",
            "holdout6",
        )
        if x in present
    ]
    splits = [*order, "all"] if args.split == "all" else [args.split]
    results = [evaluate(name, split, args.grades) for split in splits for name in names]
    for result in results:
        if result["split"] in SEALED:
            result["personas"]["rows"] = []  # totals only, so the set stays blind
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for result in results:
            _print(result, detail=args.detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
