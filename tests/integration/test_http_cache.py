"""The HTTP cache end to end: fresh and stale entries, ETag revalidation, retries, rate limits,
pruning, and the response size cap, against a mocked server."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from git_into_gsoc.config import Settings
from git_into_gsoc.errors import HttpError, NotFoundError, RateLimitError
from git_into_gsoc.http_client import CachedHttpClient

URL = "https://example.test/data.json"
GITHUB = "https://api.github.com/repos/acme/lib"


def make_client(tmp_path: Path, **overrides: object) -> tuple[CachedHttpClient, list[float]]:
    sleeps: list[float] = []
    overrides.setdefault("http_max_retries", 2)
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
    respx.get(GITHUB).mock(
        return_value=httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        )
    )
    client, _ = make_client(tmp_path)
    with pytest.raises(RateLimitError) as info:
        client.get_json(GITHUB, use_cache=False)
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
    # Only GitHub's refusal is about the GitHub token; other hosts get their own hint.
    github = "https://api.github.com/repos/a/b"
    respx.get(github).mock(return_value=httpx.Response(401, json={"message": "Bad credentials"}))
    client, _ = make_client(tmp_path)
    with pytest.raises(HttpError) as info:
        client.get_json(github, use_cache=False)
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


@respx.mock
def test_search_rate_limit_gets_a_search_specific_hint() -> None:
    import pytest

    from git_into_gsoc.errors import RateLimitError

    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-resource": "search"},
            json={"message": "API rate limit exceeded"},
        )
    )
    respx.get("https://api.github.com/repos/a/b").mock(
        return_value=httpx.Response(
            403, headers={"x-ratelimit-remaining": "0"}, json={"message": "rate limit"}
        )
    )
    client = CachedHttpClient()
    with pytest.raises(RateLimitError) as search:
        client.get_json("https://api.github.com/search/issues", params={"q": "x"})
    assert search.value.resource == "search"
    assert "search rate limit" in str(search.value)
    assert "10 requests a minute" in (search.value.hint or "")
    with pytest.raises(RateLimitError) as core:
        client.get_json("https://api.github.com/repos/a/b")
    assert core.value.resource == "core"
    assert "gh auth login" in (core.value.hint or "")


@respx.mock
def test_an_answer_that_is_not_json_is_explained(tmp_path: Path) -> None:
    portal = httpx.Response(200, text="<html>Sign in to the Wi-Fi</html>")
    respx.get(URL).mock(side_effect=[httpx.Response(200, json={"v": 1}), portal, portal])
    client, _ = make_client(tmp_path)
    assert client.get_json(URL, ttl=0) == {"v": 1}
    time.sleep(0.01)
    assert client.get_json(URL, ttl=0) == {"v": 1}  # the recent copy stands in
    with pytest.raises(HttpError, match="not JSON") as failed:
        client.get_json(URL, use_cache=False)
    assert "Wi-Fi" in (failed.value.hint or "")


@respx.mock
def test_a_redirect_loop_is_explained_and_not_retried(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(302, headers={"Location": URL}))
    client, sleeps = make_client(tmp_path)
    with pytest.raises(HttpError, match="redirects"):
        client.get_text(URL)
    assert sleeps == []


@respx.mock
def test_a_retry_after_date_without_a_time_zone_counts_as_utc(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    later = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=10)
    stamp = format_datetime(later)
    assert stamp.endswith("-0000")
    respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": stamp}))
    client, _ = make_client(tmp_path)
    with pytest.raises(RateLimitError) as limited:
        client.get_json(URL, use_cache=False)
    assert 500 < (limited.value.reset_in_seconds or 0) <= 600


@respx.mock
def test_a_limit_on_another_site_names_it_and_does_not_suggest_gh(tmp_path: Path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(429))
    client, _ = make_client(tmp_path)
    with pytest.raises(RateLimitError) as limited:
        client.get_json(URL, use_cache=False)
    assert "example.test" in str(limited.value)
    assert "GitHub" not in str(limited.value)
    assert "gh auth" not in (limited.value.hint or "")


@respx.mock
def test_a_secondary_limit_resets_when_retry_after_says(tmp_path: Path) -> None:
    respx.get(GITHUB).mock(
        return_value=httpx.Response(
            403,
            json={"message": "You have exceeded a secondary rate limit."},
            headers={
                "Retry-After": "60",
                "x-ratelimit-remaining": "4800",
                "x-ratelimit-reset": str(int(time.time()) + 3000),
            },
        )
    )
    client, _ = make_client(tmp_path)
    with pytest.raises(RateLimitError, match="secondary rate limit") as limited:
        client.get_json(GITHUB, headers={"Authorization": "Bearer t"}, use_cache=False)
    assert 50 < (limited.value.reset_in_seconds or 0) <= 60


@respx.mock
def test_a_graphql_answer_with_errors_is_not_cached(tmp_path: Path) -> None:
    graphql = "https://example.test/graphql"
    route = respx.post(graphql).mock(
        side_effect=[
            httpx.Response(200, json={"errors": [{"type": "RATE_LIMITED"}]}),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]
    )
    client, _ = make_client(tmp_path)
    client.post_json(graphql, {"query": "q"})
    assert client.post_json(graphql, {"query": "q"}) == {"data": {"ok": True}}
    assert route.call_count == 2


def _aged(path: Path, days: float, size: int = 10) -> Path:
    path.write_bytes(b"x" * size)
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))
    return path


def _client_for(tmp_path: Path, **overrides: object) -> CachedHttpClient:
    settings = Settings(**overrides)  # type: ignore[arg-type]
    return CachedHttpClient(settings, cache_root=tmp_path / "http")


def test_prune_deletes_entries_not_refreshed_within_the_age_limit(tmp_path: Path) -> None:
    client = _client_for(tmp_path, cache_max_age_days=30)
    root = tmp_path / "http"
    old = _aged(root / "old.json", 31)
    fresh = _aged(root / "fresh.json", 29)
    leftover = _aged(root / "write.tmp", 0.1)
    live = _aged(root / "live.tmp", 0.001)
    assert client.prune_cache() == 2
    assert not old.exists() and not leftover.exists()
    assert fresh.exists() and live.exists()


def test_prune_removes_the_oldest_entries_above_the_size_cap(tmp_path: Path) -> None:
    client = _client_for(tmp_path, cache_max_mb=1, cache_max_age_days=0)
    root = tmp_path / "http"
    files = [_aged(root / f"{i}.json", 10 - i, size=600_000) for i in range(3)]
    assert client.prune_cache() == 2
    assert [f.exists() for f in files] == [False, False, True]


def test_zero_turns_both_limits_off(tmp_path: Path) -> None:
    client = _client_for(tmp_path, cache_max_mb=0, cache_max_age_days=0)
    old = _aged(tmp_path / "http" / "old.json", 400, size=2_000_000)
    assert client.prune_cache() == 0 and old.exists()


def test_pruning_runs_on_start_at_most_once_a_day(tmp_path: Path) -> None:
    root = tmp_path / "http"
    root.mkdir()
    first = _aged(root / "first.json", 60)
    _client_for(tmp_path)
    assert not first.exists()
    second = _aged(root / "second.json", 60)
    _client_for(tmp_path)
    assert second.exists(), "pruned twice within a day"
    _aged(root / ".last-pruned", 2)
    _client_for(tmp_path)
    assert not second.exists()


def test_a_response_larger_than_the_cap_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import git_into_gsoc.http_client as http_module

    monkeypatch.setattr(http_module, "MAX_RESPONSE_BYTES", 1000)
    client, _ = make_client(tmp_path)
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, content=b"x" * 5000))
        with pytest.raises(HttpError, match="larger than"):
            client.get_text(URL)
        respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
        assert client.get_json(URL) == {"ok": True}


def test_a_small_compressed_bomb_is_counted_after_decompression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gzip

    import git_into_gsoc.http_client as http_module

    monkeypatch.setattr(http_module, "MAX_RESPONSE_BYTES", 100_000)
    bomb = gzip.compress(b"\0" * 5_000_000)  # about 5 KB on the wire
    client, _ = make_client(tmp_path)
    with respx.mock:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200, stream=httpx.ByteStream(bomb), headers={"Content-Encoding": "gzip"}
            )
        )
        with pytest.raises(HttpError, match="larger than"):
            client.get_text(URL)


def test_compressed_responses_still_decode(tmp_path: Path) -> None:
    import gzip

    client, _ = make_client(tmp_path)
    with respx.mock:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200,
                stream=httpx.ByteStream(gzip.compress(b'{"ok": true}')),
                headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
            )
        )
        assert client.get_json(URL) == {"ok": True}
        respx.get(URL).mock(
            return_value=httpx.Response(
                200, stream=httpx.ByteStream(b"not gzip"), headers={"Content-Encoding": "gzip"}
            )
        )
        with pytest.raises(HttpError, match="decompressed"):
            client.get_text(URL, use_cache=False)


def test_a_server_that_drips_its_answer_is_cut_off(tmp_path: Path) -> None:
    now = [0.0]

    def drip() -> Iterator[bytes]:
        for _ in range(1000):
            now[0] += 1  # each byte arrives well inside the 30-second read timeout
            yield b" "

    client = CachedHttpClient(
        Settings(http_max_retries=0, http_timeout_seconds=30),
        cache_root=tmp_path / "http",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=drip())),
        clock=lambda: now[0],
    )
    with pytest.raises(HttpError, match="took longer than"):
        client.get_text(URL, use_cache=False)
    assert now[0] < 1000
