"""Shared test setup: every test runs without the network, tokens, or the person's
own cache and data folders. Mock HTTP with respx and keep sample responses in
tests/fixtures/."""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

# Rich fixes the console width when cli.py builds its console at import, if COLUMNS
# is set then, and ignores the env={"COLUMNS": ...} a test passes to CliRunner.
# A shell that exported COLUMNS=80 broke five table asserts (#392); at 60, twelve
# more failed. Without it the width follows each CliRunner call, and is 80 otherwise.
os.environ.pop("COLUMNS", None)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def archive_year_json(year: int) -> dict[str, Any]:
    """The archive's per-year file, built from the all-years fixture so the two agree."""
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


def mock_catalog(router: respx.MockRouter, *, archive_year: bool = True) -> None:
    """Answer the organization catalog reads: 2027 not announced, 2026 official, the archive."""
    router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
    router.get(f"{OFFICIAL}/2026/organizations/").mock(
        return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
    )
    router.get(f"{ARCHIVE}/organizations.json").mock(
        return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
    )
    if archive_year:
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=archive_year_json(2026))
        )


class _NetworkBlocked(RuntimeError):
    pass


def rate_limited() -> httpx.Response:
    """GitHub's answer when the hourly quota is used up."""
    return httpx.Response(
        403, headers={"x-ratelimit-remaining": "0"}, json={"message": "API rate limit exceeded"}
    )


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
