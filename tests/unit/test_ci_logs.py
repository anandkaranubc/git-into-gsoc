"""Reading what a failed CI job printed, so `pr-check` and `diagnose` can quote it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from git_into_gsoc.config import Settings
from git_into_gsoc.diagnose import diagnose_output, failing_step
from git_into_gsoc.errors import HttpError, NotFoundError, RateLimitError
from git_into_gsoc.http_client import CachedHttpClient

# Shortened from SymPy's "Check Authors" job on a first pull request (2026-10-21), as the
# logs API returns it: a timestamp on every line, colour codes, and other contributors'
# addresses in the output.
SYMPY_LOG = "\n".join(
    "2026-10-21T19:50:58.1000000Z " + line
    for line in [
        "##[group]Run bin/mailmap_check.py",
        "\x1b[36;1mbin/mailmap_check.py\x1b[0m",
        "shell: /usr/bin/bash -e {0}",
        "##[endgroup]",
        "\x1b[31mThis author is not included in the .mailmap file:\x1b[0m",
        "new-person <new.person@example.com>",
        "\x1b[31m",
        "The .mailmap file needs to be updated because there are commits with",
        "unrecognised author/email metadata.\x1b[0m",
        "\x1b[31m",
        "        For instructions on updating the .mailmap file see:",
        "https://docs.sympy.org/dev/contributing/new-contributors-guide/workflow-process.html"
        "#mailmap-instructions\x1b[0m",
        "\x1b[32m",
        "The following authors will be added to the AUTHORS file at the time of",
        "the next SymPy release.\x1b[0m",
        "Some Contributor <someone@example.org>",
        "##[error]Process completed with exit code 1.",
    ]
)


def test_the_failing_step_is_quoted_from_its_red_lines() -> None:
    step = failing_step(SYMPY_LOG)
    assert step is not None and step["command"] == "bin/mailmap_check.py"
    assert step["printed"][0] == "This author is not included in the .mailmap file:"
    assert step["printed"][-1].endswith("workflow-process.html#mailmap-instructions")
    assert not any("example." in line for line in step["printed"])  # nobody's address
    found = diagnose_output(SYMPY_LOG)
    assert found["step"] == step and "printed its own explanation" in found["summary"]


def test_without_red_text_the_end_of_the_step_is_quoted() -> None:
    # Django's test run: thousands of "... ok" lines, the failure at the end.
    lines = ["##[group]Run python tests/runtests.py", "##[endgroup]"]
    lines += [f"test_{n} (tests.Thing.test_{n}) ... ok" for n in range(200)]
    lines += [
        "..........F..... [ 93%]",
        "ERROR: test_unicode (i18n.tests.Extract.test_unicode)",
        "xgettext: error while opening file for reading: No such file or directory",
        "FAILED (errors=1, skipped=1530)",
        "##[error]Process completed with exit code 1.",
    ]
    step = failing_step("\n".join(lines))
    assert step is not None
    assert step["printed"] == lines[-4:-1]
    # Output that is not a GitHub Actions log has no step.
    assert failing_step("Traceback (most recent call last):\nValueError: x") is None


def _client(tmp_path: Path, handler: Any) -> CachedHttpClient:
    return CachedHttpClient(
        Settings(http_max_retries=0),
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(handler),
    )


def test_a_log_is_read_from_its_end_without_sending_the_token_elsewhere(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    body = ("x" * 99 + "\n") * 5000  # 500 KB, more than the tail kept

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"Location": "https://logs.example.net/job?sig=1"})
        # Storage that ignores the range and sends everything.
        return httpx.Response(200, text=body + "the end\n")

    client = _client(tmp_path, handler)
    tail = client.get_tail(
        "https://api.github.com/repos/o/r/actions/jobs/1/logs",
        headers={"Authorization": "Bearer secret"},
        max_bytes=1000,
    )
    assert tail.endswith("the end\n") and len(tail) <= 1000
    assert tail.startswith("x")  # the cut first line was dropped, so a whole line starts it
    api, storage = seen
    assert api.headers["Authorization"] == "Bearer secret"
    assert "Authorization" not in storage.headers
    assert storage.headers["Range"] == "bytes=-1000"


def test_a_rate_limit_on_a_log_is_a_rate_limit(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9999999999"},
            json={"message": "API rate limit exceeded"},
        )

    client = _client(tmp_path, handler)
    with pytest.raises(RateLimitError):
        client.get_tail(
            "https://api.github.com/repos/o/r/actions/jobs/1/logs",
            headers={"Authorization": "Bearer t"},
        )


def test_an_expired_log_is_a_not_found_error(tmp_path: Path) -> None:
    client = _client(tmp_path, lambda request: httpx.Response(404, json={"message": "Not Found"}))
    with pytest.raises(NotFoundError):
        client.get_tail("https://api.github.com/repos/o/r/actions/jobs/1/logs")


def _toolkit(monkeypatch: pytest.MonkeyPatch, *, token: str | None, log: Any) -> Any:
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "token", token)
    read: list[int] = []

    def tail(owner: str, repo: str, job_id: int) -> str:
        read.append(job_id)
        if isinstance(log, Exception):
            raise log
        return str(log)

    monkeypatch.setattr(toolkit.github, "job_log_tail", tail)
    toolkit.read_jobs = read  # type: ignore[attr-defined]
    return toolkit


def _failing() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks = [
        {"name": "Check Authors", "conclusion": "failure", "id": 11, "app": "github-actions"},
        {"name": "Docs", "conclusion": "failure", "id": 12, "app": "github-actions"},
        {"name": "Tests", "conclusion": "failure", "id": 13, "app": "github-actions"},
        {"name": "CLA", "conclusion": "failure", "id": 14, "app": "cla-bot"},
    ]
    findings = [
        {
            "id": "checks",
            "status": "fail",
            "title": "Failing checks: CLA, Check Authors, Docs, Tests",
            "detail": "Read each log.",
        }
    ]
    return checks, findings


def test_pr_check_quotes_what_the_failed_jobs_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkit = _toolkit(monkeypatch, token="t", log=SYMPY_LOG)
    checks, findings = _failing()
    toolkit._explain_failed_checks("sympy", "sympy", checks, findings)
    detail = findings[0]["detail"]
    assert detail.startswith(
        'Check Authors: `bin/mailmap_check.py` printed "This author is not included'
    )
    assert "and links https://docs.sympy.org/" in detail and detail.endswith("Read each log.")
    assert toolkit.read_jobs == [11, 12]  # two Actions jobs at most; the CLA bot has no log
    assert findings[0]["logs"][0]["step"]["command"] == "bin/mailmap_check.py"


def test_pr_check_says_why_a_log_was_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    checks, findings = _failing()
    toolkit = _toolkit(monkeypatch, token=None, log=SYMPY_LOG)
    toolkit._explain_failed_checks("sympy", "sympy", checks, findings)
    assert "GitHub shows CI logs only with a token" in findings[0]["detail"]
    assert toolkit.read_jobs == []

    checks, findings = _failing()
    expired = NotFoundError("HTTP 404 from api.github.com", status_code=404)
    toolkit = _toolkit(monkeypatch, token="t", log=expired)
    toolkit._explain_failed_checks("sympy", "sympy", checks, findings)
    assert findings[0]["detail"].startswith(
        "Check Authors: the log was not read (GitHub no longer keeps this log)."
    )

    checks, findings = _failing()
    gone = HttpError("HTTP 410 from api.github.com: Server Error", status_code=410)
    toolkit = _toolkit(monkeypatch, token="t", log=gone)
    toolkit._explain_failed_checks("zulip", "zulip-terminal", checks, findings)
    assert "(GitHub no longer keeps this log)" in findings[0]["detail"]

    checks, findings = _failing()
    limited = RateLimitError("GitHub API rate limit exceeded", status_code=403)
    toolkit = _toolkit(monkeypatch, token="t", log=limited)
    toolkit._explain_failed_checks("sympy", "sympy", checks, findings)
    assert "GitHub's rate limit stopped it" in findings[0]["detail"]

    checks, findings = _failing()
    toolkit = _toolkit(monkeypatch, token="t", log=HttpError("HTTP 403", status_code=403))
    toolkit._explain_failed_checks("sympy", "sympy", checks, findings)
    assert "GitHub did not let this token read it" in findings[0]["detail"]
