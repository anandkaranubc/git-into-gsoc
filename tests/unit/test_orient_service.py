from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()
API = "https://api.github.com/repos/acme/lib"
NOW = datetime.now(UTC)


def _iso(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _tree_entry(path: str, kind: str = "blob") -> dict[str, Any]:
    return {"path": path, "type": kind, "size": 10, "sha": "x"}


def _mock_repo(router: respx.MockRouter) -> None:
    router.get(API).mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "acme/lib",
                "html_url": "https://github.com/acme/lib",
                "description": "A library",
                "default_branch": "main",
                "stargazers_count": 300,
                "license": {"spdx_id": "MIT"},
                "pushed_at": _iso(1),
            },
        )
    )
    router.get(f"{API}/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "abc123def456",
                "truncated": False,
                "tree": [
                    _tree_entry("README.md"),
                    _tree_entry("CONTRIBUTING.md"),
                    _tree_entry("pyproject.toml"),
                    _tree_entry(".github", "tree"),
                    _tree_entry(".github/CODEOWNERS"),
                    _tree_entry(".github/workflows", "tree"),
                    _tree_entry(".github/workflows/ci.yml"),
                    _tree_entry(".github/workflows/check-contribution.yaml"),
                    _tree_entry("src", "tree"),
                    _tree_entry("src/lib", "tree"),
                    _tree_entry("src/lib/__main__.py"),
                    _tree_entry("src/lib/core.py"),
                    _tree_entry("tests", "tree"),
                    _tree_entry("tests/test_core.py"),
                ],
            },
        )
    )
    router.get(f"{API}/rules/branches/main").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {
                    "type": "pull_request",
                    "parameters": {
                        "required_approving_review_count": 2,
                        "require_code_owner_review": True,
                        "dismiss_stale_reviews_on_push": True,
                    },
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": True,
                        "required_status_checks": [{"context": "ci / test"}],
                    },
                },
            ],
        )
    )
    router.get(f"{API}/languages").mock(
        return_value=httpx.Response(200, json={"Python": 900, "C": 100})
    )
    router.get(f"{API}/community/profile").mock(
        return_value=httpx.Response(200, json={"files": {}})
    )
    router.get(f"{API}/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "author": {"login": "maintainer", "type": "User"},
                    "commit": {
                        "message": "feat(core): add thing\n\nSigned-off-by: M <m@x>",
                        "author": {"date": _iso(2)},
                    },
                }
            ]
            * 6,
        )
    )
    router.get(f"{API}/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 7,
                    "html_url": "https://github.com/acme/lib/pull/7",
                    "title": "Fix docs link",
                    "merged_at": _iso(3),
                    "author_association": "CONTRIBUTOR",
                    "user": {"login": "newbie", "type": "User"},
                    "head": {"sha": "deadbeef"},
                }
            ],
        )
    )
    router.get(f"{API}/assignees").mock(return_value=httpx.Response(200, json=[]))
    router.get(f"{API}/pulls/7/files").mock(
        return_value=httpx.Response(
            200, json=[{"filename": "src/lib/core.py"}, {"filename": "tests/test_core.py"}]
        )
    )
    router.get(f"{API}/commits/deadbeef/check-runs").mock(
        return_value=httpx.Response(
            200, json={"check_runs": [{"name": "DCO"}, {"name": "ci / test"}]}
        )
    )
    router.get(f"{API}/commits/deadbeef/status").mock(
        return_value=httpx.Response(200, json={"statuses": [{"context": "EasyCLA"}]})
    )
    raw = {
        "CONTRIBUTING.md": "Join us on Zulip. We do not assign issues; open a PR. Sign your commits with git commit -s.",
        "pyproject.toml": '[project]\nname = "lib"\n[project.scripts]\nlib = "lib.core:app"\n',
        ".github/CODEOWNERS": "src/lib/ @maintainer @other\n",
        ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: pip install -e .\n      - run: pytest -q\n",
        ".github/workflows/check-contribution.yaml": (
            "on: pull_request_target\njobs:\n  check:\n    steps:\n      - uses: org/check@v1\n"
            "        with:\n          check_for: issue_assignee, issue_reference\n"
            "          close_on: issue_assignee, issue_reference\n"
        ),
    }
    for path, text in raw.items():
        router.get(f"{API}/contents/{path}").mock(return_value=httpx.Response(200, text=text))


@respx.mock
def test_orient_repo_builds_facts_and_paths() -> None:
    _mock_repo(respx)
    data = GSoCToolkit().orient_repo("https://github.com/acme/lib")
    assert data["as_of_commit"] == "abc123def456"
    assert data["languages"][0] == {"name": "Python", "share": 90}
    assert {row["path"] for row in data["code_map"]} >= {"src", "tests", ".github"}
    assert data["test_commands"][0]["command"] == "pytest -q"
    assert any(p["path"] == "src/lib/core.py" for p in data["entry_points"])
    assert data["maintainers"]["active_committers_90d"][0]["login"] == "maintainer"
    assert data["maintainers"]["codeowners"][0]["owners"] == "@maintainer @other"
    rules = data["conventions"]
    assert rules["dco"]["required"] and rules["cla"]["required"]
    assert rules["conventional_commits"]["expected"]
    gates = [g["gate"] for g in rules["gates"]]
    assert (
        "Needs 2 approving reviews including a code owner; pushing new commits dismisses earlier approvals"
        in gates
    )
    assert "Required checks must pass: ci / test" in gates
    assert "Your branch must be up to date with main before it can merge" in gates
    assert any(
        g["gate"].startswith("Pull requests must reference an issue that is assigned to the author")
        and g["source"] == ".github/workflows/check-contribution.yaml"
        for g in rules["gates"]
    )
    assert not any("delet" in g or "force" in g for g in gates)
    assert data["test_commands"][0]["source"] == ".github/workflows/ci.yml"
    assert any(q["kind"] == "assignment" for q in data["policies"])
    assert data["channels"] == ["Zulip"]
    assert data["example_pr"]["number"] == 7 and data["example_pr"]["touches_tests"]
    assert data["reading_plan"][0]["path"] == "README.md"
    assert data["reading_plan"][-1]["path"].endswith("/pull/7")


@respx.mock
def test_cli_orient_renders_sections() -> None:
    _mock_repo(respx)
    result = runner.invoke(app, ["orient", "acme/lib"])
    assert result.exit_code == 0, result.output
    for needle in (
        "Code map",
        "Entry points",
        "pytest -q",
        "Who writes the code",
        "Before you open a PR",
        "Read in this order",
    ):
        assert needle in result.stdout


@respx.mock
def test_cli_orient_writes_a_codetour_file(tmp_path: Path) -> None:
    _mock_repo(respx)
    target = tmp_path / "gsoc.tour"
    result = runner.invoke(app, ["orient", "acme/lib", "--codetour", str(target)])
    assert result.exit_code == 0, result.output
    tour = json.loads(target.read_text())
    assert tour["ref"] == "abc123def456"
    assert any(s.get("file") == "README.md" for s in tour["steps"])
    assert "Wrote the CodeTour file" in result.stdout


def test_example_pr_skips_authors_who_can_be_assigned_issues(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # ArduPilot (2026-10-21): orient called a PR by @khancyr "a recently merged small PR
    # from an outside contributor"; GitHub marks every merged author CONTRIBUTOR.
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "list_assignees", lambda o, r: frozenset({"khancyr"}))
    monkeypatch.setattr(
        toolkit.github, "list_pull_files", lambda o, r, n: [{"filename": "src/a.py"}]
    )

    def pull(number: int, login: str) -> dict[str, object]:
        return {
            "number": number,
            "html_url": f"https://github.com/a/b/pull/{number}",
            "title": "t",
            "user": {"login": login},
            "author_association": "CONTRIBUTOR",
        }

    example = toolkit._example_outsider_pr("a", "b", [pull(1, "khancyr"), pull(2, "newcomer")])
    assert example is not None and example["author"] == "newcomer"
