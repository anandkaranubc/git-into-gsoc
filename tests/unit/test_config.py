from __future__ import annotations

import pytest

from git_into_gsoc import config
from git_into_gsoc.config import Settings, resolve_token


def test_explicit_env_token_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    token, source = resolve_token(Settings())
    assert token == "from-env"
    assert source == "environment"


def test_gh_token_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "gh-env")
    assert Settings().resolve_github_token() == "gh-env"


def test_falls_back_to_gh_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_gh_cli_token", lambda: "from-gh")
    settings = Settings(use_gh_cli=True)
    assert settings.resolve_github_token() == "from-gh"
    assert settings.github_token_source() == "gh auth token"


def test_gh_cli_fallback_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_gh_cli_token", lambda: "from-gh")
    assert Settings(use_gh_cli=False).resolve_github_token() is None


def test_token_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret")
    assert "super-secret" not in repr(Settings())


def test_dirs_follow_settings(tmp_path: object) -> None:
    settings = config.get_settings()
    assert "cache" in str(config.cache_dir(settings))
    assert "data" in str(config.data_dir(settings))
