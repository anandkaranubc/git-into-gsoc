from __future__ import annotations

from pathlib import Path

import httpx
import respx

from git_into_gsoc.config import Settings
from git_into_gsoc.http_client import CachedHttpClient


@respx.mock
def test_cached_http_client_caches_json(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("GIG_CACHE_TTL_SECONDS", "3600")
    # Redirect cache dir via monkeypatch of cache_dir
    from git_into_gsoc import http_client as hc

    monkeypatch.setattr(hc, "cache_dir", lambda: tmp_path)

    route = respx.get("https://example.test/data.json").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = CachedHttpClient(Settings(cache_ttl_seconds=3600))
    first = client.get_json("https://example.test/data.json")
    second = client.get_json("https://example.test/data.json")
    assert first == {"ok": True}
    assert second == {"ok": True}
    assert route.call_count == 1
    # cache file written
    assert any(tmp_path.joinpath("http").glob("*.json"))
