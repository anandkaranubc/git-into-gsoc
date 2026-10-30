"""Links in pages strangers can edit must never make the tool fetch local addresses."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from git_into_gsoc.config import Settings
from git_into_gsoc.errors import HttpError
from git_into_gsoc.http_client import CachedHttpClient, is_private_host


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "localhost",
        "LOCALHOST.",
        "[::1]",
        "169.254.169.254",
        "10.0.0.1",
        "192.168.1.1",
        "0.0.0.0",
        "2130706433",
        "127.1",
        "::ffff:127.0.0.1",
        "printer.local",
        "db.internal",
        "fd00::1",
        "instance-data",
        "nas",
        "::127.0.0.1",
        "64:ff9b::a9fe:a9fe",
    ],
)
def test_local_and_private_hosts_are_recognised(host: str) -> None:
    assert is_private_host(host)


@pytest.mark.parametrize(
    "host",
    [
        "github.com",
        "api.github.com",
        "8.8.8.8",
        "example.test",
        "cafe.example",
        "my-host.example.org",
        "64:ff9b::808:808",
        "",
    ],
)
def test_public_hosts_are_not_refused(host: str) -> None:
    assert not is_private_host(host)


def _client(tmp_path: Path, handler: object, **settings: object) -> CachedHttpClient:
    return CachedHttpClient(
        Settings(http_max_retries=0, **settings),  # type: ignore[arg-type]
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_private_addresses_are_refused_even_after_a_redirect(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "ideas.example.org":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1:8080/admin"})
        return httpx.Response(200, text="private")

    client = _client(tmp_path, handler)
    for url in (
        "http://127.0.0.1:8080/admin",
        "http://localhost:3000/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "https://ideas.example.org/gsoc",
    ):
        with pytest.raises(HttpError, match="private network address"):
            client.get_text(url, use_cache=False)
    assert requested == ["https://ideas.example.org/gsoc"]


def test_a_configured_local_service_still_works(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = _client(tmp_path, handler, github_api_url="http://localhost:8080/api/v3")
    assert client.get_json("http://localhost:8080/api/v3/rate_limit", use_cache=False) == {
        "ok": True
    }
    with pytest.raises(HttpError, match="private network address"):
        client.get_text("http://localhost:9999/other", use_cache=False)


def test_an_ideas_page_linking_to_a_local_address_is_read_without_it(tmp_path: Path) -> None:
    from git_into_gsoc.gsoc.project_ideas import fetch_ideas_document

    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text="private")

    client = _client(tmp_path, handler)
    assert fetch_ideas_document(client, "http://127.0.0.1:8888/gsoc-ideas", ttl=60) is None
    assert requested == []
