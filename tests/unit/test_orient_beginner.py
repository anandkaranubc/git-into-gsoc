"""`orient` for a first-time contributor: no repeats, no guessed paths, rules with real evidence."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.github.orientation import conventions, find_paths, reading_plan


def _tree(*paths: str) -> list[dict[str, Any]]:
    return [{"path": p.rstrip("/"), "type": "tree" if p.endswith("/") else "blob"} for p in paths]


def test_a_contributing_guide_in_docs_is_not_also_an_architecture_doc() -> None:
    # MDAnalysis mdacli (blind beginner test, 2026-10-22): docs/CONTRIBUTING.rst was
    # listed twice under "Read first" and as steps 2 and 3 of the reading order.
    found = find_paths(_tree("README.rst", "docs/", "docs/CONTRIBUTING.rst", "docs/index.rst"))
    found["contributing"] = "docs/CONTRIBUTING.rst"  # as the community profile reports it
    assert "docs/CONTRIBUTING.rst" not in found["architecture_docs"]
    plan = reading_plan(found=found, points=[], example_pr=None)
    paths = [step["path"] for step in plan]
    assert paths.count("docs/CONTRIBUTING.rst") == 1


def test_one_signed_commit_is_not_a_sign_off_rule() -> None:
    def commit(message: str) -> dict[str, Any]:
        return {"commit": {"message": message}}

    signed = "Fix a typo\n\nSigned-off-by: A <a@example.com>"
    few = conventions([commit(signed)], contributing="", pr_template="", check_names=[], found={})
    assert not few["dco"]["required"]
    many = conventions(
        [commit(signed)] * 5, contributing="", pr_template="", check_names=[], found={}
    )
    assert many["dco"]["required"]
    assert "5 of the last 5 commits carry Signed-off-by" in many["dco"]["evidence"]


def test_ci_tox_and_sign_off_are_explained_in_plain_words(monkeypatch: Any) -> None:
    from typer.testing import CliRunner

    from git_into_gsoc import cli
    from git_into_gsoc.cli import app

    data = {
        "repo": "acme/lib",
        "description": "",
        "languages": [],
        "license": None,
        "pushed_days_ago": 1,
        "as_of_commit": "abc",
        "default_branch": "main",
        "code_map": [],
        "entry_points": [],
        "test_commands": [{"command": "tox -e tests", "source": ".github/workflows/tests.yml"}],
        "ci_environment": {},
        "setup_hints": [],
        "docs": {
            "readme": "README.rst",
            "contributing": "docs/C.rst",
            "architecture": ["docs/C.rst"],
        },
        "maintainers": {"commits_90d": 0, "active_committers_90d": [], "codeowners": []},
        "conventions": {
            "dco": {"required": True, "evidence": ["a DCO status check runs on pull requests"]},
            "cla": {"required": False, "evidence": []},
            "conventional_commits": {"expected": False, "evidence": []},
            "pre_commit": False,
            "pr_checklist_items": 0,
            "ai_disclosure_in_pr_template": False,
        },
        "policies": [],
        "reading_plan": [],
        "next_steps": [],
        "channels": [],
        "codetour": None,
        "issues": [],
        "note": "",
    }

    class Fake:
        def orient_repo(self, *a: Any, **k: Any) -> dict[str, Any]:
            return data

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = CliRunner().invoke(app, ["orient", "acme/lib"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    assert "CI is the set of checks GitHub runs on every pull request" in result.output
    assert "tox runs the tests in fresh, separate Python environments" in result.output
    assert "adds a 'Signed-off-by' line" in result.output
    read_first = result.output.split("Read first", 1)[1].split("\n\n", 1)[0]
    assert read_first.count("docs/C.rst") == 1
