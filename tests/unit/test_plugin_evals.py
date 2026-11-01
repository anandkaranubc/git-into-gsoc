"""The `claude plugin eval` suite in plugin-evals/: the mocks name real tools and carry the
server's current tool text, every case has graders, and the manifest points at the suite."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "plugin-evals"
MOCKS = SUITE / "mocks" / "git-into-gsoc"


def _run(coroutine: Any) -> Any:
    # Drive the coroutine without an event loop: creating one opens a socket pair on
    # Windows, which the test network guard blocks, and list_tools never waits on I/O.
    try:
        coroutine.send(None)
    except StopIteration as stop:
        return stop.value
    raise AssertionError("coroutine suspended on real I/O")


def _dedented(tool: dict[str, Any]) -> dict[str, Any]:
    # Python 3.13 strips the indentation from docstrings at compile time and earlier
    # versions keep it, so the same text differs by whitespace between CI jobs.
    return {**tool, "description": inspect.cleandoc(tool.get("description") or "")}


def _live_tools() -> list[dict[str, Any]]:
    from git_into_gsoc.mcp_server import mcp

    tools = _run(mcp.list_tools())
    return [_dedented(t.model_dump(by_alias=True, exclude_none=True, mode="json")) for t in tools]


def _mock_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    return text


def test_tool_snapshot_matches_the_server() -> None:
    # The eval run shows the model this file's descriptions and schemas, so a stale copy
    # would test old tool text.
    saved = json.loads((MOCKS / "_tools.json").read_text(encoding="utf-8"))["tools"]
    assert [_dedented(t) for t in saved] == _live_tools(), (
        "Run: python scripts/snapshot_mcp_tools.py"
    )


def test_every_mock_answers_a_real_tool_with_json() -> None:
    names = {str(t["name"]) for t in _live_tools()}
    mocks = [p for p in MOCKS.glob("*.md") if not p.name.startswith("_")]
    assert mocks
    for path in mocks:
        assert path.stem in names, f"{path.name} mocks a tool the server does not have"
        json.loads(_mock_body(path))  # the real server answers JSON, so the mock must too


def test_every_case_has_a_prompt_and_graders() -> None:
    cases = sorted(p.parent for p in SUITE.rglob("prompt.md"))
    assert len(cases) >= 5
    for case in cases:
        graders = list((case / "graders").glob("*.md"))
        assert graders, f"{case.name} has no graders"
        assert (case / "prompt.md").read_text(encoding="utf-8").startswith("---\n"), case.name


def test_manifest_points_at_the_suite() -> None:
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["experimental"]["evals"] == SUITE.name
