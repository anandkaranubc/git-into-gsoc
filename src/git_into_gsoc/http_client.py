"""HTTP client with connection pooling, disk caching, and polite retries.

Caching strategy:
* Fresh entries (younger than the TTL) are served without a request.
* Stale entries are revalidated with ETag / Last-Modified. A 304 refreshes the
  entry and, for authenticated GitHub calls, does not count against the quota.
* If the network fails or a rate limit is hit, a stale entry (up to
  `STALE_IF_ERROR_SECONDS` old) is served instead of failing.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from git_into_gsoc.config import Settings, cache_dir, get_settings
from git_into_gsoc.errors import HttpError, NotFoundError, RateLimitError

__all__ = ["CachedHttpClient", "HttpError", "NotFoundError", "RateLimitError"]

log = logging.getLogger(__name__)

STALE_IF_ERROR_SECONDS = 7 * 86400
_RETRY_STATUSES = {500, 502, 503, 504}


class CachedHttpClient:
    """Thread-safe httpx wrapper shared by all API clients."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        cache_root: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._cache_root = cache_root or (cache_dir(self.settings) / "http")
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._sleep = sleep
        self._client = httpx.Client(
            timeout=self.settings.http_timeout_seconds,
            headers={"User-Agent": self.settings.user_agent},
            transport=transport,
            follow_redirects=True,
        )
        self.stats = {"requests": 0, "cache_hits": 0, "revalidated": 0, "stale_served": 0}
        self._throttle_lock = threading.Lock()
        self._last_search = 0.0

    # ------------------------------------------------------------------ public

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        ttl: int | None = None,
    ) -> Any:
        merged = {"Accept": "application/json", **(headers or {})}
        return self._get(url, merged, params, use_cache, ttl, kind="json")

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        ttl: int | None = None,
    ) -> str:
        data = self._get(url, dict(headers or {}), params, use_cache, ttl, kind="text")
        return str(data)

    def post_json(
        self,
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
        ttl: int | None = None,
    ) -> Any:
        """POST a JSON body (GraphQL queries); responses are cached by URL + body."""
        merged = {"Accept": "application/json", **(headers or {})}
        return self._get(url, merged, None, use_cache, ttl, kind="json", json_body=body)

    def clear_cache(self) -> int:
        removed = 0
        for path in self._cache_root.glob("*.json"):
            with contextlib.suppress(OSError):
                path.unlink()
                removed += 1
        return removed

    def cache_size_bytes(self) -> int:
        return sum(p.stat().st_size for p in self._cache_root.glob("*.json") if p.is_file())

    def close(self) -> None:
        self._client.close()

    # ---------------------------------------------------------------- internal

    def _get(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        use_cache: bool,
        ttl: int | None,
        *,
        kind: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        ttl = self.settings.cache_ttl_seconds if ttl is None else ttl
        cache_key = params if json_body is None else {"body": json_body}
        cache_path = self._cache_path(kind, url, cache_key, "Authorization" in headers)
        entry = self._read_cache(cache_path) if use_cache else None
        if entry is not None and time.time() - entry.get("ts", 0) <= ttl:
            self.stats["cache_hits"] += 1
            return entry["data"]

        request_headers = dict(headers)
        if entry is not None:
            if entry.get("etag"):
                request_headers["If-None-Match"] = ", ".join(_etag_candidates(entry["etag"]))
            elif entry.get("last_modified"):
                request_headers["If-Modified-Since"] = entry["last_modified"]

        try:
            response = self._send(url, request_headers, params, json_body=json_body)
        except (RateLimitError, HttpError) as exc:
            if isinstance(exc, NotFoundError) or entry is None:
                raise
            if time.time() - entry.get("ts", 0) > STALE_IF_ERROR_SECONDS:
                raise
            log.warning("Serving stale cache for %s after error: %s", url, exc)
            self.stats["stale_served"] += 1
            return entry["data"]

        if response.status_code == 304 and entry is not None:
            self.stats["revalidated"] += 1
            entry["ts"] = time.time()
            self._write_cache(cache_path, entry)
            return entry["data"]

        data: Any = response.json() if kind == "json" else response.text
        if use_cache:
            self._write_cache(
                cache_path,
                {
                    "ts": time.time(),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "data": data,
                },
            )
        return data

    def _send(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        authenticated = "Authorization" in headers
        method = "GET" if json_body is None else "POST"
        attempts = self.settings.http_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._throttle(url)
            try:
                self.stats["requests"] += 1
                response = self._client.request(
                    method, url, headers=headers, params=params, json=json_body
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    self._sleep(min(2**attempt * 0.5, self.settings.http_max_retry_wait_seconds))
                    continue
                raise HttpError(
                    f"Network error contacting {_host(url)}: {exc}",
                    url=url,
                    hint="Check your connection; cached data is used when available.",
                ) from exc

            if response.status_code < 400 or response.status_code == 304:
                return response

            if _is_rate_limited(response):
                wait = _retry_after_seconds(response)
                if (
                    wait is not None
                    and wait <= self.settings.http_max_retry_wait_seconds
                    and attempt + 1 < attempts
                ):
                    self._sleep(wait)
                    continue
                raise _rate_limit_error(response, url, authenticated)

            if response.status_code in _RETRY_STATUSES and attempt + 1 < attempts:
                self._sleep(min(2**attempt * 0.5, self.settings.http_max_retry_wait_seconds))
                continue

            raise _http_error(response, url)

        raise HttpError(f"Request failed: {last_error}", url=url)  # pragma: no cover

    def _throttle(self, url: str) -> None:
        """Space out GitHub search calls; search has its own, much lower, rate limit."""
        interval = self.settings.search_min_interval_seconds
        if interval <= 0 or "/search/" not in url:
            return
        with self._throttle_lock:
            wait = self._last_search + interval - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            self._last_search = time.monotonic()

    def _cache_path(self, kind: str, url: str, params: dict[str, Any] | None, authed: bool) -> Path:
        raw = json.dumps({"k": kind, "u": url, "p": params or {}, "a": authed}, sort_keys=True)
        return self._cache_root / f"{hashlib.sha256(raw.encode()).hexdigest()}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) and "data" in payload else None

    def _write_cache(self, path: Path, payload: dict[str, Any]) -> None:
        tmp: str | None = None
        try:
            fd, tmp = tempfile.mkstemp(dir=self._cache_root, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as exc:  # cache is best-effort
            log.debug("Cache write failed for %s: %s", path, exc)
            if tmp:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)


def _host(url: str) -> str:
    return httpx.URL(url).host


def _etag_candidates(etag: str) -> list[str]:
    """CDNs (Netlify `-df`, Apache `-gzip`) suffix ETags of compressed bodies but
    only match the original value, so offer both forms."""
    candidates = [etag]
    for suffix in ('-df"', '-gzip"', '-br"'):
        if etag.endswith(suffix):
            candidates.append(etag[: -len(suffix)] + '"')
    return candidates


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get("x-ratelimit-remaining") == "0":
        return True
    return "rate limit" in response.text.lower()


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, (when - datetime.now(UTC)).total_seconds())


def _rate_limit_error(response: httpx.Response, url: str, authenticated: bool) -> RateLimitError:
    reset_at = None
    reset = response.headers.get("x-ratelimit-reset")
    if reset and reset.isdigit():
        reset_at = datetime.fromtimestamp(int(reset), tz=UTC)
    when = f" (resets {reset_at:%H:%M} UTC)" if reset_at else ""
    kind = "secondary rate limit" if "secondary" in response.text.lower() else "rate limit"
    return RateLimitError(
        f"GitHub API {kind} exceeded{when}",
        reset_at=reset_at,
        status_code=response.status_code,
        url=url,
        authenticated=authenticated,
    )


def _http_error(response: httpx.Response, url: str) -> HttpError:
    detail = ""
    with contextlib.suppress(ValueError):
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("message") or "")
    message = f"HTTP {response.status_code} from {_host(url)}" + (f": {detail}" if detail else "")
    if response.status_code == 404:
        return NotFoundError(message, status_code=404, url=url)
    if response.status_code == 401:
        return HttpError(
            message,
            status_code=401,
            url=url,
            hint="Your GitHub token is invalid or expired. Run `gh auth login` or reset GITHUB_TOKEN.",
        )
    if response.status_code == 422:
        return HttpError(message, status_code=422, url=url, hint="The search query was rejected.")
    return HttpError(message, status_code=response.status_code, url=url)
