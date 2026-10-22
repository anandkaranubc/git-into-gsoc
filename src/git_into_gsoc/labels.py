"""Which issue labels mark work for a newcomer, and which ask for no AI help.

One rule for the issue search, for scoring, and for `recommend`'s starter screen. The
spellings come from a census of 24,779 labels in the top repositories of 144 GSoC
organizations' GitHub owners (2026-10-21).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# The usual names, best known first: a search tries them in this order.
BEGINNER_LABELS: tuple[str, ...] = (
    "good first issue",
    "good-first-issue",
    "good first bug",
    "good first contribution",
    "first-timers-only",
    "beginner",
    "beginner friendly",
    "beginner-friendly",
    "easy",
    "e-easy",
    "starter",
    "newcomer",
    "newcomers",
    "difficulty: easy",
    "level: easy",
    "level: beginner",
)
# Projects name their own beginner labels ("GSOC Starter", "Difficulty-easy",
# "complexity:low", "low-hanging fruit"); these words mark one wherever they appear.
BEGINNER_WORDS_RE = re.compile(
    r"good[ _-]?first|beginner|first[ _-]?(?:timer|issue|contrib|pr\b)|your first|newbie|"
    r"newcomer|novice|starter|\beasy\b|low[ _-]?hanging|new[ _-]?contributor|"
    r"up[ _-]?for[ _-]?grabs|upforgrabs|(?:complexity|difficulty|level)\W*(?:low|1|one)\b"
)
# Labels with those words that do not mark a task for a newcomer. Oppia's "Impact: Low
# -- ONLY DO IF GOOD FIRST ISSUE" postpones 381 issues ("Postponing for now, since it
# doesn't affect users much"), "Good First Issue (Taken)" is taken, "Easy to Revive"
# and "Easy Review" are about pull requests, and some projects say "not a good first
# issue". "Easy to reproduce" describes a bug report and "starter-kit" a component.
_NOT_BEGINNER_RE = re.compile(
    r"\btaken\b|\bclaimed\b|only do if|postpone|review|revive|reproduc|"
    r"starter[ _-]?(?:kit|template)|\bnot[ _-](?:a[ _-])?(?:good|easy|beginner|first)"
)
# Labels that ask for the work without AI tools. GDAL's "not for AI lovers" links its AI
# tool policy; OpenStreetMap's "good first issue - LLM not welcome" says LLM-generated
# pull requests are not welcome.
_NO_AI_RE = re.compile(
    r"not for ai\b|\bno[ _-]?(?:ai|llms?)\b|\bhuman[ _-]only\b|"
    r"\b(?:ai|llms?|chatgpt|copilot)\b[^,;]*\bnot (?:welcome|allowed|accepted|wanted)\b"
)


def is_beginner_label(name: str) -> bool:
    """True for a label that marks an issue as suitable for a newcomer."""
    low = name.strip().lower()
    if _NOT_BEGINNER_RE.search(low):
        return False
    return low in BEGINNER_LABELS or bool(BEGINNER_WORDS_RE.search(low))


def no_ai_label(labels: Iterable[str]) -> str | None:
    """The label that asks for the work without AI tools, if the issue has one."""
    return next((label for label in labels if _NO_AI_RE.search(label.lower())), None)
