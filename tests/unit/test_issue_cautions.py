"""`issues` says why an issue may not suit a first contribution, as `recommend` decides it."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.matching.profile import ContributorProfile
from git_into_gsoc.service import _with_cautions


def _issue(number: int, **extra: Any) -> dict[str, Any]:
    return {
        "repo": "acme/lib",
        "number": number,
        "title": "Fix the parser crash on empty input",
        "labels": ["good first issue"],
        "availability": "available",
        "created_at": "2026-09-01T00:00:00Z",
        "body_excerpt": "Steps to reproduce: run it with no input.",
        "assessment": {"claims": []},
        **extra,
    }


def test_cautions_say_why_and_come_after_the_rest() -> None:
    # A blind beginner test (2026-10-22) found SymPy's "Find bugs in the rewrite of the
    # assumption system", a call for testing, at the top score with no warning.
    issues = [
        _issue(1, title="Find bugs in the rewrite of the assumption system: a call for testing"),
        _issue(2, created_at="2019-03-01T00:00:00Z"),
        _issue(3),
        _issue(4, availability="claimed"),
    ]
    listed = _with_cautions(issues, ContributorProfile())
    assert [i["number"] for i in listed] == [3, 1, 2, 4]
    assert "caution" not in listed[0]
    assert "call for testing" in listed[1]["caution"]
    assert listed[2]["caution"] == "open since 2019"


def test_the_issues_table_shows_the_caution(monkeypatch: Any) -> None:
    from typer.testing import CliRunner

    from git_into_gsoc import cli
    from git_into_gsoc.cli import app

    row = {
        **_issue(5),
        "beginner_score": 90,
        "signals": [],
        "caution": "an announcement, roadmap, tracker, or call for testing rather than a task",
    }

    class Fake:
        def find_issues(self, **k: Any) -> dict[str, Any]:
            return {"issues": [row], "note": "Searching acme", "next_steps": []}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = CliRunner().invoke(app, ["issues", "--repo", "acme/lib"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    assert "! an announcement, roadmap, tracker, or call for testing" in result.output


def test_issue_gives_the_same_caution_as_the_list(monkeypatch: Any) -> None:
    # A blind beginner test (2026-10-22) opened an issue the list marked "has no
    # beginner label, only 'help wanted'"; `issue` said only "available".
    from typer.testing import CliRunner

    from git_into_gsoc import cli
    from git_into_gsoc.cli import app
    from git_into_gsoc.models import Availability, IssueAssessment
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    found = IssueAssessment(
        availability=Availability.LIKELY_TAKEN, reason="An open pull request references it"
    )
    issue = {
        "title": "Speed up the parser",
        "html_url": "https://github.com/acme/lib/issues/9",
        "labels": [{"name": "help wanted"}],
        "body": "The parser is slow on large files.",
        "created_at": "2026-09-01T00:00:00Z",
        "user": {"login": "maintainer"},
    }
    monkeypatch.setattr(toolkit.github, "assess", lambda full, num: (issue, found))
    monkeypatch.setattr(toolkit.github, "get_repo", lambda owner, name: {"archived": False})
    monkeypatch.setattr(toolkit.github, "unlinked_pulls", lambda *a: [])
    data = toolkit.issue_status("acme/lib#9")
    assert data["caution"] == "has no beginner label, only 'help wanted'"

    monkeypatch.setattr(cli, "_toolkit", lambda: toolkit)
    out = CliRunner().invoke(app, ["issue", "acme/lib#9"], env={"COLUMNS": "120"}).output
    assert "Status: likely taken" in out and "likely_taken" not in out
    assert "May not suit a first contribution: has no beginner label" in out


def test_the_list_says_when_issues_have_no_beginner_label(monkeypatch: Any) -> None:
    from git_into_gsoc.models import Availability, IssueCandidate
    from git_into_gsoc.service import GSoCToolkit

    def candidate(number: int, labels: list[str]) -> IssueCandidate:
        return IssueCandidate(
            repo="acme/lib",
            number=number,
            title=f"Issue {number}",
            url=f"https://github.com/acme/lib/issues/{number}",
            labels=labels,
            availability=Availability.AVAILABLE,
        )

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "list_labels", lambda owner, name: [])
    monkeypatch.setattr(toolkit, "gsoc_github_orgs", lambda **k: ([], [], "Searching acme/lib."))
    for found, expected in (
        ([candidate(1, ["good first issue"]), candidate(2, ["help wanted"])], "1 of these have"),
        ([candidate(3, ["help wanted"])], "None of these has a beginner label"),
    ):
        monkeypatch.setattr(
            toolkit.github, "find_beginner_issues", lambda found=found, **k: list(found)
        )
        note = toolkit.find_issues(repo="acme/lib", scope="all")["note"]
        assert expected in note, note
