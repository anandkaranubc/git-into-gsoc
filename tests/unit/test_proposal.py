"""The proposal checker: sections, links and their authors, timelines, phrasing, and the
`proposal check` command."""

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


def test_a_pr_described_as_merged_must_be_merged() -> None:
    # A real beginner draft (2026-10-21) said "I have merged PR .../27463 and .../27402";
    # #27402 was closed without merging and the check still passed.
    draft = (
        "## About me\nI have merged PR https://github.com/sympy/sympy/pull/27463 and "
        "https://github.com/sympy/sympy/pull/27402.\n\n"
        "## Contributions\n- https://github.com/sympy/sympy/pull/27500 (open, under review)\n"
    )
    states = {27463: "merged", 27402: "closed", 27500: "open"}

    def lookup(repo: str, number: int) -> dict[str, Any] | None:
        state = states[number]
        return {
            "user": {"login": "me"},
            "merged_at": "2025-01-09T00:00:00Z" if state == "merged" else None,
            "state": "closed" if state != "open" else "open",
        }

    findings = _by_id(check_proposal(draft, github_user="me", lookup=lookup))
    claim = findings["link_claims"]
    assert claim["status"] == "fail"
    assert "27402" in claim["detail"] and "27463" not in claim["detail"]
    assert "27500" not in claim["detail"]  # described as open, which is true


def test_common_cover_letter_phrases_are_flagged() -> None:
    found = generic_phrases("I am a passionate and highly motivated student and a quick learner.")
    assert {"passionate and", "highly motivated", "quick learner"} <= set(found)


def test_plain_line_headings_from_a_pasted_doc_count_as_sections() -> None:
    # A simulated beginner pasted a Google Doc: headings were plain lines, so the
    # checker said the timeline and about sections were missing.
    text = (
        "Synopsis\n"
        "I will add keyboard navigation to the scheduler.\n\n"
        "2. Timeline\n"
        "Week 1: read the scheduler code.\n\n"
        "About Me\n"
        "I study computer science.\n"
        "The timeline is tight but fine.\n"
    )
    sections = detect_sections(text)
    assert sections["synopsis"] == "synopsis"
    assert sections["timeline"] == "timeline"
    assert sections["about"] == "about me"
    # An ordinary sentence that mentions a section word is not a heading.
    assert detect_sections("I will share a timeline later.")["timeline"] is None


def test_common_filler_lines_are_flagged() -> None:
    found = generic_phrases(
        "I am a fast learner and a hard worker who wants to make the world a better place "
        "with this amazing community."
    )
    assert {"fast learner", "hard worker", "make the world a better place"} <= set(found)
    assert "amazing community" in found


def test_short_draft_advice_cites_no_made_up_word_range() -> None:
    finding = _by_id(check_proposal("Timeline\nWeek 1: start."))["length"]
    assert "1,500" not in finding["detail"] and "no official length" in finding["detail"]


def test_proposal_check_file_works_as_people_type_it(tmp_path: Path) -> None:
    # A simulated beginner typed `proposal check proposal.txt` and got
    # "Got unexpected extra argument(s)".
    from typer.testing import CliRunner

    from git_into_gsoc.cli import app

    draft = tmp_path / "proposal.txt"
    draft.write_text("Synopsis\nAdd keyboard navigation.\n", encoding="utf-8")
    runner = CliRunner()
    typed = runner.invoke(app, ["proposal", "check", str(draft), "--no-verify"])
    assert typed.exit_code == 0, typed.output
    assert "Proposal check: proposal.txt" in typed.output
    missing = runner.invoke(app, ["proposal", "check"])
    assert missing.exit_code == 1 and "git-into-gsoc proposal draft.md" in missing.output


def test_a_template_heading_for_the_synopsis_counts() -> None:
    # Learning Unlimited's template calls it "The thing I want to do this summer".
    text = "The thing I want to do this summer\nImprove the scheduler.\n"
    assert detect_sections(text)["synopsis"] == "the thing i want to do this summer"
    detail = _by_id(check_proposal("Hello"))["deliverables"]["detail"]
    assert "gsocguides/student/writing-a-proposal" in detail
    assert "skip proposals" not in detail


def test_gitlab_merge_requests_are_found_and_their_authors_checked() -> None:
    # A simulated GNOME contributor linked someone else's merged MR as "My MR"; the
    # checker saw no links at all and said "No links to your contributions".
    text = (
        "## Prior contributions\n"
        "- My MR: https://gitlab.gnome.org/GNOME/gitg/-/merge_requests/413 (merged)\n"
        "- I commented on https://gitlab.gnome.org/GNOME/gitg/-/issues/345\n"
        "I am available 15 hours per week.\n"
    )
    asked: list[tuple[str, str, int]] = []

    def mr(host: str, path: str, iid: int) -> dict[str, Any] | None:
        asked.append((host, path, iid))
        return {"author": {"username": "someone-else"}, "state": "merged"}

    report = check_proposal(text, github_user="mei-lin", mr_lookup=mr)
    findings = _by_id(report)
    assert asked == [("gitlab.gnome.org", "GNOME/gitg", 413)]
    assert findings["links"]["status"] == "pass"
    assert findings["link_authors"]["status"] == "fail"
    assert "someone-else on gitlab.gnome.org" in findings["link_authors"]["detail"]
    assert findings["availability"]["status"] == "pass"
    assert {link["kind"] for link in report["links"]} == {"merge_request", "issue"}


def test_links_verified_is_true_only_when_a_link_was_checked(monkeypatch: Any) -> None:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    report = toolkit.check_proposal("No links here.", verify=True)
    assert report["links"] == [] and report["links_verified"] is False
