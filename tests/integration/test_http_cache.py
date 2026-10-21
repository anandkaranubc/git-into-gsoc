from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from git_into_gsoc.config import Settings
from git_into_gsoc.errors import HttpError, NotFoundError, RateLimitError
from git_into_gsoc.http_client import CachedHttpClient

URL = "https://example.test/data.json"


def make_client(tmp_path: Path, **overrides: object) -> tuple[CachedHttpClient, list[float]]:
    sleeps: list[float] = []
    settings = Settings(cache_ttl_seconds=3600, **overrides)  # type: ignore[arg-type]
    client = CachedHttpClient(settings, cache_root=tmp_path / "http", sleep=sleeps.append)
    return client, sleeps


@respx.mock
def test_fresh_cache_avoids_second_request(tmp_path: Path) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    client, _ = make_client(tmp_path)
    assert client.get_json(URL) == {"ok": True}
    assert client.get_json(URL) == {"ok": True}
    assert route.call_count == 1
    assert client.stats["cache_hits"] == 1
    assert list((tmp_path / "http").glob("*.json"))
    assert not list((tmp_path / "http").glob("*.tmp"))


@respx.mock
def test_stale_entry_revalidates_with_etag(tmp_path: Path) -> None:
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json={"v": 1}, headers={"ETag": '"abc"'}),
            httpx.Response(304),
        ]
    )
    client, _ = make_client(tmp_path)
    assert client.get_json(URL, ttl=0) == {"v": 1}
    time.sleep(0.01)
    assert client.get_json(URL, ttl=0) == {"v": 1}
    assert route.calls[1].request.headers["If-None-Match"] == '"abc"'
    assert client.stats["revalidated"] == 1


@respx.mock
def test_compressed_etag_suffix_also_sends_original(tmp_path: Path) -> None:
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json={"v": 1}, headers={"ETag": '"abc-ssl-df"'}),
            httpx.Response(304),
        ]
    )
    client, _ = make_client(tmp_path)
    client.get_json(URL, ttl=0)
    time.sleep(0.01)
    client.get_json(URL, ttl=0)
    assert route.calls[1].request.headers["If-None-Match"] == '"abc-ssl-df", "abc-ssl"'


@respx.mock
def test_retries_transient_server_errors(tmp_path: Path) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"ok": 1})]
    )
    client, sleeps = make_client(tmp_path)
    assert client.get_json(URL, use_cache=False) == {"ok": 1}
    assert route.call_count == 2
    assert sleeps == [0.5]


@respx.mock
def test_rate_limit_raises_with_reset_and_hint(tmp_path: Path) -> None:
    reset = int(time.time()) + 600
    respx.get(URL).mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        )
    )
    client, _ = make_client(tmp_path)
    with pytest.raises(RateLimitError) as info:
        client.get_json(URL, use_cache=False)
    assert info.value.reset_in_seconds is not None
    assert "gh auth login" in (info.value.hint or "")


@respx.mock
def test_short_retry_after_is_honoured(tmp_path: Path) -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    client, sleeps = make_client(tmp_path)
    assert client.get_json(URL, use_cache=False) == {"ok": True}
    assert sleeps == [3.0]


@respx.mock
def test_stale_cache_served_when_rate_limited(tmp_path: Path) -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json={"cached": True}),
            httpx.Response(403, headers={"x-ratelimit-remaining": "0"}),
        ]
    )
    client, _ = make_client(tmp_path)
    client.get_json(URL, ttl=0)
    time.sleep(0.01)
    assert client.get_json(URL, ttl=0) == {"cached": True}
    assert client.stats["stale_served"] == 1


@respx.mock
def test_not_found_is_never_masked_by_stale_cache(tmp_path: Path) -> None:
    respx.get(URL).mock(
        side_effect=[httpx.Response(200, json={"x": 1}), httpx.Response(404, json={})]
    )
    client, _ = make_client(tmp_path)
    client.get_json(URL, ttl=0)
    time.sleep(0.01)
    with pytest.raises(NotFoundError):
        client.get_json(URL, ttl=0)


@respx.mock
def test_network_error_after_retries(tmp_path: Path) -> None:
    respx.get(URL).mock(side_effect=httpx.ConnectError("boom"))
    client, sleeps = make_client(tmp_path, http_max_retries=1)
    with pytest.raises(HttpError, match="Network error"):
        client.get_json(URL, use_cache=False)
    assert len(sleeps) == 1


@respx.mock
def test_unauthorized_has_actionable_hint(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(401, json={"message": "Bad credentials"}))
    client, _ = make_client(tmp_path)
    with pytest.raises(HttpError) as info:
        client.get_json(URL, use_cache=False)
    assert info.value.status_code == 401
    assert "gh auth login" in (info.value.hint or "")


@respx.mock
def test_clear_cache(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    client, _ = make_client(tmp_path)
    client.get_json(URL)
    assert client.cache_size_bytes() > 0
    assert client.clear_cache() == 1
    assert client.cache_size_bytes() == 0
