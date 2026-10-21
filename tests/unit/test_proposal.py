from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import FIXTURES
from git_into_gsoc.proposal import (
    check_proposal,
    detect_sections,
    generic_phrases,
    github_links,
    timeline_entries,
)

WEAK = (FIXTURES / "proposal_weak.md").read_text(encoding="utf-8")
STRONG = (FIXTURES / "proposal_strong.md").read_text(encoding="utf-8")


def _by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in report["findings"]}


def test_sections_detected_from_headings() -> None:
    sections = detect_sections(STRONG)
    assert sections["synopsis"] == "synopsis"
    assert sections["timeline"] == "timeline"
    assert sections["contributions"] == "prior contributions"
    assert sections["ai_statement"] == "ai usage"
    assert detect_sections(WEAK)["synopsis"] is None


def test_links_and_phrases_and_weeks() -> None:
    links = github_links(STRONG)
    assert {(link.kind, link.number) for link in links} >= {("issue", "27019"), ("pull", "28100")}
    assert len([link for link in links if link.kind == "pull"]) == 2  # deduplicated
    assert timeline_entries(STRONG) == 8
    assert timeline_entries(WEAK) == 0
    assert "leverage" in generic_phrases(WEAK)
    assert generic_phrases(STRONG) == []


def test_weak_proposal_fails_on_structure_evidence_and_phrasing() -> None:
    report = check_proposal(WEAK)
    findings = _by_id(report)
    assert findings["synopsis"]["status"] == "fail"
    assert findings["links"]["status"] == "fail"
    assert findings["timeline_detail"]["status"] == "fail"
    assert findings["generic_phrasing"]["status"] == "fail"
    assert findings["specificity"]["status"] == "fail"
    assert report["summary"]["fail"] >= 5
    assert report["verdict"].startswith("Not ready")


def test_strong_proposal_passes_and_verifies_authorship() -> None:
    calls: list[tuple[str, int]] = []

    def lookup(repo: str, number: int) -> dict[str, Any] | None:
        calls.append((repo, number))
        if number == 28100:
            return {
                "user": {"login": "alice"},
                "merged_at": "2026-02-01T00:00:00Z",
                "state": "closed",
            }
        return {"user": {"login": "someone-else"}, "merged_at": None, "state": "open"}

    report = check_proposal(STRONG, github_user="alice", lookup=lookup)
    findings = _by_id(report)
    assert calls == [("sympy/sympy", 28100), ("sympy/sympy", 28150)]
    assert findings["links"]["status"] == "pass" and "1 merged" in findings["links"]["detail"]
    assert findings["link_authors"]["status"] == "fail"
    assert "someone-else" in findings["link_authors"]["detail"]
    assert findings["timeline_detail"]["status"] == "pass"
    assert findings["buffer"]["status"] == "pass"
    assert findings["specificity"]["status"] == "pass"
    assert findings["ai_statement"]["status"] == "pass"
    assert report["summary"]["fail"] == 1  # only the foreign PR


def test_strong_proposal_without_verification_has_no_failures() -> None:
    report = check_proposal(STRONG)
    assert report["summary"]["fail"] == 0
    assert all(link["state"] is None for link in report["links"])
    assert report["verdict"].startswith(("Close", "Structurally complete"))


def test_cli_proposal_check_reads_file(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from git_into_gsoc.cli import app

    draft = tmp_path / "draft.md"
    draft.write_text(WEAK, encoding="utf-8")
    result = CliRunner().invoke(app, ["proposal", str(draft), "--no-verify"])
    assert result.exit_code == 0, result.output
    assert "Not ready" in result.output
    assert "generic phrase" in result.output
    missing = CliRunner().invoke(app, ["proposal", str(tmp_path / "nope.md")])
    assert missing.exit_code == 1 and "Cannot read" in missing.output


def test_mcp_proposal_check_tool_and_resources() -> None:
    import json

    from git_into_gsoc.mcp_server import gsoc_proposal_check, mcp

    report = json.loads(gsoc_proposal_check(WEAK, verify_links=False))
    assert report["summary"]["fail"] >= 5
    # Use the sync managers: asyncio.run() opens a socketpair on Windows, which the
    # hermetic test environment blocks.
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert tools["gsoc_proposal_check"].annotations is not None
    assert tools["gsoc_proposal_check"].annotations.read_only_hint is True
    assert tools["gsoc_progress"].annotations is not None
    assert tools["gsoc_progress"].annotations.read_only_hint is False
    uris = {str(r.uri) for r in mcp._resource_manager.list_resources()}
    assert {"gsoc://journey", "gsoc://official-sources", "gsoc://anti-spam-rules"} <= uris


def test_placeholders_and_ideas_page_mirroring() -> None:
    from git_into_gsoc.proposal import mirrored_fraction, placeholders

    assert placeholders("Hi [Your Name], see <insert link> and TODO: fill, {{org}}") == [
        "[Your Name]",
        "<insert link>",
        "TODO",
        "{{org}}",
    ]
    ideas = "Implement a sparse multivariate GCD for polynomials in the ring series module."
    copied = ideas + " " + ideas + " I will do this."
    assert mirrored_fraction(copied, ideas) > 0.25
    assert mirrored_fraction(STRONG, ideas) < 0.05
    report = check_proposal(WEAK + "\n[Your name]\n", ideas_text=ideas)
    findings = _by_id(report)
    assert findings["placeholders"]["status"] == "fail"
    assert findings["mirrors_ideas_page"]["status"] == "pass"
    assert (
        _by_id(check_proposal(copied, ideas_text=ideas))["mirrors_ideas_page"]["status"] == "fail"
    )
