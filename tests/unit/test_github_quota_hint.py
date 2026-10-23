"""A beginner without a token hears that GitHub's hourly requests are running low before
a command fails. A launch audit (2026-10-23) used 52 of the 60 on the README journey."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from git_into_gsoc import cli
from git_into_gsoc.cli import app
from git_into_gsoc.config import Settings
from git_into_gsoc.http_client import GITHUB_CORE, CachedHttpClient

runner = CliRunner()


def _quota(limit: int, remaining: int, resource: str = "core") -> dict[str, str]:
    return {
        "x-ratelimit-limit": str(limit),
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": str(int(time.time()) + 1800),
        "x-ratelimit-resource": resource,
    }


def test_the_client_keeps_githubs_core_quota_and_nothing_else(tmp_path: Path) -> None:
    answers = {
        "https://api.github.com/repos/o/r": httpx.Response(200, json={}, headers=_quota(60, 12)),
        "https://api.github.com/search/issues": httpx.Response(
            200, json={"items": []}, headers=_quota(10, 3, "search")
        ),
        "https://example.org/ideas": httpx.Response(200, json={}, headers=_quota(60, 1)),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return answers[str(request.url).split("?", 1)[0]]

    client = CachedHttpClient(
        Settings(http_max_retries=0),
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(handler),
    )
    GITHUB_CORE.clear()
    client.get_json("https://api.github.com/repos/o/r")
    assert (GITHUB_CORE["limit"], GITHUB_CORE["remaining"]) == (60, 12)
    # The search quota refills every minute, and another host's headers are not GitHub's.
    client.get_json("https://api.github.com/search/issues")
    client.get_json("https://example.org/ideas")
    assert GITHUB_CORE["remaining"] == 12


@pytest.mark.parametrize(
    ("limit", "remaining", "warned"),
    [(60, 12, True), (60, 15, True), (60, 16, False), (5000, 3, False)],
)
def test_a_command_says_how_many_requests_are_left_only_when_few_are(
    monkeypatch: pytest.MonkeyPatch, limit: int, remaining: int, warned: bool
) -> None:
    class Fake:
        def issue_status(self, ref: str, number: int | None) -> dict[str, Any]:
            reset_at = datetime.now(UTC) + timedelta(minutes=30, seconds=30)
            GITHUB_CORE.update(limit=limit, remaining=remaining, reset_at=reset_at)
            return {"repo": "acme/lib", "number": 7, "url": "https://github.com/acme/lib/issues/7"}

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = runner.invoke(app, ["issue", "acme/lib#7", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert result.stdout.lstrip().startswith("{")  # JSON stays clean on stdout
    line = f"GitHub requests left this hour: {remaining} of 60"
    assert (line in result.stderr) is warned
    if warned:
        assert "resets in 31 minutes" in result.stderr and "gh auth login" in result.stderr
