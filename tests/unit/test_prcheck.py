"""Checking a pull request against the repository's own rules."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.github.prcheck import check_pull_request

TEMPLATE = "## Description\n\n## Checklist\n- [ ] Tests added\n- [ ] Docs updated\n"


def _rules(**extra: Any) -> dict[str, Any]:
    return {
        "dco": {"required": False, "evidence": []},
        "conventional_commits": {"expected": False},
        "changelog": {"expected": False, "evidence": []},
        "ai_disclosure_in_pr_template": False,
        "gates": [],
        **extra,
    }


def _pull(**extra: Any) -> dict[str, Any]:
    return {
        "number": 7,
        "title": "Fix empty input in the reader",
        "body": "Fixes #3. The reader crashed on empty files; it now returns an empty list.\n"
        "- [x] Tests added\n- [x] Docs updated",
        "state": "open",
        "base": {"ref": "main"},
        "additions": 40,
        "deletions": 5,
        "changed_files": 2,
        "mergeable_state": "clean",
        **extra,
    }


def _ids(report: dict[str, Any], status: str) -> set[str]:
    return {f["id"] for f in report["findings"] if f["status"] == status}


def _commit(message: str) -> dict[str, Any]:
    return {"commit": {"message": message}}


FILES = [{"filename": "src/reader.py"}, {"filename": "tests/test_reader.py"}]


def test_a_tidy_pull_request_passes() -> None:
    report = check_pull_request(
        _pull(),
        FILES,
        [_commit("Fix empty input")],
        [{"name": "tests", "status": "completed", "conclusion": "success"}],
        rules=_rules(),
        pr_template=TEMPLATE,
    )
    assert _ids(report, "fail") == set() and _ids(report, "warn") == set()
    assert {"issue_link", "tests", "checks"} <= _ids(report, "pass")
    assert report["verdict"].startswith("Ready for review")


def test_blockers_from_conflict_checks_sign_off_and_issue_gate() -> None:
    gates = [
        {
            "gate": "Pull requests must reference an issue that is assigned to the author",
            "source": ".github/workflows/check.yml",
        }
    ]
    report = check_pull_request(
        _pull(
            body="Small tidy-up of the reader so it handles more cases correctly.",
            mergeable_state="dirty",
        ),
        FILES,
        [_commit("Fix empty input"), _commit("Address review\n\nSigned-off-by: A <a@x>")],
        [{"name": "lint", "status": "completed", "conclusion": "failure"}],
        rules=_rules(dco={"required": True}, gates=gates),
        pr_template=TEMPLATE,
    )
    assert _ids(report, "fail") == {"conflict", "checks", "sign_off", "issue_link"}
    sign_off = next(f for f in report["findings"] if f["id"] == "sign_off")
    assert sign_off["title"] == "1 of 2 commit(s) lack a sign-off"
    assert "git rebase --signoff origin/main" in sign_off["detail"]
    assert report["verdict"] == "Fix 4 problem(s) before asking for review."


def test_warnings_for_template_tests_changelog_disclosure_size_and_style() -> None:
    report = check_pull_request(
        _pull(
            title="Reader improvements",
            body="Fixes #3. Improves the reader in several ways.\n- [ ] Tests added\n- [x] Docs updated",
            additions=900,
            deletions=10,
            changed_files=4,
            draft=True,
        ),
        [{"filename": "src/reader.py"}, {"filename": "src/writer.py"}],
        [_commit("reader improvements")],
        [],
        rules=_rules(
            conventional_commits={"expected": True},
            changelog={"expected": True, "evidence": ["changelog/ holds one entry per change"]},
            ai_disclosure_in_pr_template=True,
        ),
        pr_template=TEMPLATE,
        test_dirs=["tests"],
        news_dir="changelog",
    )
    assert _ids(report, "warn") == {
        "checklist",
        "commit_style",
        "tests",
        "changelog",
        "ai_disclosure",
        "size",
        "draft",
    }
    tests = next(f for f in report["findings"] if f["id"] == "tests")
    assert "tests here live in tests/" in tests["detail"]
    assert report["verdict"].startswith("No blockers")


def test_changelog_entry_in_the_fragment_folder_and_gates_listed() -> None:
    report = check_pull_request(
        _pull(),
        [*FILES, {"filename": "changelog/7.bugfix.rst"}],
        [],
        [],
        rules=_rules(
            changelog={"expected": True, "evidence": []},
            gates=[{"gate": "Needs 2 approving reviews", "source": "ruleset on main"}],
        ),
        pr_template=TEMPLATE,
        news_dir="changelog",
    )
    assert "changelog" in _ids(report, "pass")
    assert report["what_happens_next"] == ["Needs 2 approving reviews"]
