"""Naming the likely cause of a failed setup or test run."""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.diagnose import diagnose_output
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()


def _ids(report: dict) -> list[str]:
    return [c["id"] for c in report["causes"]]


def test_missing_module_with_ci_context() -> None:
    output = """
Traceback (most recent call last):
  File "/home/me/proj/tests/test_core.py", line 3, in <module>
    import numpy
ModuleNotFoundError: No module named 'numpy'
"""
    ci = {
        "runtimes": [
            {"name": "Python", "versions": ["3.11", "3.13"], "source": ".github/workflows/ci.yml"}
        ],
        "services": [],
        "runners": ["ubuntu-latest"],
        "test_commands": [{"command": "pytest -q", "source": ".github/workflows/ci.yml"}],
    }
    report = diagnose_output(output, ci=ci)
    assert _ids(report) == ["missing_module"]
    cause = report["causes"][0]
    assert cause["name"] == "numpy" and cause["line"] == 5
    assert cause["quote"] == "ModuleNotFoundError: No module named 'numpy'"
    assert "CI uses Python 3.11, 3.13 (.github/workflows/ci.yml)" in report["ci"]
    assert "CI runs: pytest -q (.github/workflows/ci.yml)" in report["ci"]
    assert report["summary"].startswith("Most likely: A dependency is not installed")


def test_environment_causes_outrank_the_test_failures_they_cause() -> None:
    output = """
E   psycopg.OperationalError: connection failed: Connection refused
        Is the server running on that host and accepting TCP/IP connections?
FAILED tests/test_db.py::test_insert - psycopg.OperationalError
=== 3 failed, 10 passed in 2.1s ===
"""
    ci = {
        "runtimes": [],
        "services": [{"name": "postgres", "image": "postgres:16", "source": "ci.yml"}],
        "runners": [],
        "test_commands": [],
    }
    report = diagnose_output(output, ci=ci)
    assert _ids(report) == ["service_not_running"]
    assert "CI starts these services for the tests: postgres (postgres:16)" in report["ci"]


def test_each_family_is_recognised() -> None:
    samples = {
        "runtime_version": "ERROR: Package 'proj' requires a different Python: 3.9.6 not in '>=3.11'",
        "compiler_or_headers": "error: Microsoft Visual C++ 14.0 or greater is required.",
        "missing_env_var": "KeyError: 'GITHUB_TOKEN'",
        "command_not_found": "bash: make: command not found",
        "permission": "ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied",
        "network": "pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool",
        "port_in_use": "OSError: [Errno 48] Address already in use",
        "lockfile": "npm ERR! `npm ci` can only install packages when your package.json and package-lock.json are in sync",
        "out_of_memory": "FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory",
        "test_failure": "FAILED tests/test_parser.py::test_empty - AssertionError: assert [] == None",
    }
    for expected, line in samples.items():
        assert _ids(diagnose_output(line))[:1] == [expected], (
            expected,
            _ids(diagnose_output(line)),
        )
    assert diagnose_output("KeyError: 'GITHUB_TOKEN'")["causes"][0]["name"] == "GITHUB_TOKEN"


def test_unknown_output_points_to_asking_well() -> None:
    report = diagnose_output("Something odd happened.\nexit status 3")
    assert report["causes"] == []
    assert "draft question" in report["summary"]


@respx.mock
def test_service_reads_ci_and_cli_reads_stdin() -> None:
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(200, json={"full_name": "acme/lib", "default_branch": "main"})
    )
    respx.get(f"{api}/git/trees/main").mock(
        return_value=httpx.Response(
            200, json={"tree": [{"path": ".github/workflows/tests.yml", "type": "blob"}]}
        )
    )
    respx.get(f"{api}/contents/.github/workflows/tests.yml").mock(
        return_value=httpx.Response(
            200,
            text="jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: python -m pip install -e .[test]\n      - run: pytest -q\n",
        )
    )
    report = GSoCToolkit().diagnose("ModuleNotFoundError: No module named 'lib'", repo="acme/lib")
    assert report["repo"] == "acme/lib"
    assert "CI uses Python 3.12 (.github/workflows/tests.yml)" in report["ci"]
    assert (
        "CI installs with: python -m pip install -e .[test] (.github/workflows/tests.yml)"
        in report["ci"]
    )
    result = runner.invoke(app, ["diagnose", "-"], input="bash: tox: command not found\n")
    assert result.exit_code == 0, result.output
    assert "command not found" in result.output and "Install the tool" in result.output


def test_cli_reads_a_utf16_log_from_windows_powershell(tmp_path) -> None:
    log = tmp_path / "log.txt"
    log.write_text("ModuleNotFoundError: No module named 'numpy'\r\n", encoding="utf-16")
    result = runner.invoke(app, ["diagnose", str(log)])
    assert result.exit_code == 0, result.output
    assert "missing module" in result.output and "numpy" in result.output
    missing = runner.invoke(app, ["diagnose", str(tmp_path / "nope.txt")])
    assert missing.exit_code != 0 and "Cannot read" in missing.output


def test_a_stale_lock_file_gets_a_way_forward() -> None:
    # A real run on ruxailab/web-eye-tracker-front: `npm ci` refused; `npm install` built.
    line = (
        "npm error `npm ci` can only install packages when your package.json and package-lock.json"
    )
    cause = diagnose_output(line + " or npm-shrinkwrap.json are in sync.")["causes"][0]
    advice = " ".join(str(v) for v in cause.values())
    assert "npm install" in advice and "git checkout -- package-lock.json" in advice


def test_style_checks_are_named_with_the_line_that_failed() -> None:
    samples = [
        "AssertionError: File contains trailing whitespace: sympy/core/add.py, line 445.",
        "src/app.py:3:10: W291 trailing whitespace",
        "src/app.py:12:80: E501 line too long (88 > 79 characters)",
        "src/app.py:3:0: C0303: Trailing whitespace (trailing-whitespace)",
        "W293 [*] Blank line contains whitespace",
        "[*] 2 fixable with the `--fix` option.",
        "would reformat src/app.py",
        "1 file would be reformatted, 12 files would be left unchanged.",
        "ERROR: src/app.py Imports are incorrectly sorted and/or formatted.",
        "trim trailing whitespace.................................................Failed",
        "✖ 3 problems (3 errors, 0 warnings)",
        "[warn] Code style issues found in the above file. Run Prettier with --write to fix.",
        "main.go:3: File is not `gofmt`-ed with `-s` (gofmt)",
        "Diff in /home/runner/work/app/src/main.rs at line 3:",
        "src/a.c:3:10: error: code should be clang-formatted [-Wclang-format-violations]",
        "1 file inspected, 2 offenses detected, 2 offenses autocorrectable",
    ]
    for line in samples:
        assert _ids(diagnose_output(line)) == ["style_check"], line
    # A hook that runs tests or a type checker is not a style check.
    for line in ("pytest.................................Failed", "mypy.........Failed"):
        assert "style_check" not in _ids(diagnose_output(line)), line
    # git's warning while it applies a patch is not a check that failed. scikit-learn's
    # Pyodide build prints one for a patch it applies to a tool it downloads.
    assert (
        diagnose_output("emsdk/patches/0003-dylink.patch:38: trailing whitespace.")["causes"] == []
    )


def test_a_style_check_run_as_a_test_is_not_also_a_failing_test() -> None:
    # SymPy's code-quality check is a test, so pytest reports it like any other failure.
    # Lines as `gh run view --log` prints them: job, step, timestamp, then the output.
    prefix = "Slow Tests\tUNKNOWN STEP\t2026-10-22T06:08:24.3039166Z "
    output = "\n".join(
        prefix + line
        for line in [
            "    def test_files():",
            "          o no lines contains a trailing whitespace",
            "E               AssertionError: File contains trailing whitespace: "
            "/home/runner/work/sympy/sympy/sympy/parsing/autolev/_listener_autolev_antlr.py, "
            "line 445.",
            "sympy/testing/tests/test_code_quality.py:238: AssertionError",
            "FAILED sympy/testing/tests/test_code_quality.py::test_files - AssertionError: "
            "File contains trailing whitespace: /home/runner/work/sympy/sympy/sympy/parsing/a.py",
            "= 1 failed, 227 passed, 3 skipped in 1793.63s (0:29:53) =",
        ]
    )
    report = diagnose_output(output)
    assert _ids(report) == ["style_check"]
    cause = report["causes"][0]
    # The failure itself, not the test's description of what it checks, and the line
    # number survives because the CI prefix is gone.
    assert cause["line"] == 3 and cause["quote"].endswith("_listener_autolev_antlr.py, line 445.")
    assert report["summary"].startswith("Most likely: A style check failed")

    # Another test failing in the same run still counts, quoted by the line naming it.
    other = (
        "FAILED sympy/parsing/tests/test_autolev.py::test_rule_tests - "
        "AssertionError: mismatch in ruletest1 in line no: 3"
    )
    report = diagnose_output(output + "\n" + prefix + other)
    assert _ids(report) == ["style_check", "test_failure"]
    assert report["causes"][1]["quote"] == other and report["causes"][1]["line"] == 7


def test_a_style_check_does_not_hide_an_environment_cause() -> None:
    output = (
        "ModuleNotFoundError: No module named 'numpy'\nsrc/a.py:1:1: F401 'os' imported but unused"
    )
    assert _ids(diagnose_output(output)) == ["missing_module", "style_check"]


def test_ci_logs_are_read_without_their_prefixes_and_colours() -> None:
    # Apache Airflow's static checks (2026-10-22): prek prints the failed hook in colour,
    # and `gh run view --log` writes the escape character as "^[".
    line = (
        "CI image checks / Static checks\tUNKNOWN STEP\t2026-10-22T04:05:58.9869118Z "
        "^[[2m  ^[[0mCompile / format / lint UI^[[32m..........^[[39m^[[31;7mFailed^[[0m"
    )
    cause = diagnose_output(line)["causes"][0]
    assert cause["id"] == "style_check"
    assert cause["quote"] == "Compile / format / lint UI..........Failed"


def test_a_passing_test_is_not_evidence() -> None:
    # Django's test run (2026-10-22): a passing test's name said "permission denied",
    # and the failing test was reported by unittest as "ERROR: test_... (...)".
    output = """
user is not authenticated after a backend raises permission denied ... ok
tests/test_auth.py::test_permission_denied PASSED [ 10%]
ERROR: test_unicode_file_name (i18n.test_extraction.BasicExtractorTests.test_unicode_file_name)
FAILED (errors=1, skipped=1530, expected failures=7)
"""
    report = diagnose_output(output)
    assert _ids(report) == ["test_failure"]
    assert report["causes"][0]["quote"].startswith("ERROR: test_unicode_file_name")
    # NumPy's Pixi build log (2026-10-22) printed a mangled path with "eacces" inside a
    # word; only the error code on its own means permission denied.
    assert diagnose_output("pixi-pack_plplaageacces/build/work")["causes"] == []
    # The same log's import check: a count of zero is not a failure.
    assert diagnose_output("Checked 115 modules (0 disabled, 0 failed on import)")["causes"] == []
    assert _ids(diagnose_output("Error: EACCES: permission denied, mkdir")) == ["permission"]


def test_a_name_missing_from_an_installed_module_is_not_a_missing_module() -> None:
    # NumPy's CI (2026-10-22): the test is newer than the built copy it imports from.
    numpy = (
        "E   ImportError: cannot import name 'HAS_SUBPROCESSES' from 'numpy.testing' "
        "(/tmp/build-install/usr/lib/python3/dist-packages/numpy/testing/__init__.py)"
    )
    report = diagnose_output(numpy)
    assert _ids(report) == ["import_mismatch"]
    assert report["causes"][0]["name"] == "HAS_SUBPROCESSES"
    assert "rebuild" in " ".join(report["causes"][0]["try"])
    circular = (
        "ImportError: cannot import name 'Parser' from partially initialized module "
        "'lib.parser' (most likely due to a circular import)"
    )
    assert _ids(diagnose_output(circular)) == ["import_mismatch"]
    esm = (
        "SyntaxError: The requested module './utils.js' does not provide an export named "
        "'formatDate'"
    )
    assert diagnose_output(esm)["causes"][0]["name"] == "formatDate"
    webpack = "export 'formatDate' (imported as 'formatDate') was not found in './utils'"
    assert _ids(diagnose_output(webpack)) == ["import_mismatch"]
    # Meson trying archivers in turn is not a missing command.
    probe = (
        "Detecting archiver via: `llvm-ar-20 --version` -> [Errno 2] No such file or "
        "directory: 'llvm-ar-20'"
    )
    assert diagnose_output(probe)["causes"] == []
    # A module that is not there at all is still a missing module.
    assert _ids(diagnose_output("ModuleNotFoundError: No module named 'numpy'")) == [
        "missing_module"
    ]
