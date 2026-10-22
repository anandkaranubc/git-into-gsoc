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
import ipaddress
import json
import logging
import os
import socket
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from git_into_gsoc.config import Settings, cache_dir, cache_location, get_settings
from git_into_gsoc.errors import HttpError, NotFoundError, RateLimitError, reset_phrase

__all__ = ["CachedHttpClient", "HttpError", "NotFoundError", "RateLimitError"]

log = logging.getLogger(__name__)

STALE_IF_ERROR_SECONDS = 7 * 86400
PRUNE_INTERVAL_SECONDS = 86400
# The largest real response is the full organization list (about 15 MB). Pages that
# strangers can edit are linked from ideas pages, so a body (after decompression)
# larger than this is refused instead of filling memory.
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
# Left by a write that was interrupted; a live write finishes in well under this.
STALE_TMP_SECONDS = 3600
_PRUNE_MARKER = ".last-pruned"
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
        try:
            self._cache_root = cache_root or (cache_dir(self.settings) / "http")
            self._cache_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # A sandboxed assistant may forbid writing outside the project. Reading and
            # writing the cache are best-effort already, so run without one.
            log.warning("Running without a response cache: %s", exc)
            self._cache_root = cache_root or (cache_location(self.settings) / "http")
        self._sleep = sleep
        self._prune_if_due()
        # Service addresses the user configured may be local (a mirror, a test server).
        self._trusted_origins = {
            _origin(httpx.URL(url))
            for url in (
                self.settings.github_api_url,
                self.settings.gsoc_orgs_api_url,
                self.settings.gsoc_official_api_url,
                self.settings.ecosystems_commits_api_url,
            )
        }
        self._client = httpx.Client(
            timeout=self.settings.http_timeout_seconds,
            headers={"User-Agent": self.settings.user_agent},
            transport=transport,
            follow_redirects=True,
            event_hooks={"request": [self._refuse_private_address]},
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
        """GET `url` and parse the JSON body, through the cache.

        A fresh cached copy is served without a request; a stale one is revalidated.
        Raises HttpError (NotFoundError for a 404, RateLimitError for a limit) when
        the request fails and no cached copy under a week old can stand in.
        """
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
        """GET `url` as text, with the same caching and errors as `get_json`."""
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

    def get_tail(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int = 200_000,
        timeout: float = 20.0,
    ) -> str:
        """The last `max_bytes` of a large text body, such as a CI job's log. Not cached.

        GitHub answers a log request with a redirect to short-lived storage on another
        host. That second request carries no Authorization header and asks for the end
        of the file only, so a log of tens of megabytes costs a few hundred kilobytes.
        """
        try:
            self._throttle(url)
            request = self._client.build_request("GET", url, headers=headers or {}, timeout=timeout)
            self.stats["requests"] += 1
            response = self._client.send(request, stream=True, follow_redirects=False)
            location = response.headers.get("Location")
            if response.is_redirect and location:
                response.close()
                # Only the range: the token was for GitHub, not for the storage host.
                follow = self._client.build_request(
                    "GET",
                    response.url.join(location),
                    headers={"Range": f"bytes=-{max_bytes}"},
                    timeout=timeout,
                )
                self.stats["requests"] += 1
                response = self._client.send(follow, stream=True, follow_redirects=False)
            try:
                if response.status_code >= 400:
                    response.read()
                    if _is_rate_limited(response):
                        raise _rate_limit_error(response, url, "Authorization" in (headers or {}))
                    raise _http_error(response, url)
                tail, seen = b"", 0
                for chunk in response.iter_bytes():
                    seen += len(chunk)
                    if seen > MAX_RESPONSE_BYTES:
                        raise HttpError(
                            f"The log from {_host(url)} is larger than "
                            f"{MAX_RESPONSE_BYTES // 1_048_576} MB, so it was not read.",
                            url=url,
                        )
                    # A server that ignores the range sends everything: keep the end.
                    tail = (tail + chunk)[-max_bytes:]
            finally:
                response.close()
        except httpx.HTTPError as exc:
            raise HttpError(f"Could not read {_host(url)}: {exc}", url=url) from exc
        text = tail.decode("utf-8", errors="replace")
        if len(tail) >= max_bytes and "\n" in text:
            text = text.split("\n", 1)[1]  # the first line was cut in the middle
        return text

    def clear_cache(self) -> int:
        removed = 0
        for path in self._cache_root.glob("*.json"):
            with contextlib.suppress(OSError):
                path.unlink()
                removed += 1
        return removed

    def prune_cache(self, *, now: float | None = None) -> int:
        """Delete entries not refreshed within the age limit, then the oldest entries
        until the cache fits the size cap. Returns how many files were removed."""
        now = time.time() if now is None else now
        max_age = self.settings.cache_max_age_days * 86400
        budget = self.settings.cache_max_mb * 1_048_576
        removed = 0
        kept: list[tuple[float, int, Path]] = []
        for path in self._cache_root.iterdir():
            if path.suffix not in {".json", ".tmp"}:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            age = now - stat.st_mtime
            stale_tmp = path.suffix == ".tmp" and age > STALE_TMP_SECONDS
            if stale_tmp or (path.suffix == ".json" and 0 < max_age < age):
                removed += _unlink(path)
            elif path.suffix == ".json":
                kept.append((stat.st_mtime, stat.st_size, path))
        total = sum(size for _, size, _ in kept)
        for _, size, path in sorted(kept):  # oldest first
            if budget <= 0 or total <= budget:
                break
            if _unlink(path):
                removed += 1
                total -= size
        return removed

    def _prune_if_due(self) -> None:
        """Prune at most once a day; a marker file's age says when it last ran."""
        marker = self._cache_root / _PRUNE_MARKER
        try:
            if time.time() - marker.stat().st_mtime < PRUNE_INTERVAL_SECONDS:
                return
        except FileNotFoundError:
            pass
        except OSError:
            return
        try:
            marker.touch()
            removed = self.prune_cache()
        except OSError as exc:  # a read-only or vanished cache never blocks a command
            log.debug("Cache prune skipped: %s", exc)
            return
        if removed:
            log.info("Pruned %d old cache entries", removed)

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
                response = self._request_capped(method, url, headers, params, json_body)
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

    def _refuse_private_address(self, request: httpx.Request) -> None:
        """Runs before every request, redirects included.

        Ideas pages and wikis that strangers can edit link to other pages, and the
        tool follows some of those links. A link (or a redirect) to this computer or
        its local network must never be fetched on the reader's behalf.
        """
        host = request.url.host
        if _origin(request.url) not in self._trusted_origins and is_private_host(host):
            raise HttpError(
                f"Refused to fetch {host}: it is a local or private network address.",
                url=str(request.url),
                hint="git-into-gsoc reads only public pages; links to private addresses "
                "are skipped.",
            )

    def _request_capped(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        """Like ``client.request``, but stop reading once the body passes the cap.

        The body is counted after decompression, so a small compressed bomb is caught
        too. The returned response holds the decoded body, without encoding headers.
        """
        request = self._client.build_request(
            method, url, headers=headers, params=params, json=json_body
        )
        undecodable = f"The response from {_host(url)} could not be decompressed."
        try:
            response = self._client.send(request, stream=True)
        except httpx.DecodingError as exc:
            raise HttpError(undecodable, url=url) from exc
        try:
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise HttpError(
                        f"The response from {_host(url)} is larger than "
                        f"{MAX_RESPONSE_BYTES // 1_048_576} MB, so it was not read.",
                        url=url,
                        hint="Open the page in a browser instead.",
                    )
                chunks.append(chunk)
        except httpx.DecodingError as exc:
            raise HttpError(undecodable, url=url) from exc
        finally:
            response.close()
        kept = [
            (key, value)
            for key, value in response.headers.multi_items()
            if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        ]
        return httpx.Response(
            response.status_code,
            headers=kept,
            content=b"".join(chunks),
            request=response.request,
        )

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


def _unlink(path: Path) -> int:
    """1 when the file was removed; another process may have removed it first."""
    try:
        path.unlink()
    except OSError:
        return 0
    return 1


def _host(url: str) -> str:
    return httpx.URL(url).host


def _origin(url: httpx.URL) -> tuple[str, str, int | None]:
    return url.scheme, url.host, url.port


_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa", ".lan")


def is_private_host(host: str) -> bool:
    """True when a host names this computer or a private network.

    Covers local names and every way of writing an address directly
    (127.1, 2130706433, 0x7f.0.0.1, [::1], ::ffff:127.0.0.1). Public names that
    resolve to private addresses are not caught here; that would need a DNS lookup
    per request.
    """
    name = host.strip("[]").rstrip(".").lower()
    if not name:
        return False
    if name == "localhost" or name.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        address: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(name)
    except ValueError:
        if not all(part.isalnum() for part in name.split(".")):
            return False  # a hostname with hyphens or underscores, never an address
        try:
            address = ipaddress.IPv4Address(socket.inet_aton(name))
        except OSError:
            return False
    mapped = getattr(address, "ipv4_mapped", None)
    return not (mapped or address).is_global


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
    when = f"; it {reset_phrase(reset_at)}" if reset_at else ""
    resource = response.headers.get("x-ratelimit-resource") or (
        "search" if "/search/" in url else "core"
    )
    if "secondary" in response.text.lower():
        kind = "secondary rate limit"
    elif resource == "search":
        kind = "search rate limit"
    else:
        kind = "rate limit"
    return RateLimitError(
        f"GitHub API {kind} exceeded{when}",
        reset_at=reset_at,
        status_code=response.status_code,
        url=url,
        authenticated=authenticated,
        resource=resource,
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
        reasons = []
        with contextlib.suppress(ValueError, AttributeError, TypeError):
            reasons = [str(e.get("message")) for e in response.json().get("errors") or []]
        reason = next((r for r in reasons if r and r != "None"), "")
        if "cannot be searched" in reason:
            return HttpError(
                f"GitHub could not run the search: {reason}",
                status_code=422,
                url=url,
                hint="Check the spelling of the user, organization, or repository you gave.",
            )
        return HttpError(
            message + (f" ({reason})" if reason else ""),
            status_code=422,
            url=url,
            hint="The search query was rejected.",
        )
    return HttpError(message, status_code=response.status_code, url=url)
