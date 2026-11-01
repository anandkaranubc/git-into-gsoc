"""The site's start page ranks with the package's own code, run in the browser.

These tests run that same code (``scripts/start_page.py``) natively on the JSON the
site build writes, and check it against the benchmark index the CLI uses. If the
JSON round trip or the page's wrapper ever drifted from `rank_orgs`, the benchmark
personas in ``evals/`` would show it here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_site import start_data  # noqa: E402
from scripts.eval_matching import catalog  # noqa: E402
from scripts.start_page import answer, load_index  # noqa: E402

from git_into_gsoc.matching.profile import build_profile  # noqa: E402
from git_into_gsoc.matching.rank import OrgIndex  # noqa: E402


def _personas() -> list[dict[str, Any]]:
    out = []
    for name in ("personas.json", "dev2.json"):
        data = json.loads((ROOT / "evals" / name).read_text(encoding="utf-8"))
        out.extend(p["profile"] for p in data["personas"])
    return out


@pytest.fixture(scope="module")
def page_index() -> OrgIndex:
    """The index the browser builds: through JSON, as ``orgs.json`` is written and read."""
    data_dir = ROOT / "src/git_into_gsoc/data"
    official = json.loads((data_dir / "official_orgs.json").read_text(encoding="utf-8"))
    signals = json.loads((data_dir / "org_signals.json").read_text(encoding="utf-8"))
    return load_index(json.loads(json.dumps(start_data(official, signals))))


def test_page_ranks_every_benchmark_persona_exactly_as_the_cli(page_index: OrgIndex) -> None:
    cli = catalog().index
    for profile in _personas():
        person = build_profile(
            technologies=profile.get("technologies"),
            interests=profile.get("interests"),
            experience=profile.get("experience"),
            hours_per_week=profile.get("hours_per_week"),
        )
        ours = page_index.rank(person, limit=10)
        theirs = cli.rank(person, limit=10)
        assert [(m.org.name, m.score, m.fit) for m in ours] == [
            (m.org.name, m.score, m.fit) for m in theirs
        ], profile
        for mine, cli_match in zip(ours, theirs, strict=True):
            assert mine.reasons() == cli_match.reasons()
            assert mine.evidence() == cli_match.evidence()
            assert mine.caveats == cli_match.caveats


def test_answer_is_shaped_like_what_start_prints(page_index: OrgIndex) -> None:
    result = answer(
        page_index,
        technologies="pyhton",
        interests="science, ai",
        hours=10,
        experience="new",
    )
    assert len(result["organizations"]) == 3
    assert result["read_as"] == ["Read 'pyhton' as 'python'."]
    assert result["commands"] == [
        "git-into-gsoc profile --experience new",
        'git-into-gsoc start --tech "pyhton" --interests "science, ai" --hours 10',
    ]
    assert result["next_steps"][0]["command"].startswith("git-into-gsoc org ")
    first = result["organizations"][0]
    match = page_index.rank(
        build_profile(
            technologies=["pyhton"],
            interests=["science", "ai"],
            experience="new",
            hours_per_week=10,
        ),
        limit=1,
    )[0]
    assert first["name"] == match.org.name
    assert first["why"] == [r for r in match.reasons() if not r.startswith("Accepted in")][:3]
    assert first["readiness"] == match.readiness[:1]
    assert first["caveats"] == match.caveats[:2]
    assert first["fit"] in {"strong", "good", "partial"}
    assert first["slug"]


def test_sitting_out_organizations_are_set_aside_as_start_does(page_index: OrgIndex) -> None:
    sitting_out = {
        p.org.name
        for p in page_index.profiles
        if p.participation.get("status") == "not_taking_part"
    }
    assert sitting_out, "the snapshot has no organization sitting out; pick another case"
    result = answer(page_index, technologies="django", interests="web", limit=1)
    shown = {org["name"] for org in result["organizations"]}
    assert shown and not shown & sitting_out
    for org in result["set_aside"]:
        assert org["name"] in sitting_out
        assert org["status"] == "not_taking_part"
        assert org["url"]


def test_blank_answers_rank_nothing(page_index: OrgIndex) -> None:
    result = answer(page_index, technologies="", interests="", hours=None, experience=None)
    assert result["organizations"] == []
    assert result["commands"] == ["git-into-gsoc start"]
