from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.github.orientation import (
    active_committers,
    ci_test_commands,
    code_map,
    conventions,
    entry_points,
    find_paths,
    policy_quotes,
    rank_workflows,
    reading_plan,
)

NOW = datetime(2026, 10, 21, tzinfo=UTC)


def _tree(*paths: str) -> list[dict[str, Any]]:
    out = []
    for path in paths:
        kind = "tree" if path.endswith("/") else "blob"
        out.append({"path": path.rstrip("/"), "type": kind, "size": 100})
    return out


TREE = _tree(
    "README.md",
    "CONTRIBUTING.md",
    "ARCHITECTURE.md",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".github/",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/",
    ".github/workflows/tests.yml",
    ".github/workflows/release.yml",
    "lib/",
    "lib/pkg/",
    "lib/pkg/__init__.py",
    "lib/pkg/__main__.py",
    "lib/pkg/core.py",
    "lib/pkg/tests/",
    "lib/pkg/tests/test_core.py",
    "doc/",
    "doc/users/index.rst",
    "doc/users/guide.rst",
    "examples/",
    "examples/demo.py",
    "src/",
    "src/_ext.c",
    "tools/",
    "tools/release.sh",
)


def test_code_map_groups_top_level_directories_with_purpose_guesses() -> None:
    rows = code_map(TREE)
    by_name = {row["path"]: row for row in rows}
    assert by_name["lib"]["files"] == 4
    assert by_name["lib"]["purpose"] == "source"
    assert by_name["doc"]["purpose"] == "docs"
    assert by_name["examples"]["purpose"] == "examples"
    assert by_name["tools"]["purpose"] == "tooling"
    assert by_name["lib"]["main_extension"] == ".py"
    dirs = [r for r in rows if r["path"] != "."]
    assert dirs[0]["files"] >= dirs[-1]["files"]
    assert rows[-1]["path"] == "." and rows[-1]["files"] == 5


def test_find_paths_detects_docs_and_conventions_files() -> None:
    found = find_paths(TREE)
    assert found["architecture_docs"] == ["ARCHITECTURE.md"]
    assert found["codeowners"] == ".github/CODEOWNERS"
    assert found["pr_template"] == ".github/PULL_REQUEST_TEMPLATE.md"
    assert found["pre_commit"] is True
    assert found["workflows"] == [".github/workflows/release.yml", ".github/workflows/tests.yml"]
    assert found["test_dirs"] == ["lib/pkg/tests"]


def test_entry_points_from_tree_and_manifests() -> None:
    points = entry_points(
        TREE,
        pyproject='[project]\nname="pkg"\n[project.scripts]\npkg = "pkg.cli:app"\n',
        package_json=None,
    )
    assert any(p["path"] == "lib/pkg/__main__.py" for p in points)
    assert any(p["reason"].startswith("pyproject") and "pkg.cli:app" in p["reason"] for p in points)


def test_test_commands_from_workflow_run_lines() -> None:
    workflow = """
name: Tests
jobs:
  test:
    steps:
      - run: pip install -e .
      - name: Run
        run: |
          python -m pytest -rfEsXR -n auto \\
            lib
      - run: npm run lint
"""
    commands = ci_test_commands({".github/workflows/tests.yml": workflow})
    assert commands[0]["command"].startswith("python -m pytest -rfEsXR -n auto")
    assert commands[0]["source"] == ".github/workflows/tests.yml"
    assert all("pip install" not in c["command"] for c in commands)


def test_conventions_detects_dco_cla_and_commit_style() -> None:
    commits = [
        {"commit": {"message": f"feat(core): change {i}\n\nSigned-off-by: A <a@x>"}}
        for i in range(8)
    ]
    commits += [{"commit": {"message": "Fix typo"}}, {"commit": {"message": "docs: tidy"}}]
    result = conventions(
        commits,
        contributing="Please sign your commits with git commit -s (Developer Certificate of Origin).",
        pr_template="- [ ] Tests added\n- [ ] Docs updated\n## AI Disclosure\n",
        check_names=["DCO", "ci/test", "EasyCLA"],
        found={"commitlint": True, "pre_commit": True, "codeowners": ".github/CODEOWNERS"},
    )
    assert result["dco"]["required"] is True and "git commit -s" in result["dco"]["evidence"][0]
    assert result["cla"]["required"] is True
    assert result["conventional_commits"]["ratio"] >= 0.8
    assert result["pr_checklist_items"] == 2
    assert result["ai_disclosure_in_pr_template"] is True
    assert ".github/CODEOWNERS" in result["codeowners"]


def test_policy_quotes_pull_verbatim_sentences() -> None:
    quotes = policy_quotes(
        {
            "CONTRIBUTING.md": "Welcome! We do not assign issues; just open a PR. Please disclose any AI assistance in the PR description.",
            ".github/PULL_REQUEST_TEMPLATE.md": "Keep one PR at a time open. Thanks for contributing.",
        }
    )
    kinds = {q["kind"] for q in quotes}
    assert {"assignment", "ai", "pr_limit"} <= kinds
    assert any(q["source"] == "CONTRIBUTING.md" and "We do not assign" in q["text"] for q in quotes)


def test_active_committers_excludes_bots_and_counts() -> None:
    def commit(login: str | None, name: str, days: int, bot: bool = False) -> dict[str, Any]:
        return {
            "author": {"login": login, "type": "Bot" if bot else "User"} if login else None,
            "commit": {
                "author": {"name": name, "date": (NOW - timedelta(days=days)).isoformat()},
                "message": "x",
            },
        }

    commits = [commit("alice", "Alice", 3)] * 5 + [commit("bob", "Bob", 10)] * 2
    commits += [commit("dependabot[bot]", "dependabot", 1, bot=True)]
    commits += [commit(None, "Carol Offline", 4)]
    people = active_committers(commits)
    assert people[0] == {"login": "alice", "commits": 5}
    assert {"login": "Carol Offline", "commits": 1} in people
    assert not any("dependabot" in p["login"] for p in people)


def test_reading_plan_is_ordered_and_cites_paths() -> None:
    plan = reading_plan(
        found={
            "readme": "README.md",
            "contributing": "CONTRIBUTING.md",
            "architecture_docs": ["ARCHITECTURE.md"],
            "test_dirs": ["lib/pkg/tests"],
            "workflows": [".github/workflows/tests.yml"],
        },
        points=[{"path": "lib/pkg/__main__.py", "reason": "module entry point"}],
        example_pr={"number": 42, "url": "https://github.com/a/b/pull/42", "files": 2},
    )
    paths = [step["path"] for step in plan]
    assert paths[:3] == ["README.md", "CONTRIBUTING.md", "ARCHITECTURE.md"]
    assert "lib/pkg/__main__.py" in paths
    assert "lib/pkg/tests" in paths
    assert plan[-1]["path"].endswith("/pull/42")


def test_rank_workflows_prefers_test_pipelines() -> None:
    paths = [
        ".github/workflows/autoclose_comment.yml",
        ".github/workflows/cibuildwheel.yml",
        ".github/workflows/tests.yml",
        ".github/workflows/release.yml",
    ]
    assert rank_workflows(paths) == [
        ".github/workflows/tests.yml",
        ".github/workflows/cibuildwheel.yml",
    ]


def test_policy_quotes_skip_markdown_headings_and_checklists() -> None:
    quotes = policy_quotes(
        {
            "PR_TEMPLATE.md": "## PR summary\n## AI Disclosure\n- [ ] Use an expressive title\n"
            "We do not assign issues, so please just open a pull request.\n"
        }
    )
    assert len(quotes) == 1
    assert quotes[0]["text"].startswith("We do not assign issues")


def test_code_map_names_the_main_package_and_test_dirs_rank_by_test_files() -> None:
    tree = _tree(
        "sympy/",
        "sympy/core.py",
        "sympy/tests/",
        "sympy/tests/test_core.py",
        "sympy/tests/test_x.py",
        "doc/",
        "doc/testing/",
        "doc/testing/index.rst",
    )
    rows = {r["path"]: r for r in code_map(tree, repo_name="sympy")}
    assert rows["sympy"]["purpose"] == "source (main package)"
    assert find_paths(tree)["test_dirs"][0] == "sympy/tests"
