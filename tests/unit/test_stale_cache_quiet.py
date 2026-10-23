"""Serving a recent cached copy after an error says nothing in the terminal."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import pytest

from git_into_gsoc.config import Settings
from git_into_gsoc.http_client import CachedHttpClient


def test_a_cached_copy_after_an_error_is_served_without_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = [httpx.Response(200, json={"items": [1]}), httpx.Response(500)]

    def handler(request: httpx.Request) -> httpx.Response:
        return answers.pop(0)

    client = CachedHttpClient(
        Settings(http_max_retries=0),
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(handler),
    )
    url = "https://api.github.com/search/issues"
    assert client.get_json(url) == {"items": [1]}
    time.sleep(0.01)
    caplog.set_level(logging.DEBUG)
    # ttl=0: the copy is too old to serve on its own, so the failed request falls back to it.
    assert client.get_json(url, ttl=0) == {"items": [1]}
    assert client.stats["stale_served"] == 1
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    captured = capsys.readouterr()
    assert "Serving stale cache" not in captured.out + captured.err
