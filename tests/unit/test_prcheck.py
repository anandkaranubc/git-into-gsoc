"""Checking a pull request against the repository's own rules."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from conftest import load_fixture
from git_into_gsoc.github.client import GitHubClient
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


# OWASP/threat-dragon's template offers two exclusive options (2026-10-21, PR #1913).
EITHER_OR = (
    "- [x] appropriate unit tests have been created and/or modified\n"
    "- [{a}] *either* no AI-generated content has been used in this pull request\n"
    "- [{b}] *or* any [use of AI](../blob/main/contributing.md#use-of-ai) in this pull "
    "request has been disclosed below:\n"
)


def _checklist(body: str) -> dict[str, Any] | None:
    report = check_pull_request(
        _pull(body="Fixes #3. The reader crashed on empty files; it now returns [].\n" + body),
        FILES,
        [_commit("Fix empty input")],
        [],
        rules=_rules(),
        pr_template=TEMPLATE,
    )
    return next((f for f in report["findings"] if f["id"] == "checklist"), None)


def test_one_ticked_option_of_an_either_or_pair_is_enough() -> None:
    assert _checklist(EITHER_OR.format(a=" ", b="x")) is None
    assert _checklist(EITHER_OR.format(a="x", b=" ")) is None
    neither = _checklist(EITHER_OR.format(a=" ", b=" "))
    assert neither is not None
    assert neither["title"] == "1 checklist item(s) unticked"
    assert "either no AI-generated content has been used in this pull request" in neither["detail"]
    assert "*" not in neither["detail"] and "](" not in neither["detail"]


def test_long_unticked_items_are_cut_at_a_word() -> None:
    item = (
        "you have considered any changes required for the functional tests, the desktop "
        "build, and the documentation site"
    )
    found = _checklist(f"- [ ] {item}\n")
    assert found is not None
    assert "functional tests, the desktop build, and\u2026. Tick them" in found["detail"]


def test_a_page_about_testing_is_not_a_test_change() -> None:
    # zulip/zulip#40416 (2026-10-21) changes only docs/testing/manual-testing.md, and
    # pr-check said "Includes test changes".
    report = check_pull_request(
        _pull(body="Fixes #3. Update the manual testing page.\n- [ ] Tests added\n- [ ] Docs."),
        [{"filename": "docs/testing/manual-testing.md"}],
        [_commit("docs: update menu references")],
        [],
        rules=_rules(),
        pr_template=TEMPLATE,
    )
    findings = {f["id"]: f for f in report["findings"]}
    assert "tests" not in findings
    assert ".." not in findings["checklist"]["detail"]


def test_failing_commit_statuses_are_failing_checks() -> None:
    # A live check of 0.24.0: KubeVirt's Prow reports as commit statuses, and pr-check
    # said "Checks are passing" and "No blockers" with two Prow jobs failing.
    api = "https://api.github.com/repos/kubevirt/kubevirt/commits/abc123"
    with respx.mock:
        respx.get(f"{api}/check-runs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "check_runs": [
                        {"name": "check-vep", "status": "completed", "conclusion": "success"}
                    ]
                },
            )
        )
        respx.get(f"{api}/status").mock(
            return_value=httpx.Response(200, json=load_fixture("commit_status_prow.json"))
        )
        checks = GitHubClient().check_runs("kubevirt", "kubevirt", "abc123")
    by_name = {c["name"]: c for c in checks}
    assert len(checks) == 7 and by_name["check-vep"]["conclusion"] == "success"
    assert by_name["pull-kubevirt-fuzz"]["conclusion"] == "failure"
    assert by_name["tide"]["status"] == "pending" and by_name["tide"]["conclusion"] is None
    assert by_name["pull-kubevirt-fuzz"]["url"].startswith("https://prow.ci.kubevirt.io/view/")

    report = check_pull_request(_pull(), [], [], checks, rules=_rules())
    failing = next(f for f in report["findings"] if f["id"] == "checks")
    assert failing["status"] == "fail"
    assert failing["title"] == (
        "Failing checks: pull-kubevirt-check-unassigned-tests, pull-kubevirt-fuzz"
    )
    assert (
        "Logs: pull-kubevirt-check-unassigned-tests: https://prow.ci.kubevirt.io/"
        in (failing["detail"])
    )


def test_commit_statuses_are_cleaned_and_do_not_repeat_check_runs() -> None:
    api = "https://api.github.com/repos/acme/lib/commits/abc123"
    statuses = [
        {"context": "ci / test", "state": "failure"},  # also a check run: the run wins
        {
            "context": "build<!-- hidden note -->\u200b",
            "state": "error",
            "target_url": "https://ci.example/1",
        },
        {"context": "", "state": "failure"},
    ]
    with respx.mock:
        respx.get(f"{api}/check-runs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "check_runs": [
                        {"name": "ci / test", "status": "completed", "conclusion": "success"}
                    ]
                },
            )
        )
        respx.get(f"{api}/status").mock(
            return_value=httpx.Response(200, json={"statuses": statuses})
        )
        checks = GitHubClient().check_runs("acme", "lib", "abc123")
    assert [(c["name"], c["conclusion"]) for c in checks] == [
        ("ci / test", "success"),
        ("build", "failure"),
    ]
