"""A 404 is remembered, so missing pages are not asked for on every command."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from git_into_gsoc.config import Settings
from git_into_gsoc.errors import HttpError, NotFoundError
from git_into_gsoc.http_client import CachedHttpClient


def _client(tmp_path: Path, handler: object) -> CachedHttpClient:
    return CachedHttpClient(
        Settings(http_max_retries=0),
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_a_missing_page_is_asked_for_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404, json={"message": "Not Found"})

    client = _client(tmp_path, handler)
    url = "https://summerofcode.withgoogle.com/api/program/2027/organizations/"
    with pytest.raises(NotFoundError, match="Not Found"):
        client.get_json(url, ttl=86400)
    with pytest.raises(NotFoundError, match="Not Found"):
        client.get_json(url, ttl=86400)
    assert calls == [url]
    assert client.stats["cache_hits"] == 1


def test_a_page_that_appears_is_seen_once_the_memory_is_stale(tmp_path: Path) -> None:
    answers = [httpx.Response(404), httpx.Response(200, json=[{"name": "An org"}])]

    def handler(request: httpx.Request) -> httpx.Response:
        return answers.pop(0)

    client = _client(tmp_path, handler)
    url = "https://summerofcode.withgoogle.com/api/program/2027/organizations/"
    with pytest.raises(NotFoundError):
        client.get_json(url)
    # ttl=0: the remembered 404 is too old, so the page is asked for again.
    assert client.get_json(url, ttl=0) == [{"name": "An org"}]
    assert not answers


def test_a_not_found_memory_is_not_served_after_a_network_error(tmp_path: Path) -> None:
    answers: list[httpx.Response | Exception] = [httpx.Response(404), httpx.ConnectError("down")]

    def handler(request: httpx.Request) -> httpx.Response:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client = _client(tmp_path, handler)
    url = "https://api.github.com/repos/someone/missing"
    with pytest.raises(NotFoundError):
        client.get_json(url)
    # A stale 404 is not a copy of the page: the network error is reported as itself.
    with pytest.raises(HttpError, match="Network error"):
        client.get_json(url, ttl=0)
