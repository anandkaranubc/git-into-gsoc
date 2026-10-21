from __future__ import annotations

from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.drafts import DRAFT_KINDS, claim_convention, render_draft

runner = CliRunner()


def test_every_kind_renders_with_rules_and_sources() -> None:
    for kind in DRAFT_KINDS:
        draft = render_draft(kind, context={})
        assert draft["kind"] == kind
        assert "<" in draft["template"] and ">" in draft["template"]
        assert draft["rules"] and all(r["source"].startswith("http") for r in draft["rules"])
        assert draft["must_fill"]
        assert "—" not in draft["template"]


def test_claim_uses_issue_facts_and_convention() -> None:
    draft = render_draft(
        "claim",
        context={
            "issue": {"repo": "acme/lib", "number": 12, "title": "Crash on empty input"},
            "claim_convention": {"kind": "command", "text": "/assign"},
            "files": ["lib/parser.py"],
        },
    )
    assert "acme/lib#12" in draft["template"]
    assert "/assign" in draft["template"]
    assert "lib/parser.py" in draft["template"]
    assert any("plan" in field.lower() for field in draft["must_fill"])


def test_claim_convention_detection() -> None:
    assert claim_convention("Comment /assign to claim an issue.")["kind"] == "command"
    assert claim_convention("Type .take on the issue to be assigned.")["text"] == ".take"
    assert claim_convention("We do not assign issues; just open a PR.")["kind"] == "no_assignment"
    assert (
        claim_convention("Leave a comment with your intention to start working on it.")["kind"]
        == "comment"
    )
    assert claim_convention("")["kind"] == "unknown"


def test_intro_mentions_org_and_channel() -> None:
    draft = render_draft(
        "intro",
        context={"org": "SymPy", "channels": ["Zulip", "Mailing list"], "year": 2027},
    )
    assert "SymPy" in draft["template"]
    assert "Zulip" in draft["template"]
    assert "2027" in draft["template"]


def test_status_uses_latest_log_entry() -> None:
    draft = render_draft(
        "status",
        context={
            "log": {
                "goal": "Reproduce #12",
                "done": "Reproduced",
                "stuck": "Flaky test",
                "next_step": "Ask",
            }
        },
    )
    assert "Reproduced" in draft["template"] and "Flaky test" in draft["template"]


def test_cli_draft_offline_kind() -> None:
    result = runner.invoke(app, ["draft", "question"])
    assert result.exit_code == 0, result.output
    assert "What I tried" in result.stdout
    assert "Rules" in result.stdout


def test_cli_draft_unknown_kind() -> None:
    result = runner.invoke(app, ["draft", "poem"])
    assert result.exit_code != 0


def test_pr_draft_lists_the_exact_setup_commands() -> None:
    draft = render_draft(
        "pr",
        context={
            "repo": "sympy/sympy",
            "issue": {"repo": "sympy/sympy", "number": 5},
            "default_branch": "master",
            "handle": "octocat",
            "test_commands": ["pytest sympy/core"],
        },
    )
    text = draft["template"]
    assert "git clone https://github.com/octocat/sympy.git" in text
    assert "git switch -c fix-5-<short-name> upstream/master" in text
    assert "pytest sympy/core" in text
    assert "git push -u origin fix-5-<short-name>" in text
    assert "Before you start" not in render_draft("pr", context={})["template"]


def test_pr_draft_lists_branch_rule_gates() -> None:
    text = render_draft(
        "pr", context={"gates": ["Needs 2 approving reviews including a code owner"]}
    )["template"]
    assert "This repository's branch rules also require:" in text
    assert "  - Needs 2 approving reviews including a code owner" in text
    assert "branch rules" not in render_draft("pr", context={})["template"]
