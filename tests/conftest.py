"""Shared test setup: every test runs without the network, tokens, or the person's
own cache and data folders. Mock HTTP with respx and keep sample responses in
tests/fixtures/."""

from __future__ import annotations

import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _NetworkBlocked(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def hermetic_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate every test from the user's tokens, cache, data, and the network."""
    from git_into_gsoc import config

    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GIG_GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIG_USE_GH_CLI", "false")
    monkeypatch.setenv("GIG_HTTP_MAX_RETRIES", "0")
    monkeypatch.setenv("GIG_SEARCH_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("GIG_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("GIG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    config.get_settings.cache_clear()
    config._gh_cli_token.cache_clear()

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise _NetworkBlocked("Network access is disabled in tests; mock with respx.")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    # The shipped ideas-page and repository evidence is refreshed weekly; tests
    # that rank fixture organizations must not change when it does. Tests of
    # that evidence pass their own (see tests/unit/test_matching*.py).
    from git_into_gsoc.gsoc import client as gsoc_client

    monkeypatch.setattr(
        gsoc_client,
        "load_signals",
        lambda: {"generated": None, "year": None, "organizations": {}},
    )
    yield
    config.get_settings.cache_clear()
