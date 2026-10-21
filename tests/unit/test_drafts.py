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


def _ids(report: dict, status: str) -> set[str]:
    return {f["id"] for f in report["findings"] if f["status"] == status}


def test_check_message_catches_placeholders_and_machine_tone() -> None:
    from git_into_gsoc.drafts import check_message

    text = (
        "I hope this message finds you well! I am passionate about delving into this "
        "cutting-edge project. I read <CONTRIBUTING or the developer guide>. Can you point me "
        "to the parser tests? Contact me at <me@example.org> or <https://example.org>."
    )
    report = check_message("intro", text)
    placeholders = next(f for f in report["findings"] if f["id"] == "placeholders")
    assert placeholders["status"] == "fail"
    assert "<CONTRIBUTING or the developer guide>" in placeholders["detail"]
    assert "example.org" not in placeholders["detail"]
    assert "machine_tone" in _ids(report, "warn")
    assert report["verdict"] == "Fix 1 problem(s) before sending."


def test_check_message_kind_rules() -> None:
    from git_into_gsoc.drafts import check_message

    assert "greeting_only" in _ids(check_message("intro", "Hi everyone!"), "fail")
    assert "bare_claim" in _ids(
        check_message("claim", "Can I work on this? Please assign it to me."), "fail"
    )
    planned = check_message(
        "claim",
        "I'd like to work on this. I reproduced it on main with an empty CSV file; the cause "
        "looks to be in reader.py. Plan: return an empty list early. PR by Friday.",
    )
    assert _ids(planned, "fail") == set() and _ids(planned, "warn") == set()
    question = check_message("question", "Can I ask something about the build. It fails for me.")
    assert "question" in _ids(question, "fail")
    assert {"ask_to_ask", "tried"} <= _ids(question, "warn")
    pr = check_message("pr", "Small cleanup of the reader.")
    assert {"issue_link", "validation"} <= _ids(pr, "warn")
    status = check_message("status", "This week I finished the parser fix.")
    assert len([f for f in status["findings"] if f["id"] == "three_questions"]) == 2


def test_check_message_rejects_unknown_kinds_through_the_service() -> None:
    import pytest

    from git_into_gsoc.errors import InputError
    from git_into_gsoc.service import GSoCToolkit

    with pytest.raises(InputError):
        GSoCToolkit().check_message("poem", "hello")


def test_cli_draft_check_reads_a_file(tmp_path) -> None:
    message = tmp_path / "claim.md"
    message.write_text("Can I work on this?", encoding="utf-8")
    result = runner.invoke(app, ["draft", "claim", "--check", str(message)])
    assert result.exit_code == 0, result.output
    assert "A bare request to work on it" in result.output
    assert "Fix 1 problem(s) before sending." in result.output


def test_claim_draft_reads_the_whole_contributing_guide(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.models import ContributionGuide
    from git_into_gsoc.service import GSoCToolkit

    # zulip/zulip explains `@zulipbot claim` around line 400 of CONTRIBUTING.md; only
    # the first 1,500 characters were read, so the draft said nothing about it.
    intro = "Welcome to Zulip. " * 120
    full = intro + "\nTo claim a help wanted issue, post a comment that says `@zulipbot claim`.\n"
    full += "Sign your commits with git commit -s.\n"
    guide = ContributionGuide(
        repo="zulip/zulip", contributing_excerpt=intro[:1500], contributing_text=full
    )
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "contribution_guide", lambda repo: guide)
    monkeypatch.setattr(
        toolkit, "issue_status", lambda ref: {"title": "x", "availability": "available"}
    )
    draft = toolkit.draft("claim", issue="zulip/zulip#36000")
    assert draft["context"]["claim_convention"] == {"kind": "command", "text": "@zulipbot claim"}
    assert "@zulipbot claim" in draft["template"]
    assert "contributing_text" not in guide.model_dump()  # never printed or sent to assistants


def test_pr_draft_uses_the_install_and_test_commands_ci_runs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.models import ContributionGuide
    from git_into_gsoc.service import GSoCToolkit

    # A real run on sympy/sympy: the draft said "<the project's test command>" although
    # orient knew CI runs `pytest -n auto`, and it never said how to install.
    toolkit = GSoCToolkit()
    gh = toolkit.github
    monkeypatch.setattr(gh, "get_repo", lambda o, r: {"default_branch": "master"})
    monkeypatch.setattr(gh, "branch_rules", lambda *a: [])
    monkeypatch.setattr(
        gh, "contribution_guide", lambda repo: ContributionGuide(repo="sympy/sympy")
    )
    tree = {"tree": [{"path": ".github/workflows/runtests.yml", "type": "blob"}]}
    monkeypatch.setattr(gh, "git_tree", lambda *a: tree)
    workflow = (
        "jobs:\n  t:\n    steps:\n      - run: python -m pip install --upgrade pip\n"
        "      - run: pip install -r requirements-dev.txt\n      - run: pytest -n auto\n"
    )
    monkeypatch.setattr(gh, "get_raw_file", lambda *a: workflow)
    draft = toolkit.draft("pr", repo="sympy/sympy")
    assert "pip install -r requirements-dev.txt   # install as CI does" in draft["template"]
    assert "pytest -n auto   # run the tests once" in draft["template"]
    assert "<the project's test command>" not in draft["template"]
    assert "python3 -m venv .venv" in draft["template"]  # before any pip install


def test_manifest_commands_fill_in_when_ci_has_no_tests() -> None:
    from git_into_gsoc.drafts import manifest_commands

    # processing/p5.sound.js (2026-10-21): no test workflow, package.json has only "build".
    names = {"package.json", "package-lock.json"}
    install, check = manifest_commands(names, package_json='{"scripts": {"build": "rollup -c"}}')
    assert install == ["npm ci"] and check == "npm run build"
    install, check = manifest_commands(
        {"package.json", "yarn.lock"}, package_json='{"scripts": {"test": "jest"}}'
    )
    assert install == ["yarn install"] and check == "yarn test"
    npm_default = '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}'
    assert manifest_commands({"package.json"}, package_json=npm_default)[1] is None
    assert manifest_commands({"pyproject.toml", "tests"}, package_json=None) == (
        ["pip install -e ."],
        "pytest",
    )
    assert manifest_commands({"Cargo.toml"}, package_json=None) == ([], "cargo test")
    assert manifest_commands({"Gemfile"}, package_json=None) == (["bundle install"], None)


def test_pr_draft_says_when_no_test_command_exists(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from git_into_gsoc.drafts import render_draft

    draft = render_draft(
        "pr",
        context={
            "repo": "processing/p5.sound.js",
            "default_branch": "main",
            "install_commands": ["npm ci"],
            "commands_source": "package.json",
            "test_commands": ["npm run build"],
            "test_is_build": True,
        },
    )
    assert "npm ci   # install (from package.json)" in draft["template"]
    assert "npm run build   # no test command found; at least check it builds" in draft["template"]


def test_pr_draft_lists_each_install_step_once() -> None:
    from git_into_gsoc.drafts import render_draft

    # OWASP/threat-dragon: "npm clean-install" and "npm clean-install --ignore-scripts".
    draft = render_draft(
        "pr",
        context={
            "repo": "OWASP/threat-dragon",
            "default_branch": "main",
            "install_commands": ["npm clean-install", "npm clean-install --ignore-scripts"],
            "test_commands": ["npm run test:desktop"],
        },
    )
    assert draft["template"].count("npm clean-install") == 1
