"""The pure orientation functions: code map, paths, entry points, CI commands and environment,
conventions, policy quotes, gates, and workflow ranking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.github.orientation import (
    active_committers,
    branch_gates,
    ci_environment,
    ci_install_commands,
    ci_test_commands,
    code_map,
    conventions,
    entry_points,
    find_paths,
    policy_quotes,
    rank_gate_workflows,
    rank_workflows,
    reading_plan,
    workflow_gates,
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
        pyproject='[project]\nname="pkg"\n[project.scripts]\npkg = "pkg.core:app"\n',
        package_json=None,
    )
    assert any(p["path"] == "lib/pkg/__main__.py" for p in points)
    # The module's real file, found under lib/: never the guess "pkg/core.py".
    assert points[0] == {
        "path": "lib/pkg/core.py",
        "reason": "pyproject.toml [project.scripts] pkg = pkg.core:app",
    }


def test_a_script_module_that_is_not_in_the_tree_is_not_listed() -> None:
    # MDAnalysis mdacli listed "mdacli/__main__.py", which does not exist: its code is
    # under src/. A manifest entry whose file cannot be found is dropped.
    points = entry_points(
        TREE,
        pyproject='[project]\nname="pkg"\n[project.scripts]\npkg = "pkg.missing:app"\n',
        package_json=None,
    )
    assert not any("pkg.missing" in p["reason"] for p in points)


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


def test_rank_workflows_reads_quality_gates_before_builds() -> None:
    # OWASP/threat-dragon (2026-10-21): the tests run in *-quality-gates.yaml, and
    # reading desktop-build.yaml instead left `orient` with no test command.
    names = ["desktop-build", "desktop-quality-gates", "docker-build", "housekeeping"]
    names += ["release", "server-quality-gates", "sboms", "vulnerability-scan"]
    paths = [f".github/workflows/{n}.yaml" for n in names]
    assert all("quality-gates" in p for p in rank_workflows(paths))


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


def test_codetour_from_orientation_pins_commit_and_orders_steps() -> None:
    from git_into_gsoc.github.orientation import codetour_from_orientation

    data = {
        "repo": "acme/lib",
        "as_of_commit": "abc123",
        "default_branch": "main",
        "code_map": [
            {"path": "lib", "files": 10, "purpose": "source", "purpose_is_guess": True},
            {"path": ".", "files": 3, "purpose": "project root", "purpose_is_guess": False},
        ],
        "test_commands": [{"command": "pytest -q", "source": ".github/workflows/ci.yml"}],
        "reading_plan": [
            {"path": "README.md", "why": "What the project is"},
            {"path": "tests", "why": "How behaviour is tested"},
            {"path": "https://github.com/acme/lib/pull/7", "why": "A small merged PR"},
        ],
        "docs": {"test_dirs": ["tests"]},
    }
    tour = codetour_from_orientation(data)
    assert tour["$schema"] == "https://aka.ms/codetour-schema"
    assert tour["title"].startswith("#1 - ")
    assert tour["ref"] == "abc123"
    kinds = [("file" in s, "directory" in s) for s in tour["steps"]]
    assert (tour["steps"][1]["file"], tour["steps"][1]["line"]) == ("README.md", 1)
    assert any(s.get("directory") == "tests" for s in tour["steps"])
    assert any(">> pytest -q" in s["description"] for s in tour["steps"])
    assert any("pull/7" in s["description"] for s in tour["steps"] if "file" not in s)
    assert kinds[0] == (False, False)  # the intro step is description only


def test_branch_gates_translate_rules_a_contributor_must_meet() -> None:
    rules = [
        {"type": "deletion"},
        {"type": "creation"},
        {"type": "required_signatures"},
        {"type": "required_linear_history"},
        {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
        {"type": "merge_queue", "parameters": {"merge_method": "SQUASH"}},
        {
            "type": "commit_message_pattern",
            "parameters": {"operator": "starts_with", "pattern": "[A-Z]+-", "name": "Ticket id"},
        },
        {"type": "required_status_checks", "parameters": {"required_status_checks": []}},
    ]
    gates = [g["gate"] for g in branch_gates(rules, branch="main")]
    assert gates == [
        "Commits must be signed (GPG or SSH); set up commit signing before you push",
        "Linear history: rebase on main instead of merging it into your branch",
        "Needs 1 approving review",
        "Merged through a merge queue (squash)",
        "Commit messages must starts with `[A-Z]+-` (Ticket id)",
    ]
    assert branch_gates([], branch="main") == []
    zero = [{"type": "pull_request", "parameters": {"required_approving_review_count": 0}}]
    assert branch_gates(zero, branch="main") == []


def test_workflow_gates_and_gate_workflow_ranking() -> None:
    paths = [
        ".github/workflows/ci.yml",
        ".github/workflows/lint-pr-title.yml",
        ".github/workflows/check-linked-issues.yml",
        ".github/workflows/release.yml",
    ]
    assert rank_gate_workflows(paths, skip=[".github/workflows/ci.yml"]) == [
        ".github/workflows/check-linked-issues.yml",
        ".github/workflows/lint-pr-title.yml",
    ]
    gates = workflow_gates(
        {
            ".github/workflows/lint-pr-title.yml": "steps:\n  - uses: amannn/action-semantic-pull-request@v5\n",
            ".github/workflows/check-linked-issues.yml": "uses: nearform-actions/github-action-check-linked-issues@v1\n",
            ".github/workflows/ci.yml": "run: pytest\n",
        }
    )
    assert {
        "gate": "The pull request title is checked against a format",
        "source": ".github/workflows/lint-pr-title.yml",
    } in gates
    assert {
        "gate": "Pull requests must reference an issue",
        "source": ".github/workflows/check-linked-issues.yml",
    } in gates
    assert len(gates) == 2


def test_ci_environment_reads_matrix_versions_services_and_runners() -> None:
    workflow = """
name: tests
on: [push]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.13", '3.12']
    services:
      postgres:
        image: postgres:16
        ports:
          - 5432:5432
      redis:
        image: "redis:7"
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: actions/setup-node@v4
        with:
          node-version:
            - 20
            - 22
      - run: pytest -q
"""
    env = ci_environment({".github/workflows/tests.yml": workflow})
    assert env["runtimes"] == [
        {
            "name": "Node.js",
            "versions": ["20", "22"],
            "most_used": None,
            "source": ".github/workflows/tests.yml",
        },
        {
            "name": "Python",
            "versions": ["3.11", "3.12", "3.13"],
            "most_used": None,
            "source": ".github/workflows/tests.yml",
        },
    ]
    assert [(s["name"], s["image"]) for s in env["services"]] == [
        ("postgres", "postgres:16"),
        ("redis", "redis:7"),
    ]
    assert env["runners"] == ["ubuntu-latest", "windows-latest"]
    assert ci_environment({}) == {"runtimes": [], "services": [], "runners": []}


def test_changelog_requirement_from_fragments_or_contributing() -> None:
    from git_into_gsoc.github.orientation import conventions, find_paths

    tree = [
        {"path": "changelog", "type": "tree"},
        {"path": "changelog/1234.bugfix.rst", "type": "blob"},
        {"path": "changelog/1240.feature.rst", "type": "blob"},
        {"path": "src", "type": "tree"},
    ]
    found = find_paths(tree)
    assert found["news_fragments"] == "changelog"
    rules = conventions([], contributing="", pr_template="", check_names=[], found=found)
    assert rules["changelog"] == {
        "expected": True,
        "evidence": ["changelog/ holds one entry per change"],
    }
    text_only = conventions(
        [],
        contributing="Please add an entry to CHANGES.rst for every user-facing change.",
        pr_template="",
        check_names=[],
        found=find_paths([]),
    )
    assert text_only["changelog"]["expected"]
    assert text_only["changelog"]["evidence"] == [
        "CONTRIBUTING asks contributors to update 'CHANGES.rst'"
    ]
    none = conventions([], contributing="", pr_template="", check_names=[], found=find_paths([]))
    assert none["changelog"] == {"expected": False, "evidence": []}


def test_release_note_folders_are_not_mistaken_for_news_fragments() -> None:
    from git_into_gsoc.github.orientation import find_paths

    numpy_like = [
        {"path": "doc", "type": "tree"},
        {"path": "doc/changelog", "type": "tree"},
        {"path": "doc/changelog/1.26.0-changelog.rst", "type": "blob"},
        {"path": "doc/changelog/2.0.0-changelog.rst", "type": "blob"},
        {"path": "doc/release", "type": "tree"},
        {"path": "doc/release/upcoming_changes", "type": "tree"},
        {"path": "doc/release/upcoming_changes/26000.improvement.rst", "type": "blob"},
    ]
    assert find_paths(numpy_like)["news_fragments"] == "doc/release/upcoming_changes"
    notes_only = [
        {"path": "changelog", "type": "tree"},
        {"path": "changelog/v1.0.md", "type": "blob"},
        {"path": "changelog/v2.0.md", "type": "blob"},
    ]
    assert find_paths(notes_only)["news_fragments"] is None


def test_release_notes_in_the_pr_template_count() -> None:
    from git_into_gsoc.github.orientation import conventions, find_paths

    rules = conventions(
        [],
        contributing="",
        pr_template="#### Release Notes\n<!-- BEGIN RELEASE NOTES -->\n* solvers\n",
        check_names=[],
        found=find_paths([]),
    )
    assert rules["changelog"]["expected"]
    assert rules["changelog"]["evidence"] == ["The PR template has a 'Release Notes' section"]


def test_generated_changelogs_are_not_a_request() -> None:
    from git_into_gsoc.github.orientation import changelog_request

    stdlib_like = (
        "When writing commit messages, follow the style guide. Adherence to project commit "
        "conventions is necessary for project automation (e.g., automatic changelog and "
        "release notes generation)."
    )
    assert changelog_request(stdlib_like, "") is None
    assert changelog_request("The changelog is maintained by the release team.", "") is None
    assert (
        changelog_request("Please add a news entry for every user-facing change.", "")
        == "CONTRIBUTING asks contributors to update 'news entry'"
    )


def test_ci_install_commands_skip_installer_upgrades() -> None:
    workflow = (
        "jobs:\n  t:\n    steps:\n"
        "      - run: python -m pip install --upgrade pip setuptools\n"
        "      - run: |\n          pip install -r requirements-dev.txt\n          npm ci\n"
        "      - run: pytest\n"
    )
    commands = [c["command"] for c in ci_install_commands({"ci.yml": workflow})]
    assert commands == ["pip install -r requirements-dev.txt", "npm ci"]


def test_a_matrix_toolchain_that_is_not_rust_is_not_reported_as_rust() -> None:
    # ArduPilot's test_ccache.yml (2026-10-21): `toolchain: [` opens a flow list of
    # firmware targets on the next lines; orient printed "CI uses Rust [".
    ardupilot = (
        "jobs:\n  build:\n    strategy:\n      matrix:\n"
        "        toolchain: [\n            chibios,\n        ]\n        gcc: [10]\n"
    )
    rust = "jobs:\n  t:\n    steps:\n      - uses: dtolnay/rust-toolchain@v1\n        with:\n"
    rust += "          toolchain: [stable, nightly]\n"
    env = ci_environment({"a.yml": ardupilot, "r.yml": rust})
    runtimes = {r["name"]: r["versions"] for r in env["runtimes"]}
    assert runtimes == {"Rust": ["nightly", "stable"]}


# Excerpt of OWASP/threat-dragon's contributing.md (2026-10-21): hard-wrapped
# sentences, list items with indented continuations, and markdown links.
THREAT_DRAGON = """\
* ensure that [unit tests][unit] have been extended or created for any code changes
* the use of generative AI is not prohibited but must be declared in the [pull request](#use-of-ai-for-coding)
* the main repository only accepts [signed commits][signed-commits], otherwise the contribution will be rejected

7. if coding using [generative AI](#use-of-ai-for-coding);
  you must understand fully the changes and keep sprawl to a minimum
8. ensure the GitHub Actions are passing; a [local script][pr-script] is available
  to help debug if you need it.

Threat Dragon is a project that is used globally by many organizations;
therefore the code base has to be coherent and functional.
Avoid using generative AI for any issues, pull requests, comments and discussions.

If it is genuinely helpful to use generative AI
then it **must** be declared for pull requests or when creating / commenting on issues.

* **Do not submit an AI-generated PR you haven't personally understood and tested**, as this
  wastes maintainers' time.
Note that you should _not_ claim an issue while you are iterating; snake_case_names stay.
"""


def test_policy_quotes_join_wrapped_lines_and_drop_markdown() -> None:
    texts = [q["text"] for q in policy_quotes({"contributing.md": THREAT_DRAGON})]
    assert (
        "If it is genuinely helpful to use generative AI then it must be declared for pull "
        "requests or when creating / commenting on issues."
    ) in texts
    assert (
        "if coding using generative AI; you must understand fully the changes and keep "
        "sprawl to a minimum"
    ) in texts
    assert (
        "the use of generative AI is not prohibited but must be declared in the pull request"
        in texts
    )
    assert "If it is genuinely helpful to use generative AI" not in texts
    assert not any("](" in t or "*" in t or "][" in t for t in texts)
    assert (
        "Note that you should not claim an issue while you are iterating; snake_case_names stay."
        in texts
    )


def test_policy_quotes_drop_markdown_escapes() -> None:
    # ArduPilot: "simply work on it\\*" printed with the backslash.
    text = "We typically do not assign issues, simply work on it\\* and open a PR.\n"
    quotes = [q["text"] for q in policy_quotes({"CONTRIBUTING.md": text})]
    assert quotes == ["We typically do not assign issues, simply work on it* and open a PR."]


ARDUPILOT_WORKFLOWS = [
    f".github/workflows/{n}.yml"
    for n in (
        "test_branch_conventions",
        "test_ccache",
        "test_chibios",
        "test_coverage",
        "test_location_ratchet",
        "test_size",
        "test_sitl_copter",
        "test_unit_tests",
        "workflows_lint",
    )
]


def test_unit_test_workflows_rank_first_and_convention_checks_last() -> None:
    # A simulated run: orient read test_branch_conventions.yml as "what CI runs".
    ranked = rank_workflows(ARDUPILOT_WORKFLOWS, limit=3)
    assert ranked[0].endswith("test_unit_tests.yml")
    assert not any("conventions" in p or "size" in p or "ratchet" in p for p in ranked)


def test_ci_commands_include_autotest_and_unittest_scripts() -> None:
    workflow = (
        "jobs:\n  t:\n    steps:\n      - run: |\n"
        "          Tools/autotest/unittest/extract_param_defaults_unittest.py\n"
        "          Tools/autotest/autotest.py test.CAN --debug\n"
    )
    commands = [c["command"] for c in ci_test_commands({"t.yml": workflow})]
    assert "Tools/autotest/autotest.py test.CAN --debug" in commands
    assert any(c.endswith("_unittest.py") for c in commands)


def test_test_folders_that_ci_runs_come_first() -> None:
    from git_into_gsoc.github.orientation import PURPOSES, ci_test_dirs_first

    dirs = ["Tools/renode/tests", "libraries/AP_Math/tests", "Tools/autotest"]
    texts = {"t.yml": "run: Tools/autotest/autotest.py test.CAN --debug"}
    assert ci_test_dirs_first(dirs, texts) == [
        "Tools/autotest",
        "Tools/renode/tests",
        "libraries/AP_Math/tests",
    ]
    assert ci_test_dirs_first(dirs, {}) == dirs
    assert "autotest" in PURPOSES["tests"]


def test_ci_versions_put_the_usual_one_first_and_other_implementations_last() -> None:
    # sympy/sympy: one job checks the Python 2 error message on pypy2.7, and orient
    # printed "CI uses Python pypy2.7, 3.10, ..." as if Python 2 were supported.
    job = "    steps:\n      - uses: actions/setup-python@v6\n        with:\n"
    workflow = "jobs:\n"
    for version in ("'3.14'", "'3.14'", "'3.14'", "'3.13'", "'pypy2.7'"):
        workflow += f"  j{len(workflow)}:\n{job}          python-version: {version}\n"
    workflow += "  m:\n    strategy:\n      matrix:\n        python-version: ['3.10', '3.11', 'pypy-3.11']\n"
    python = ci_environment({"runtests.yml": workflow})["runtimes"][0]
    assert python["versions"] == ["3.10", "3.11", "3.13", "3.14", "pypy2.7", "pypy-3.11"]
    assert python["most_used"] == "3.14"


def test_ci_install_commands_skip_pip_upgrades_and_prefer_the_common_one() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands

    # sympy/sympy runtests.yml (2026-10-21), shortened.
    workflow = (
        "jobs:\n  a:\n    steps:\n      - run: python -m pip install --upgrade pip setuptools\n"
        "      - run: pip install -r requirements-dev.txt\n      - run: pip install .\n"
        "  b:\n    steps:\n      - run: python -m pip install --upgrade pip\n"
        "      - run: pip install -r requirements-dev.txt\n      - run: pytest -n auto\n"
    )
    commands = [c["command"] for c in ci_install_commands({"runtests.yml": workflow})]
    assert commands[0] == "pip install -r requirements-dev.txt"
    assert not any("--upgrade pip" in c for c in commands)
    node = "jobs:\n  t:\n    steps:\n      - run: npm ci\n      - run: npm test\n"
    assert [c["command"] for c in ci_install_commands({"n.yml": node})] == ["npm ci"]


def test_automation_workflows_are_not_read_as_the_test_setup() -> None:
    # CircuitVerse/Interactive-Book: orient said "CI uses Node.js 16" from
    # issue-assign-to-contributor.yml, a bot that assigns issues.
    paths = [f".github/workflows/{n}.yml" for n in ("deploy", "issue-assign-to-contributor")]
    paths += [".github/workflows/language.yml"]
    assert rank_workflows(paths, limit=3)[-1].endswith("issue-assign-to-contributor.yml")


def test_installing_npm_itself_is_not_the_project_install() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands

    # OWASP/threat-dragon: the draft listed "npm install --global npm@11.18.0".
    workflow = (
        "jobs:\n  t:\n    steps:\n      - run: npm install --global npm@11.18.0\n"
        "      - run: npm clean-install\n      - run: npm run test:unit\n"
    )
    assert [c["command"] for c in ci_install_commands({"t.yml": workflow})] == ["npm clean-install"]


def test_ci_install_commands_never_suggest_a_system_wide_install() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands

    # OSGeo/gdal code_checks.yml (2026-10-22): a PR draft for a GDAL issue said to run
    # this "as CI does", to install a citation checker with sudo.
    gdal = (
        "jobs:\n  cff:\n    steps:\n      - run: |\n"
        "          PYTHON_CMD=python3 && sudo $PYTHON_CMD -m pip install "
        "--break-system-packages cffconvert\n"
        "          PYTHON_CMD=python3 && $PYTHON_CMD -m pip install cmake-format pyyaml\n"
        "          cffconvert --validate\n"
    )
    assert ci_install_commands({"code_checks.yml": gdal}) == []


def test_tool_installs_count_only_where_the_tests_run_or_the_project_installs() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands

    tests = "jobs:\n  t:\n    steps:\n      - run: pip install tox\n      - run: tox -e py\n"
    lint = "jobs:\n  l:\n    steps:\n      - run: pip install codespell\n      - run: codespell\n"
    build = (
        "jobs:\n  b:\n    steps:\n      - run: pip install cython numpy\n"
        "      - run: pip install -e . --no-build-isolation\n"
    )
    commands = ci_install_commands({"lint.yml": lint, "tests.yml": tests, "build.yml": build})
    # In workflow order, so a build dependency still comes before the project.
    assert [c["command"] for c in commands] == [
        "pip install tox",
        "pip install cython numpy",
        "pip install -e . --no-build-isolation",
    ]
    node = "jobs:\n  t:\n    steps:\n      - run: npm install --no-audit\n      - run: npm install -D eslint\n"
    assert [c["command"] for c in ci_install_commands({"n.yml": node})] == [
        "npm install --no-audit",
        "npm install -D eslint",
    ]


def test_a_command_continued_over_several_lines_is_read_whole() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands, ci_test_commands

    # MDAnalysis gh-ci-cron.yaml (2026-10-22), shortened.
    workflow = (
        "jobs:\n  t:\n    steps:\n      - run: |\n"
        "          python -m pip install        \\\n"
        '            "cython>=0.28"           \\\n'
        "            packaging \\\n"
        "            # Base deps\n"
        "          python -m pip install pytest-xdist pytest-timeout\n"
        "          python -m pip install --no-build-isolation -v -e ./package\n"
        "      - run: |\n          pytest -n auto \\\n            --timeout=200 testsuite/\n"
    )
    assert [c["command"] for c in ci_install_commands({"cron.yml": workflow})] == [
        'python -m pip install "cython>=0.28" packaging',
        "python -m pip install pytest-xdist pytest-timeout",
        "python -m pip install --no-build-isolation -v -e ./package",
    ]
    assert [c["command"] for c in ci_test_commands({"cron.yml": workflow})] == [
        "pytest -n auto --timeout=200 testsuite/"
    ]
    long = "jobs:\n  t:\n    steps:\n      - run: pip install -r requirements.txt " + "pkg " * 60
    (command,) = [c["command"] for c in ci_install_commands({"l.yml": long + "\n"})]
    assert len(command) <= 160 and command.endswith(" pkg ...")


def test_a_yarn_script_is_a_test_command_not_an_install() -> None:
    from git_into_gsoc.github.orientation import ci_install_commands, ci_test_commands

    # Rocket.Chat's ci-test-unit.yml, Joplin's ui-tests.yml, and Zulip's zulip-ci.yml
    # (2026-10-22).
    workflow = (
        "jobs:\n  t:\n    steps:\n      - run: yarn\n      - run: yarn install --frozen-lockfile\n"
        "      - run: yarn build\n      - run: yarn test:e2e --shard=1/2\n"
        "      - run: yarn test-ui-ios\n      - run: yarn testunit --concurrency=1\n"
        "      - run: ./tools/test-help-documentation --skip-external-links\n"
    )
    assert [c["command"] for c in ci_install_commands({"t.yml": workflow})] == [
        "yarn",
        "yarn install --frozen-lockfile",
    ]
    assert [c["command"] for c in ci_test_commands({"t.yml": workflow})] == [
        "yarn test:e2e --shard=1/2",
        "yarn test-ui-ios",
        "yarn testunit --concurrency=1",
        "./tools/test-help-documentation --skip-external-links",
    ]


def test_a_standard_test_runner_comes_before_a_project_script() -> None:
    from git_into_gsoc.github.orientation import ci_test_commands

    # SymPy (2026-10-22): bin/test quality runs only the code-quality tests.
    workflow = (
        "jobs:\n  q:\n    steps:\n      - run: bin/test quality\n"
        "  t:\n    steps:\n      - run: pytest -n auto\n"
    )
    assert [c["command"] for c in ci_test_commands({"t.yml": workflow})] == [
        "pytest -n auto",
        "bin/test quality",
    ]
    # A path that only starts like a test script runs no tests.
    other = "jobs:\n  d:\n    steps:\n      - run: |\n"
    for line in ("scripts/testdata/gen.sh", "scripts/testing-setup.sh", "cp scripts/test-data/a ."):
        assert ci_test_commands({"d.yml": other + f"          {line}\n"}) == [], line
    assert [
        c["command"]
        for c in ci_test_commands({"d.yml": other + "          bash scripts/run-tests.sh\n"})
    ] == ["bash scripts/run-tests.sh"]


def test_orient_says_when_merged_work_goes_to_another_branch() -> None:
    from git_into_gsoc.github.orientation import work_branch

    # metabrainz/listenbrainz-android (2026-10-22): recent outside pull requests merged
    # into `cmp`, a Compose Multiplatform migration, while `main` sat still.
    merged = [{"base": {"ref": "cmp"}}] * 5 + [{"base": {"ref": "main"}}] * 2
    found = work_branch(merged, default="main")
    assert found is not None and found["branch"] == "cmp"
    assert found["note"].startswith(
        "5 of the last 7 merged pull requests went to `cmp`, not `main`"
    )
    # Most work on the default branch, or too few pull requests to tell: nothing to say.
    assert work_branch([{"base": {"ref": "main"}}] * 6, default="main") is None
    assert work_branch([{"base": {"ref": "cmp"}}] * 3, default="main") is None
    even = (
        [{"base": {"ref": "cmp"}}] * 2
        + [{"base": {"ref": "dev"}}] * 2
        + [{"base": {"ref": "main"}}] * 2
    )
    assert work_branch(even, default="main") is None
