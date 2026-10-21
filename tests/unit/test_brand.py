"""The brand kit draws one icon per journey phase; keep it in step with the CLI."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from git_into_gsoc.models import JourneyPhase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.brand.glyphs import ICONS, PHASES  # noqa: E402


def test_every_journey_phase_has_an_icon_in_cli_order() -> None:
    assert [phase.value for phase in JourneyPhase] == PHASES
    assert list(ICONS)[: len(PHASES)] == PHASES


def test_icons_sit_on_the_12_unit_grid() -> None:
    for name, rows in ICONS.items():
        assert len(rows) == 12, name
        assert all(len(row) == 12 and set(row) <= {".", "X"} for row in rows), name


def test_generated_icon_files_exist() -> None:
    for name in ICONS:
        for scheme in ("ink", "paper", "merge"):
            assert (ROOT / "brand" / "icons" / f"{name}-{scheme}.svg").is_file(), name


def test_site_journey_lists_every_phase() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    journey = re.search(r'<ol class="journey">(.*?)</ol>', html, flags=re.S)
    assert journey is not None
    assert journey.group(1).count("<li>") == len(JourneyPhase)
