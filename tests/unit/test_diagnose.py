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
