"""Shared HTTP helpers with simple disk caching."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

from git_into_gsoc.config import Settings, cache_dir, get_settings


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CachedHttpClient:
    """Thin httpx wrapper with optional JSON disk cache."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache_root = cache_dir() / "http"
        self._cache_root.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, method: str, url: str, params: dict[str, Any] | None) -> Path:
        raw = json.dumps({"m": method, "u": url, "p": params or {}}, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return self._cache_root / f"{digest}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("ts", 0) > self.settings.cache_ttl_seconds:
            return None
        return payload.get("data")

    def _write_cache(self, path: Path, data: Any) -> None:
        path.write_text(
            json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> Any:
        cache_path = self._cache_key("GET", url, params)
        if use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        request_headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            response = client.get(url, headers=request_headers, params=params)

        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise HttpError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN or GH_TOKEN for higher limits.",
                status_code=403,
            )
        if response.status_code >= 400:
            raise HttpError(
                f"HTTP {response.status_code} for {url}: {response.text[:300]}",
                status_code=response.status_code,
            )

        data = response.json()
        if use_cache:
            self._write_cache(cache_path, data)
        return data

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> str:
        cache_path = self._cache_key("GET_TEXT", url, None)
        if use_cache:
            cached = self._read_cache(cache_path)
            if isinstance(cached, str):
                return cached

        request_headers = {"User-Agent": self.settings.user_agent}
        if headers:
            request_headers.update(headers)

        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            response = client.get(url, headers=request_headers, follow_redirects=True)

        if response.status_code >= 400:
            raise HttpError(
                f"HTTP {response.status_code} for {url}",
                status_code=response.status_code,
            )
        text = response.text
        if use_cache:
            self._write_cache(cache_path, text)
        return text
